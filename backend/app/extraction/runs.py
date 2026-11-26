"""Extraction runs: one run is one folder under `settings.runs_dir/<id>`.

    <run>/run.json       the `RunStatus`, saved on every change
    <run>/events.jsonl   one `RunEvent` per line: every tool call and text block of the agent
    <run>/input/ work/ results/   see `workspace.py`

A run does the extraction flow: the agent session, then `propose_model` when the agent made
`results/components.json`. When asked, the analysis follows in `<run>/analysis/`, or starts alone
on a copy of an earlier run's results. A run can wait at checkpoint A (after extraction) or B
(before the simulation). A waiting run frees the slot and survives a restart. One run at a time:
the machine is busy with reader calls during a run.
"""

import asyncio
import json
import logging
import re
import secrets
import shutil
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from ..analysis.session import (
    CHECKPOINT_FILES,
    UPSTREAM,
    AnalysisError,
    AnalysisResult,
    Steering,
    analyse_results,
    check_designer_numbers,
    resume_analysis,
)
from ..settings import Settings
from .agent import AgentResult, EventSink, run_agent
from .proposal import propose_model
from .queue import ReadLimits
from .reader import Reader, ReaderError
from .workspace import ExtractionError, Workspace, load_json, save_json

log = logging.getLogger(__name__)

REQUEST_FILE = "analysis_request.json"

RunState = Literal["running", "waiting", "done", "failed", "cancelled", "interrupted"]
Checkpoint = Literal["A", "B"]
RUN_ID = re.compile(r"^[0-9]{8}-[0-9]{6}-[0-9a-f]{4}$")

AgentFunction = Callable[
    [Workspace, Settings, Reader, ReadLimits, EventSink], Awaitable[AgentResult]
]

AnalysisFunction = Callable[
    [Path, Path, str, dict[str, Any] | None, dict[str, Any] | None, EventSink, bool],
    Awaitable[AnalysisResult],
]
ResumeFunction = Callable[[Path, str, str, Steering, EventSink], Awaitable[AnalysisResult]]


class RunBusyError(Exception):
    """A run is already running."""


class RunNotFoundError(Exception):
    pass


class RunNotWaitingError(Exception):
    """The run is not at a checkpoint."""


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
    verify: list[Checkpoint] = []
    """The checkpoints where this run waits for a person."""
    checkpoint: Checkpoint | None = None
    checkpoint_files: list[str] = []
    """What the person reviews at the checkpoint, relative to the run folder."""
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


@dataclass(frozen=True)
class CheckpointASteering:
    """Replaced extraction results."""

    rules: bytes | None = None
    components: bytes | None = None


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


def _load_request(ws: Workspace) -> AnalysisRequest:
    data = load_json(ws.root / REQUEST_FILE, {})
    return AnalysisRequest(data.get("timings"), data.get("focus"))


def _replace_results(ws: Workspace, steering: CheckpointASteering | None) -> None:
    if steering is None:
        return
    if steering.components is not None:
        try:
            if not isinstance(json.loads(steering.components), dict):
                raise ValueError
        except ValueError as e:
            raise AnalysisError("components.json must be a JSON object") from e
    if steering.rules is not None:
        try:
            if not steering.rules.decode().strip():
                raise ValueError
        except ValueError as e:
            raise AnalysisError("rules.md must be text and not empty") from e
        (ws.results / "rules.md").write_bytes(steering.rules)
    if steering.components is not None:
        (ws.results / "components.json").write_bytes(steering.components)


class RunManager:
    def __init__(
        self,
        settings: Settings,
        reader: Reader,
        agent: AgentFunction = run_agent,
        propose: Callable[[Workspace, Reader], Awaitable[object]] = propose_model,
        analyse: AnalysisFunction = analyse_results,
        resume: ResumeFunction = resume_analysis,
    ):
        self.settings = settings
        self.reader = reader
        self.agent = agent
        self.propose = propose
        self.analyse = analyse
        self.resume = resume
        self.limits = ReadLimits(parallel=settings.parallel_reads)
        self._task: asyncio.Task | None = None
        self._active_id: str | None = None

    # ------------------------------------------------------------ starting and stopping

    def start(
        self,
        files: dict[str, bytes],
        analysis: AnalysisRequest | None = None,
        verify: list[Checkpoint] | None = None,
    ) -> RunStatus:
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
            id=run_id,
            state="running",
            files=ws.uploaded_files(),
            started=_now(),
            activity="start",
            verify=verify or [],
        )
        self._launch(ws, status, analysis)
        return status

    def start_analysis(
        self,
        source_run: str,
        analysis: AnalysisRequest,
        verify: list[Checkpoint] | None = None,
    ) -> RunStatus:
        """Starts a new run that does only the analysis, on an earlier run's extraction results."""
        self._check_free()
        if verify and "A" in verify:
            raise AnalysisError("a run that does only the analysis has no checkpoint A")
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
            verify=verify or [],
        )
        self._launch(ws, status, analysis)
        return status

    def continue_run(
        self, run_id: str, steering: CheckpointASteering | Steering | None = None
    ) -> RunStatus:
        """Continues a waiting run. No steering approves; steering must fit the checkpoint."""
        status = self.get(run_id)
        if status.state != "waiting":
            raise RunNotWaitingError(f"run {run_id} is {status.state}")
        self._check_free()
        ws = Workspace(self._folder(run_id))
        if status.checkpoint == "A":
            if isinstance(steering, Steering):
                raise AnalysisError("checkpoint A takes a replaced rules.md or components.json")
            _replace_results(ws, steering)
            analysis = _load_request(ws)
            flow = partial(self._run_analysis, ws, status, analysis)
        else:
            if isinstance(steering, CheckpointASteering):
                raise AnalysisError("checkpoint B takes numbers, answers or a note, not files")
            steering = steering or Steering()
            check_designer_numbers(steering.timings, steering.focus)
            flow = partial(self._resume_analysis, ws, status, steering)
        status.state, status.checkpoint, status.checkpoint_files = "running", None, []
        status.finished = None
        self._save(ws, status)
        self._active_id = run_id
        self._task = asyncio.create_task(self._run(ws, status, flow))
        return status

    def _launch(self, ws: Workspace, status: RunStatus, analysis: AnalysisRequest | None) -> None:
        if analysis:
            save_json(
                ws.root / REQUEST_FILE, {"timings": analysis.timings, "focus": analysis.focus}
            )
        self._save(ws, status)
        self._active_id = status.id

        async def flow(on_event: EventSink) -> None:
            if status.phase == "extraction":
                await self._run_extraction(ws, status, on_event)
                if status.state != "running" or not analysis:
                    return
                if "A" in status.verify:
                    self._wait(ws, status, "A", ["results/rules.md", "results/components.json"])
                    on_event("checkpoint", "A")
                    return
            if analysis:
                await self._run_analysis(ws, status, analysis, on_event)

        self._task = asyncio.create_task(self._run(ws, status, flow))

    def _wait(
        self, ws: Workspace, status: RunStatus, checkpoint: Checkpoint, files: list[str]
    ) -> None:
        status.state, status.checkpoint, status.checkpoint_files = "waiting", checkpoint, files
        self._save(ws, status)

    def _check_free(self) -> None:
        if self._active_id is not None:
            raise RunBusyError(f"run {self._active_id} is still running")

    def cancel(self, run_id: str) -> RunStatus:
        """Stops a running run. Does nothing for a run that has ended."""
        status = self.get(run_id)
        if status.state == "waiting":
            status.state, status.checkpoint, status.checkpoint_files = "cancelled", None, []
            status.finished = _now()
            ws = Workspace(self._folder(run_id))
            self._save(ws, status)
            _EventLog(ws.root / "events.jsonl").add("end", "cancelled")
        elif self._active_id == run_id and self._task is not None:
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
        self,
        ws: Workspace,
        status: RunStatus,
        flow: Callable[[EventSink], Awaitable[None]],
    ) -> None:
        counter = _EventLog(ws.root / "events.jsonl")

        def on_event(kind: str, text: str) -> None:
            counter.add(kind, text)
            status.activity = f"{kind}: {text}"[:200]
            self._save(ws, status)

        try:
            await flow(on_event)
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
            if status.state != "waiting":
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
            "B" in status.verify,
        )
        self._after_session(ws, status, result, on_event)

    async def _resume_analysis(
        self, ws: Workspace, status: RunStatus, steering: Steering, on_event: EventSink
    ) -> None:
        if status.analysis_session_id is None:
            raise AnalysisError("the run has no analysis session to continue")
        on_event("phase", "analysis continues")
        result = await self.resume(
            ws.root / "analysis",
            self.settings.analysis_model,
            status.analysis_session_id,
            steering,
            on_event,
        )
        self._after_session(ws, status, result, on_event)

    def _after_session(
        self, ws: Workspace, status: RunStatus, result: AnalysisResult, on_event: EventSink
    ) -> None:
        status.reply = result.reply
        status.analysis_session_id = result.session_id
        status.analysis_cost_usd += result.cost_usd
        status.analysis_runlog = result.runlog
        status.analysis_validator = result.validator_exit
        if result.at_checkpoint:
            self._wait(ws, status, "B", [f"analysis/out/{name}" for name in CHECKPOINT_FILES])
            on_event("checkpoint", "B")
            return
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
        self.count = len(path.read_text().splitlines()) if path.exists() else 0

    def add(self, kind: str, text: str) -> None:
        self.count += 1
        event = RunEvent(index=self.count, at=_now(), kind=kind, text=text)
        with self.path.open("a") as file:
            file.write(event.model_dump_json() + "\n")
