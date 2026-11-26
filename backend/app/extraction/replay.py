"""Replays a finished run from its saved status and events, at any speed.

The client keeps the clock and asks for the state at `elapsed_s` seconds into the recording.
Nothing runs again and no model is called. Files come from the normal files endpoint.
"""

from datetime import timedelta

from pydantic import BaseModel

from .runs import Checkpoint, RunEvent, RunState, RunStatus

ENDED: tuple[RunState, ...] = ("done", "failed", "cancelled", "interrupted")


class ReplayFrame(BaseModel):
    run_id: str
    elapsed_s: float
    duration_s: float
    ended: bool
    state: RunState
    phase: str
    checkpoint: Checkpoint | None
    activity: str
    events: list[RunEvent]
    """Every event up to `elapsed_s`. Each event's `at` is the original time."""


def frame(status: RunStatus, events: list[RunEvent], elapsed_s: float) -> ReplayFrame:
    """The run as it was `elapsed_s` seconds after it started."""
    if status.state not in ENDED or status.finished is None:
        raise ValueError(f"run {status.id} is {status.state}")
    duration = (status.finished - status.started).total_seconds()
    elapsed = min(max(elapsed_s, 0.0), duration)
    ended = elapsed >= duration
    cutoff = status.started + timedelta(seconds=elapsed)
    visible = events if ended else [event for event in events if event.at <= cutoff]

    phase = "analysis" if status.source_run else "extraction"
    checkpoint: Checkpoint | None = None
    activity = "start"
    for event in visible:
        activity = f"{event.kind}: {event.text}"[:200]
        if event.kind == "phase":
            phase, checkpoint = "analysis", None
        elif event.kind == "checkpoint":
            checkpoint = event.text
    return ReplayFrame(
        run_id=status.id,
        elapsed_s=elapsed,
        duration_s=duration,
        ended=ended,
        state=status.state if ended else "waiting" if checkpoint else "running",
        phase=status.phase if ended else phase,
        checkpoint=None if ended else checkpoint,
        activity=status.activity if ended else activity,
        events=visible,
    )
