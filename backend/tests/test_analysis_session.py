import asyncio
import json
import threading
from pathlib import Path

import pytest
from claude_agent_sdk import ResultMessage

from app.analysis import session
from app.analysis.session import AnalysisError, find_runlog, prepare, session_options, verify_kit


@pytest.fixture
def extraction(tmp_path: Path) -> tuple[Path, Path]:
    rules, components = tmp_path / "rules.md", tmp_path / "components.json"
    rules.write_text("# Rules")
    components.write_text("{}")
    return rules, components


def test_prepare_copies_the_kit_and_renames_the_extraction_results(tmp_path, extraction):
    folder = tmp_path / "analysis"
    prepare(folder, *extraction, timings={"schema": "timings_v1"}, focus={"schema": "focus_v1"})
    names = {p.name for p in folder.iterdir()}
    assert {f.name for f in verify_kit()} <= names
    assert {"01_rules.txt", "01_components.json", "01_timings.json", "01_focus.json"} <= names
    assert (folder / "01_rules.txt").read_text() == "# Rules"
    assert json.loads((folder / "01_focus.json").read_text())["schema"] == "focus_v1"


def test_prepare_leaves_out_designer_numbers_that_were_not_given(tmp_path, extraction):
    folder = tmp_path / "analysis"
    prepare(folder, *extraction)
    assert not (folder / "01_timings.json").exists()
    assert not (folder / "01_focus.json").exists()


def test_prepare_refuses_the_wrong_schema(tmp_path, extraction):
    with pytest.raises(AnalysisError, match="timings_v1"):
        prepare(tmp_path / "analysis", *extraction, timings={"schema": "other"})
    assert not (tmp_path / "analysis").exists()


def test_session_loads_nothing_from_the_user_setup(tmp_path):
    options = session_options(tmp_path, "claude-opus-5-5")
    assert options.setting_sources == []
    assert options.strict_mcp_config is True
    assert options.tools == ["Bash", "Read", "Write", "Edit"]
    assert options.system_prompt["preset"] == "claude_code"


def test_find_runlog_takes_the_last_line():
    assert find_runlog("RUNLOG: old\ntext\nRUNLOG: phases=9") == "RUNLOG: phases=9"
    assert find_runlog("no log") is None


def test_validator_does_not_block_the_event_loop(tmp_path, monkeypatch):
    (tmp_path / "out").mkdir()
    finished = threading.Event()

    async def fake_query(prompt, options):
        yield ResultMessage(
            subtype="success",
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id="sid",
            result="RUNLOG: phases=1",
        )

    def slow_validate(folder, runlog):
        finished.wait(2)
        return 0

    monkeypatch.setattr(session, "query", fake_query)
    monkeypatch.setattr(session, "validate", slow_validate)

    async def scenario():
        task = asyncio.create_task(session.run_session(tmp_path, "m"))
        await asyncio.sleep(0.05)
        assert not task.done()
        finished.set()
        return await task

    assert asyncio.run(scenario()).validator_exit == 0
