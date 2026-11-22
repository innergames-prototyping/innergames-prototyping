import asyncio
import json

import pytest
from fake_results import PROPOSAL, write_results
from fastapi.testclient import TestClient

from app.analysis.session import (
    AnalysisError,
    AnalysisResult,
    Steering,
    apply_steering,
    is_at_checkpoint,
)
from app.extraction.agent import AgentResult
from app.extraction.reader import RecordedReader
from app.extraction.runs import (
    AnalysisRequest,
    CheckpointASteering,
    RunBusyError,
    RunManager,
    RunNotWaitingError,
)
from app.main import create_app
from app.settings import Settings


async def agent(ws, settings, reader, limits, on_event):
    write_results(ws)
    return AgentResult("Extracted.", 0.5, is_error=False)


class FakeAnalysis:
    def __init__(self):
        self.started, self.resumed = [], []

    async def analyse(self, results, folder, model, timings, focus, on_event, stop_at_b=False):
        self.started.append(((results / "rules.md").read_text(), stop_at_b))
        if stop_at_b:
            return AnalysisResult("sid", "CHECKPOINT B", 1.0, False, None, None, True)
        return AnalysisResult("sid", "Done", 3.0, False, "RUNLOG: x", 0)

    async def resume(self, folder, model, session_id, steering, on_event):
        self.resumed.append((session_id, steering))
        return AnalysisResult(session_id, "Done", 2.0, False, "RUNLOG: x", 0)


def manager(tmp_path, fake):
    settings = Settings(tmp_path / "data", "a", "r", 2)
    return RunManager(
        settings,
        RecordedReader(lambda *_: PROPOSAL),
        agent,
        analyse=fake.analyse,
        resume=fake.resume,
    )


def test_run_without_verify_does_not_wait(tmp_path):
    fake = FakeAnalysis()
    runs = manager(tmp_path, fake)

    async def scenario():
        run_id = runs.start({"a.png": b"x"}, AnalysisRequest()).id
        await runs.wait()
        return runs.get(run_id)

    assert asyncio.run(scenario()).state == "done"
    assert fake.started[0][1] is False


def test_run_waits_at_a_and_b_then_finishes_with_steering(tmp_path):
    fake = FakeAnalysis()
    runs = manager(tmp_path, fake)
    steering = Steering(answers=("Yes",), note="Use the short rule")

    async def scenario():
        run_id = runs.start({"a.png": b"x"}, AnalysisRequest(), ["A", "B"]).id
        await runs.wait()
        at_a = runs.get(run_id)
        assert fake.started == []
        runs.continue_run(run_id, CheckpointASteering(rules=b"Corrected rules"))
        await runs.wait()
        at_b = runs.get(run_id)
        runs.continue_run(run_id, steering)
        await runs.wait()
        return at_a, at_b, runs.get(run_id), runs.events(run_id)

    at_a, at_b, end, events = asyncio.run(scenario())

    assert (at_a.state, at_a.checkpoint) == ("waiting", "A")
    assert at_a.finished is None
    assert (at_b.state, at_b.checkpoint) == ("waiting", "B")
    assert "analysis/out/D03_duration_table.json" in at_b.checkpoint_files
    assert fake.started == [("Corrected rules", True)]
    assert fake.resumed == [("sid", steering)]
    assert (end.state, end.checkpoint, end.analysis_cost_usd) == ("done", None, 3.0)
    assert [e.index for e in events] == list(range(1, len(events) + 1))


def test_waiting_run_frees_the_slot_and_survives_a_restart(tmp_path):
    fake = FakeAnalysis()
    runs = manager(tmp_path, fake)

    async def scenario():
        waiting = runs.start({"a.png": b"x"}, AnalysisRequest(), ["A"]).id
        await runs.wait()
        other = runs.start({"b.png": b"x"})
        with pytest.raises(RunBusyError):
            runs.continue_run(waiting)
        await runs.wait()
        restarted = manager(tmp_path, fake)
        assert restarted.get(other.id).state == "done"
        assert restarted.get(waiting).state == "waiting"
        restarted.continue_run(waiting)
        await restarted.wait()
        return restarted.get(waiting)

    assert asyncio.run(scenario()).state == "done"


def test_waiting_run_can_be_cancelled_and_not_continued(tmp_path):
    runs = manager(tmp_path, FakeAnalysis())

    async def scenario():
        run_id = runs.start({"a.png": b"x"}, AnalysisRequest(), ["A"]).id
        await runs.wait()
        runs.cancel(run_id)
        with pytest.raises(RunNotWaitingError):
            runs.continue_run(run_id)
        return runs.get(run_id)

    status = asyncio.run(scenario())
    assert (status.state, status.checkpoint) == ("cancelled", None)


@pytest.mark.parametrize("steering", [Steering(note="x"), CheckpointASteering(components=b"[]")])
def test_wrong_steering_at_a_leaves_the_run_waiting(tmp_path, steering):
    runs = manager(tmp_path, FakeAnalysis())

    async def scenario():
        run_id = runs.start({"a.png": b"x"}, AnalysisRequest(), ["A"]).id
        await runs.wait()
        with pytest.raises(AnalysisError):
            runs.continue_run(run_id, steering)
        return runs.get(run_id)

    assert asyncio.run(scenario()).state == "waiting"


def test_analysis_alone_has_no_checkpoint_a(tmp_path):
    runs = manager(tmp_path, FakeAnalysis())

    async def scenario():
        first = runs.start({"a.png": b"x"}).id
        await runs.wait()
        with pytest.raises(AnalysisError, match="checkpoint A"):
            runs.start_analysis(first, AnalysisRequest(), ["A"])

    asyncio.run(scenario())


def test_steering_merges_timings_and_builds_the_message(tmp_path):
    (tmp_path / "01_timings.json").write_text(
        json.dumps(
            {"schema": "timings_v1", "categories": {"move": {"min_s": 5}}, "sessions": [{"a": 1}]}
        )
    )
    steering = Steering(
        timings={
            "schema": "timings_v1",
            "categories": {"setup": {"min_s": 60}},
            "sessions": [{"b": 2}],
        },
        answers=("Doors stay open",),
        note="Check the boss",
    )
    message = apply_steering(tmp_path, steering)
    merged = json.loads((tmp_path / "01_timings.json").read_text())
    assert set(merged["categories"]) == {"move", "setup"}
    assert len(merged["sessions"]) == 2
    assert "Doors stay open" in message and "Check the boss" in message


def test_checkpoint_needs_the_marker_and_the_files(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    assert not is_at_checkpoint(tmp_path, "CHECKPOINT B", None)
    (out / "D01_rules_dossier.md").write_text("x")
    (out / "D03_duration_table.json").write_text("{}")
    assert is_at_checkpoint(tmp_path, "Ready.\nCHECKPOINT B", None)
    assert not is_at_checkpoint(tmp_path, "CHECKPOINT B", "RUNLOG: x")
    assert not is_at_checkpoint(tmp_path, "Ready.", None)


def test_api_continue_at_each_checkpoint(tmp_path):
    fake = FakeAnalysis()
    runs = manager(tmp_path, fake)

    def wait_for(client, run_id, state):
        for _ in range(200):
            status = client.get(f"/api/runs/{run_id}").json()
            if status["state"] == state:
                return status
            asyncio.run(asyncio.sleep(0.01))
        raise AssertionError(status)

    with TestClient(create_app(runs.settings, runs)) as client:
        response = client.post(
            "/api/runs",
            files=[("files", ("a.png", b"x"))],
            data={"verify": ["A", "B"]},
        )
        run_id = response.json()["id"]
        assert wait_for(client, run_id, "waiting")["checkpoint"] == "A"
        assert client.post(f"/api/runs/{run_id}/continue", json={"note": "x"}).status_code == 422
        response = client.post(
            f"/api/runs/{run_id}/continue", files={"rules": ("rules.md", b"New rules")}
        )
        assert response.status_code == 200
        for _ in range(200):
            status = client.get(f"/api/runs/{run_id}").json()
            if status["checkpoint"] == "B":
                break
            asyncio.run(asyncio.sleep(0.01))
        response = client.post(f"/api/runs/{run_id}/continue", json={"note": "Go"})
        assert response.status_code == 200
        wait_for(client, run_id, "done")
        assert client.post(f"/api/runs/{run_id}/continue").status_code == 409
    assert fake.started == [("New rules", True)]
    assert fake.resumed[0][1].note == "Go"
