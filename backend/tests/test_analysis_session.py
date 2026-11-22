import json
from pathlib import Path

import pytest

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
