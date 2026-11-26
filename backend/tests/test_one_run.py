import asyncio
import json

import pytest
from fake_results import PROPOSAL, write_results
from fastapi.testclient import TestClient

from app.analysis.session import AnalysisError, AnalysisResult
from app.extraction.agent import AgentResult
from app.extraction.reader import RecordedReader
from app.extraction.runs import AnalysisRequest, RunManager
from app.main import create_app
from app.settings import Settings


async def agent(ws, settings, reader, limits, on_event):
    write_results(ws)
    return AgentResult("Extracted.", 0.5, is_error=False)


def analyser(calls, validator=0, is_error=False):
    async def analyse(results, folder, model, timings, focus, on_event, stop_at_b=False):
        calls.append((results, folder, model, timings, focus))
        on_event("text", "analysing")
        return AnalysisResult("sid", "Analysed.", 2.0, is_error, "RUNLOG: phases=9", validator)

    return analyse


def manager(tmp_path, analyse):
    settings = Settings(tmp_path / "data", "a", "r", 2)
    return RunManager(settings, RecordedReader(lambda *_: PROPOSAL), agent, analyse=analyse)


def run(runs, start):
    async def scenario():
        run_id = start().id
        await runs.wait()
        return runs.get(run_id)

    return asyncio.run(scenario())


def test_one_run_does_extraction_then_analysis(tmp_path):
    calls = []
    runs = manager(tmp_path, analyser(calls))
    timings = {"schema": "timings_v1"}
    status = run(runs, lambda: runs.start({"a.png": b"x"}, AnalysisRequest(timings=timings)))
    assert (status.state, status.phase) == ("done", "analysis")
    assert status.analysis_session_id == "sid"
    assert status.analysis_validator == 0
    assert calls[0][1].name == "analysis"
    assert calls[0][3] == timings


def test_extraction_alone_does_not_start_the_analysis(tmp_path):
    calls = []
    runs = manager(tmp_path, analyser(calls))
    status = run(runs, lambda: runs.start({"a.png": b"x"}))
    assert (status.state, status.phase) == ("done", "extraction")
    assert calls == []


@pytest.mark.parametrize("validator,is_error", [(1, False), (2, False), (None, False), (0, True)])
def test_analysis_without_a_passing_validator_fails_the_run(tmp_path, validator, is_error):
    runs = manager(tmp_path, analyser([], validator, is_error))
    status = run(runs, lambda: runs.start({"a.png": b"x"}, AnalysisRequest()))
    assert status.state == "failed"
    assert status.analysis_cost_usd == 2.0


def test_analysis_alone_uses_a_copy_of_the_earlier_results(tmp_path):
    calls = []
    runs = manager(tmp_path, analyser(calls))
    first = run(runs, lambda: runs.start({"a.png": b"x"}))
    second = run(runs, lambda: runs.start_analysis(first.id, AnalysisRequest()))
    assert (second.state, second.source_run) == ("done", first.id)
    assert second.id != first.id
    assert calls[0][0] == runs.workspace(second.id).results
    assert (calls[0][0] / "rules.md").is_file()


def test_analysis_alone_needs_extraction_results(tmp_path):
    async def empty(ws, settings, reader, limits, on_event):
        return AgentResult("Nothing.", 0, is_error=False)

    runs = manager(tmp_path, analyser([]))
    runs.agent = empty
    first = run(runs, lambda: runs.start({"a.png": b"x"}))
    with pytest.raises(AnalysisError, match="rules.md"):
        runs.start_analysis(first.id, AnalysisRequest())


def test_api_refuses_wrong_designer_numbers_with_422(tmp_path):
    runs = manager(tmp_path, analyser([]))
    with TestClient(create_app(runs.settings, runs)) as client:
        for timings in ('{"schema": "other"}', "not json", "[]"):
            response = client.post(
                "/api/runs",
                files=[("files", ("a.png", b"x"))],
                data={"timings": timings},
            )
            assert response.status_code == 422
        assert client.get("/api/runs").json() == []


def test_api_starts_one_run_and_reports_it(tmp_path):
    calls = []
    runs = manager(tmp_path, analyser(calls))
    focus = {"schema": "focus_v1", "focus_items": []}
    with TestClient(create_app(runs.settings, runs)) as client:
        response = client.post(
            "/api/runs",
            files=[("files", ("a.png", b"x"))],
            data={"focus": json.dumps(focus)},
        )
        assert response.status_code == 201
        run_id = response.json()["id"]
        for _ in range(100):
            status = client.get(f"/api/runs/{run_id}").json()
            if status["state"] != "running":
                break
            asyncio.run(asyncio.sleep(0.02))
    assert status["state"] == "done"
    assert calls[0][4] == focus
