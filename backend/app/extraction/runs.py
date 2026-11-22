"""Extraction runs: one run is one folder under `settings.runs_dir/<id>`.

    <run>/run.json       the `RunStatus`, saved on every change
    <run>/events.jsonl   one `RunEvent` per line: every tool call and text block of the agent
    <run>/input/ work/ results/   see `workspace.py`

A run does the extraction flow: the agent session, then `propose_model` when the agent made
`results/components.json`. When asked, the analysis follows in `<run>/analysis/`, or starts alone
on a copy of an earlier run's results. One run at a time: the machine is busy with reader calls
during a run.
"""

import asyncio
import logging
import re
import secrets
import shutil
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from ..analysis.session import (
    UPSTREAM,
    AnalysisError,
    AnalysisResult,
    analyse_results,
    check_designer_numbers,
)
from ..settings import Settings
from .agent import AgentResult, EventSink, run_agent
from .proposal import propose_model
from .queue import ReadLimits
from .reader import Reader, ReaderError
from .workspace import ExtractionError, Workspace

log = logging.getLogger(__name__)

RunState = Literal["running", "done", "failed", "cancelled", "interrupted"]
RUN_ID = re.compile(r"^[0-9]{8}-[0-9]{6}-[0-9a-f]{4}$")

AgentFunction = Callable[
    [Workspace, Settings, Reader, ReadLimits, EventSink], Awaitable[AgentResult]
]

AnalysisFunction = Callable[
    [Path, Path, str, dict[str, Any] | None, dict[str, Any] | None, EventSink],
    Awaitable[AnalysisResult],
]


class RunBusyError(Exception):
    """A run is already running."""


class RunNotFoundError(Exception):
    pass


class RunStatus(BaseModel):
    id: str
    state: RunState
    files: list[str]
    started: datetime
    finished: datetime | None = None
    activity: str = ""
    agent_cost_usd: float = 0.0
    reads_cost_usd: float = 0.0
    reply: str = ""
    error: str = ""
    results: list[str] = []
    """Files in `results/`, relative to the run folder."""
    phase: Literal["extraction", "analysis"] = "extraction"
    source_run: str | None = None
    """The earlier run whose extraction results this analysis uses."""
    analysis_session_id: str | None = None
    analysis_cost_usd: float = 0.0
    analysis_runlog: str | None = None
    analysis_validator: int | None = None
    """Exit code of the kit's validator: 0 passed, 1 failed, 2 could not finish."""


@dataclass(frozen=True)
class AnalysisRequest:
    timings: dict[str, Any] | None = None
    focus: dict[str, Any] | None = None


class RunEvent(BaseModel):
    index: int
    """Starts at 1. `events(id, after=n)` returns the events with a higher index."""
    at: datetime
    kind: str
    text: str


def _now() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return f"{_now():%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"


class RunManager:
    def __init__(
        self,
        settings: Settings,
        reader: Reader,
        agent: AgentFunction = run_agent,
        propose: Callable[[Workspace, Reader], Awaitable[object]] = propose_model,
        analyse: AnalysisFunction = analyse_results,
    ):
        self.settings = settings
        self.reader = reader
        self.agent = agent
        self.propose = propose
        self.analyse = analyse
        self.limits = ReadLimits(parallel=settings.parallel_reads)
        self._task: asyncio.Task | None = None
        self._active_id: str | None = None

    # ------------------------------------------------------------ starting and stopping

    def start(self, files: dict[str, bytes], analysis: AnalysisRequest | None = None) -> RunStatus:
        """Saves the files in a new run folder and starts the run. Call it inside the event loop.

        With `analysis`, the analysis phase follows the extraction."""
        self._check_free()
        if not files:
            raise ExtractionError("no files to extract")
        if analysis:
            check_designer_numbers(analysis.timings, analysis.focus)
        run_id = _new_id()
        ws = Workspace(self.settings.runs_dir / run_id).create()
        for name, data in files.items():
            (ws.input / Path(name).name).write_bytes(data)
        status = RunStatus(
            id=run_id, state="running", files=ws.uploaded_files(), started=_now(), activity="start"
        )
        self._save(ws, status)
        self._active_id = run_id
        self._task = asyncio.create_task(self._run(ws, status, analysis))
        return status

    def start_analysis(self, source_run: str, analysis: AnalysisRequest) -> RunStatus:
        """Starts a new run that does only the analysis, on an earlier run's extraction results."""
        self._check_free()
        check_designer_numbers(analysis.timings, analysis.focus)
        source = self.workspace(source_run)
        missing = [name for name in UPSTREAM if not (source.results / name).is_file()]
        if missing:
            raise AnalysisError(f"run {source_run} has no {', '.join(missing)}")
        ws = Workspace(self.settings.runs_dir / _new_id()).create()
        for name in UPSTREAM:
            shutil.copy(source.results / name, ws.results / name)
        status = RunStatus(
            id=ws.root.name,
            state="running",
            files=[],
            started=_now(),
            activity="start",
            phase="analysis",
            source_run=source_run,
        )
        self._save(ws, status)
        self._active_id = status.id
        self._task = asyncio.create_task(self._run(ws, status, analysis))
        return status

    def _check_free(self) -> None:
        if self._active_id is not None:
            raise RunBusyError(f"run {self._active_id} is still running")

    def cancel(self, run_id: str) -> RunStatus:
        """Stops a running run. Does nothing for a run that has ended."""
        status = self.get(run_id)
        if self._active_id == run_id and self._task is not None:
            self._task.cancel()
        return status

    async def wait(self) -> None:
        """Waits until the current run has ended (for tests and the CLI)."""
        if self._task is not None:
            await asyncio.gather(self._task, return_exceptions=True)

    # ------------------------------------------------------------ reading

    def get(self, run_id: str) -> RunStatus:
        path = self._folder(run_id) / "run.json"
        if not path.exists():
            raise RunNotFoundError(run_id)
        status = RunStatus.model_validate_json(path.read_text())
        if status.state == "running" and run_id != self._active_id:
            # The backend stopped during this run. Nothing runs it now.
            status.state = "interrupted"
            status.finished = status.finished or _now()
            (self._folder(run_id) / "run.json").write_text(status.model_dump_json(indent=1))
        return status

    def list_runs(self) -> list[RunStatus]:
        """All runs, newest first."""
        if not self.settings.runs_dir.exists():
            return []
        ids = sorted(
            (p.name for p in self.settings.runs_dir.iterdir() if RUN_ID.match(p.name)),
            reverse=True,
        )
        return [self.get(run_id) for run_id in ids if (self._folder(run_id) / "run.json").exists()]

    def events(self, run_id: str, after: int = 0) -> list[RunEvent]:
        self.get(run_id)
        path = self._folder(run_id) / "events.jsonl"
        if not path.exists():
            return []
        events = [RunEvent.model_validate_json(line) for line in path.read_text().splitlines()]
        return [event for event in events if event.index > after]

    def workspace(self, run_id: str) -> Workspace:
        self.get(run_id)
        return Workspace(self._folder(run_id))

    def _folder(self, run_id: str) -> Path:
        if not RUN_ID.match(run_id):
            raise RunNotFoundError(run_id)
        return self.settings.runs_dir / run_id

    # ------------------------------------------------------------ the run

    async def _run(
        self, ws: Workspace, status: RunStatus, analysis: AnalysisRequest | None
    ) -> None:
        counter = _EventLog(ws.root / "events.jsonl")

        def on_event(kind: str, text: str) -> None:
            counter.add(kind, text)
            status.activity = f"{kind}: {text}"[:200]
            self._save(ws, status)

        try:
            if status.phase == "extraction":
                await self._run_extraction(ws, status, on_event)
            if analysis and status.state == "running":
                await self._run_analysis(ws, status, analysis, on_event)
            if status.state == "running":
                status.state = "done"
        except asyncio.CancelledError:
            status.state = "cancelled"
            counter.add("end", "cancelled")
        except (ExtractionError, ReaderError, AnalysisError) as e:
            status.state, status.error = "failed", str(e)
            counter.add("error", str(e))
        except Exception as e:
            log.exception("run %s failed", status.id)
            status.state, status.error = "failed", f"{type(e).__name__}: {e}"
            counter.add("error", status.error)
        finally:
            status.finished = _now()
            self._save(ws, status)
            self._active_id = None

    async def _run_extraction(self, ws: Workspace, status: RunStatus, on_event: EventSink) -> None:
        result = await self.agent(ws, self.settings, self.reader, self.limits, on_event)
        status.reply, status.agent_cost_usd = result.reply, result.cost_usd
        if result.is_error:
            status.state, status.error = "failed", result.reply or "the agent session failed"
            return
        if (ws.results / "components.json").exists():
            on_event("step", "propose_model")
            await self.propose(ws, self.reader)

    async def _run_analysis(
        self, ws: Workspace, status: RunStatus, analysis: AnalysisRequest, on_event: EventSink
    ) -> None:
        status.phase = "analysis"
        on_event("phase", "analysis")
        result = await self.analyse(
            ws.results,
            ws.root / "analysis",
            self.settings.analysis_model,
            analysis.timings,
            analysis.focus,
            on_event,
        )
        status.reply = result.reply
        status.analysis_session_id = result.session_id
        status.analysis_cost_usd = result.cost_usd
        status.analysis_runlog = result.runlog
        status.analysis_validator = result.validator_exit
        if result.is_error:
            raise AnalysisError(result.reply or "the analysis session failed")
        if result.validator_exit != 0:
            raise AnalysisError(f"the kit's validator gave exit {result.validator_exit}")

    def _save(self, ws: Workspace, status: RunStatus) -> None:
        from . import cost

        status.results = sorted(ws.rel(p) for p in ws.results.iterdir() if p.is_file())
        status.reads_cost_usd = cost.total_cost(ws)
        (ws.root / "run.json").write_text(status.model_dump_json(indent=1))


class _EventLog:
    """Appends events to `events.jsonl` with a running index."""

    def __init__(self, path: Path):
        self.path = path
        self.count = 0

    def add(self, kind: str, text: str) -> None:
        self.count += 1
        event = RunEvent(index=self.count, at=_now(), kind=kind, text=text)
        with self.path.open("a") as file:
            file.write(event.model_dump_json() + "\n")
