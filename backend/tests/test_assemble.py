import json

import pytest
from extraction_workspace import CONFIG, build, write_rules

from app.extraction.assemble import assemble
from app.extraction.workspace import ExtractionError, Workspace, load_json


def config_with(**changes):
    return json.loads(json.dumps(CONFIG)) | changes


def settled(ws: Workspace, **changes) -> None:
    """A run with no open conflicts, as it is after the agent worked through `check`."""
    build(ws, config_with(**changes), d002_values=(2, 2))
    write_rules(ws)


def test_writes_all_four_files(ws: Workspace):
    settled(
        ws, rules_items=[{"kind": "tile", "count": 2, "source": {"file": "rules.pdf", "page": 1}}]
    )
    out = assemble(ws)
    assert "VALID" in out and "INVALID" not in out
    assert (ws.results / "rules.md").read_text() == "# Rules\nPlay cards.\n"
    assert (ws.work / "review.html").exists()
    record = load_json(ws.work / "components.json")
    assert record["spec_version"] == "extraction-1.0"
    assert len(record["items"]) == 6
    from_rules = [i for i in record["items"] if i["from_rules"]]
    assert [i["kind"] for i in from_rules] == ["tile", "tile"]
    assert from_rules[0]["id"] == "rules#p1_tile_01"
    assert {i["confidence"] for i in record["items"] if not i["from_rules"]} <= {"high", "medium"}


def test_export_merges_identical_items_with_a_count(ws: Workspace):
    settled(
        ws, rules_items=[{"kind": "tile", "count": 2, "source": {"file": "rules.pdf", "page": 1}}]
    )
    assemble(ws)
    exported = load_json(ws.results / "components.json")
    by_kind = {(c["kind"], json.dumps(c.get("fields"))): c for c in exported["components"]}
    assert by_kind[("card", '{"value": 1}')]["count"] == 2
    assert by_kind[("card", '{"value": 2}')]["count"] == 1
    # the two tiles named by the rules join the tile shown in the files
    assert by_kind[("tile", "null")]["count"] == 3
    assert "source" not in by_kind[("tile", "null")]
    assert [k["id"] for k in exported["component_kinds"]] == ["card", "tile"]


def test_refuses_open_conflicts_unless_forced(ws: Workspace):
    # the titles of the reads differ: unresolved, but the value is settled
    build(ws, d002_values=(2, 2), d002_titles=("Gold", "Silver"))
    write_rules(ws)
    with pytest.raises(ExtractionError, match="unresolved or sideways designs"):
        assemble(ws)
    assemble(ws, force=True)
    items = load_json(ws.work / "components.json")["items"]
    assert {i["id"]: i["confidence"] for i in items}["cards#p1_r1_c3"] == "low"


def test_refuses_a_design_with_no_value_for_its_kind_even_when_forced(ws: Workspace):
    build(ws)
    write_rules(ws)
    with pytest.raises(ExtractionError, match="no value for any field"):
        assemble(ws, force=True)


def test_refuses_a_rules_fix_that_does_not_match(ws: Workspace):
    settled(ws, rules_fixes=[{"find": "no such text", "replace": "x"}])
    with pytest.raises(ExtractionError, match="rules_fixes"):
        assemble(ws)


def test_rules_fix_is_applied(ws: Workspace):
    settled(ws, rules_fixes=[{"find": "Play", "replace": "Draw"}])
    assemble(ws)
    assert (ws.results / "rules.md").read_text() == "# Rules\nDraw cards.\n"


def test_refuses_without_a_game(ws: Workspace):
    settled(ws, game=None)
    with pytest.raises(ExtractionError, match="update_config"):
        assemble(ws)


def test_refuses_when_regions_changed_since_the_rules_read(ws: Workspace):
    settled(ws)
    regions = CONFIG["rules_regions"] + [{"file": "rules.pdf", "page": 1, "box": [0, 0, 0.5, 0.5]}]
    ws.update_config({"rules_regions": regions})
    with pytest.raises(ExtractionError, match="rules_regions changed"):
        assemble(ws)
