import asyncio
import json

import pytest
from fake_results import PROPOSAL, write_results

from app.extraction.agent import AgentResult
from app.extraction.reader import RecordedReader
from app.extraction.runs import RunBusyError, RunManager, RunNotFoundError, RunStatus
from app.settings import Settings


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path / "data", agent_model="a", reader_model="r", parallel_reads=2)


def reader():
    return RecordedReader(lambda *_: PROPOSAL)


async def good_agent(ws, settings, reader, limits, on_event):
    on_event("tool", "render_pdfs")
    on_event("text", "Done.")
    write_results(ws)
    return AgentResult("All done.", 0.25, is_error=False)


def test_run_goes_through_agent_and_proposal(settings):
    async def scenario():
        manager = RunManager(settings, reader(), good_agent)
        status = manager.start({"rules.pdf": b"%PDF-1.4"})
        assert status.state == "running"
        await manager.wait()
        return manager, status.id

    manager, run_id = asyncio.run(scenario())

    status = manager.get(run_id)
    assert status.state == "done"
    assert status.reply == "All done."
    assert status.agent_cost_usd == 0.25
    assert status.files == ["rules.pdf"]
    assert status.finished is not None
    assert "results/game_model_v1.json" in status.results
    assert "results/rules.md" in status.results
    assert (settings.runs_dir / run_id / "input" / "rules.pdf").exists()
    assert [e.kind for e in manager.events(run_id)] == ["tool", "text", "step"]
    assert [e.index for e in manager.events(run_id, after=1)] == [2, 3]
    assert manager.list()[0].id == run_id


def test_no_proposal_without_components(settings):
    async def agent(ws, settings, reader, limits, on_event):
        return AgentResult("Nothing to extract.", 0.1, is_error=False)

    async def scenario():
        manager = RunManager(settings, reader(), agent)
        run_id = manager.start({"a.png": b"x"}).id
        await manager.wait()
        return manager.get(run_id)

    status = asyncio.run(scenario())

    assert status.state == "done"
    assert status.results == []


def test_second_start_while_running_is_refused(settings):
    async def scenario():
        gate = asyncio.Event()

        async def slow_agent(ws, settings, reader, limits, on_event):
            await gate.wait()
            return AgentResult("ok", 0, is_error=False)

        manager = RunManager(settings, reader(), slow_agent)
        manager.start({"a.png": b"x"})
        with pytest.raises(RunBusyError):
            manager.start({"b.png": b"x"})
        gate.set()
        await manager.wait()
        # After the run ended a new one may start.
        manager.start({"c.png": b"x"})
        await manager.wait()

    asyncio.run(scenario())


def test_failed_agent_gives_failed_run(settings):
    async def agent(ws, settings, reader, limits, on_event):
        return AgentResult("credit balance too low", 0, is_error=True)

    async def scenario():
        manager = RunManager(settings, reader(), agent)
        run_id = manager.start({"a.png": b"x"}).id
        await manager.wait()
        return manager.get(run_id)

    status = asyncio.run(scenario())

    assert status.state == "failed"
    assert status.error == "credit balance too low"


def test_exception_in_agent_gives_failed_run(settings):
    async def agent(ws, settings, reader, limits, on_event):
        raise RuntimeError("boom")

    async def scenario():
        manager = RunManager(settings, reader(), agent)
        run_id = manager.start({"a.png": b"x"}).id
        await manager.wait()
        return manager.get(run_id)

    status = asyncio.run(scenario())

    assert status.state == "failed"
    assert "boom" in status.error


def test_cancel(settings):
    async def scenario():
        started = asyncio.Event()

        async def hanging_agent(ws, settings, reader, limits, on_event):
            started.set()
            await asyncio.sleep(60)

        manager = RunManager(settings, reader(), hanging_agent)
        run_id = manager.start({"a.png": b"x"}).id
        await started.wait()
        manager.cancel(run_id)
        await manager.wait()
        return manager.get(run_id)

    assert asyncio.run(scenario()).state == "cancelled"


def test_run_left_running_by_an_earlier_process_is_interrupted(settings):
    async def scenario():
        gate = asyncio.Event()

        async def agent(ws, settings, reader, limits, on_event):
            await gate.wait()
            return AgentResult("ok", 0, is_error=False)

        old = RunManager(settings, reader(), agent)
        run_id = old.start({"a.png": b"x"}).id
        assert json.loads((settings.runs_dir / run_id / "run.json").read_text())["state"] == (
            "running"
        )
        # A new backend process reads the same folder while nothing runs the old run.
        status = RunManager(settings, reader()).get(run_id)
        gate.set()
        await old.wait()
        return status

    status = asyncio.run(scenario())

    assert status.state == "interrupted"
    assert status.finished is not None


def test_unknown_run(settings):
    manager = RunManager(settings, reader())

    with pytest.raises(RunNotFoundError):
        manager.get("20260101-000000-abcd")
    with pytest.raises(RunNotFoundError):
        manager.get("../etc")


def test_status_roundtrip():
    assert RunStatus.model_validate_json(
        RunStatus(id="x", state="done", files=[], started="2026-01-01T00:00:00Z").model_dump_json()
    )
