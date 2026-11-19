"""Extraction runs: one run is one folder under `settings.runs_dir/<id>`.

    <run>/run.json       the `RunStatus`, saved on every change
    <run>/events.jsonl   one `RunEvent` per line: every tool call and text block of the agent
    <run>/input/ work/ results/   see `workspace.py`

A run does the whole flow: the agent session, then `propose_model` when the agent made
`results/components.json`. One run at a time: the machine is busy with reader calls during a run.
"""

import asyncio
import logging
import re
import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

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


class RunEvent(BaseModel):
    index: int
    """Starts at 1. `events(id, after=n)` returns the events with a higher index."""
    at: datetime
    kind: str
    text: str


def _now() -> datetime:
    return datetime.now(UTC)


class RunManager:
    def __init__(
        self,
        settings: Settings,
        reader: Reader,
        agent: AgentFunction = run_agent,
        propose: Callable[[Workspace, Reader], Awaitable[object]] = propose_model,
    ):
        self.settings = settings
        self.reader = reader
        self.agent = agent
        self.propose = propose
        self.limits = ReadLimits(parallel=settings.parallel_reads)
        self._task: asyncio.Task | None = None
        self._active_id: str | None = None

    # ------------------------------------------------------------ starting and stopping

    def start(self, files: dict[str, bytes]) -> RunStatus:
        """Saves the files in a new run folder and starts the run. Call it inside the event loop."""
        if self._active_id is not None:
            raise RunBusyError(f"run {self._active_id} is still running")
        if not files:
            raise ExtractionError("no files to extract")
        run_id = f"{_now():%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"
        ws = Workspace(self.settings.runs_dir / run_id).create()
        for name, data in files.items():
            (ws.input / Path(name).name).write_bytes(data)
        status = RunStatus(
            id=run_id, state="running", files=ws.uploaded_files(), started=_now(), activity="start"
        )
        self._save(ws, status)
        self._active_id = run_id
        self._task = asyncio.create_task(self._run(ws, status))
        return status

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

    def list(self) -> list[RunStatus]:
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

    async def _run(self, ws: Workspace, status: RunStatus) -> None:
        counter = _EventLog(ws.root / "events.jsonl")

        def on_event(kind: str, text: str) -> None:
            counter.add(kind, text)
            status.activity = f"{kind}: {text}"[:200]
            self._save(ws, status)

        try:
            await self._run_flow(ws, status, on_event)
        except asyncio.CancelledError:
            status.state = "cancelled"
            counter.add("end", "cancelled")
        except (ExtractionError, ReaderError) as e:
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

    async def _run_flow(self, ws: Workspace, status: RunStatus, on_event: EventSink) -> None:
        result = await self.agent(ws, self.settings, self.reader, self.limits, on_event)
        status.reply, status.agent_cost_usd = result.reply, result.cost_usd
        if result.is_error:
            status.state, status.error = "failed", result.reply or "the agent session failed"
            return
        if (ws.results / "components.json").exists():
            on_event("step", "propose_model")
            await self.propose(ws, self.reader)
        status.state = "done"

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
