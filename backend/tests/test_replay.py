from datetime import UTC, datetime, timedelta

import pytest
from fake_results import PROPOSAL
from fastapi.testclient import TestClient

from app.extraction.reader import RecordedReader
from app.extraction.replay import frame
from app.extraction.runs import RunEvent, RunManager, RunStatus
from app.main import create_app
from app.settings import Settings

START = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)


def event(index, seconds, kind, text):
    return RunEvent(index=index, at=START + timedelta(seconds=seconds), kind=kind, text=text)


EVENTS = [
    event(1, 10, "tool", "render_pdfs"),
    event(2, 20, "phase", "analysis"),
    event(3, 30, "checkpoint", "B"),
    event(4, 40, "phase", "analysis continues"),
    event(5, 50, "text", "Done"),
]


def status(state="done"):
    return RunStatus(
        id="20261122-120000-abcd",
        state=state,
        files=[],
        started=START,
        finished=START + timedelta(seconds=60),
        phase="analysis",
        activity="text: Done",
    )


@pytest.mark.parametrize(
    "elapsed,count,state,phase,checkpoint",
    [
        (0, 0, "running", "extraction", None),
        (10, 1, "running", "extraction", None),
        (25, 2, "running", "analysis", None),
        (35, 3, "waiting", "analysis", "B"),
        (45, 4, "running", "analysis", None),
        (60, 5, "done", "analysis", None),
        (999, 5, "done", "analysis", None),
    ],
)
def test_frame_shows_the_run_at_that_moment(elapsed, count, state, phase, checkpoint):
    result = frame(status(), EVENTS, elapsed)
    assert len(result.events) == count
    assert (result.state, result.phase, result.checkpoint) == (state, phase, checkpoint)
    assert result.duration_s == 60


@pytest.mark.parametrize("state", ["running", "waiting"])
def test_only_a_finished_run_can_be_replayed(state):
    with pytest.raises(ValueError):
        frame(status(state), EVENTS, 0)


def test_api_serves_a_frame_of_a_saved_run(tmp_path):
    settings = Settings(tmp_path / "data", "a", "r", 2)
    runs = RunManager(settings, RecordedReader(lambda *_: PROPOSAL))
    folder = settings.runs_dir / status().id
    folder.mkdir(parents=True)
    (folder / "run.json").write_text(status().model_dump_json())
    (folder / "events.jsonl").write_text("".join(e.model_dump_json() + "\n" for e in EVENTS))
    with TestClient(create_app(settings, runs)) as client:
        body = client.get(f"/api/runs/{status().id}/replay", params={"elapsed_s": 35}).json()
        assert (body["state"], body["checkpoint"], len(body["events"])) == ("waiting", "B", 3)
        assert client.get("/api/runs/20261122-120000-ffff/replay").status_code == 404
