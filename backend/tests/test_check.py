import json

from extraction_workspace import CONFIG, build

from app.extraction.check import run_check
from app.extraction.workspace import Workspace, load_json, save_json


def test_conflict_when_two_reads_disagree(ws: Workspace):
    build(ws)
    out = run_check(ws)
    assert "CONFLICT d002 ['fields.value']" in out
    assert "d001" not in out.split("CONFLICT")[1].split("\n")[0]
    report = load_json(ws.work / "check.json")
    assert [c["design"] for c in report["conflicts"]] == ["d002"]
    assert report["conflicts"][0]["image"] == "work/items/k3/front.png"


def test_count_mismatch_against_count_in_rules(ws: Workspace):
    build(ws, d002_values=(2, 2))
    out = run_check(ws)
    assert "CONFLICT" not in out
    assert "CHECK kind card: rules say 3, found 3" not in out
    cfg = json.loads(json.dumps(CONFIG))
    cfg["kinds"][0]["count_in_rules"] = 5
    save_json(ws.config_path, cfg)
    out = run_check(ws)
    assert "CHECK kind card: rules say 5, found 3 (files plus rules_items)" in out


def test_back_group_with_two_kinds(ws: Workspace):
    build(ws)
    out = run_check(ws)
    assert "CHECK back group b01 (identical backs) holds several kinds:" in out
    assert "card" in out and "tile" in out


def test_back_kinds_allows_the_mix(ws: Workspace):
    cfg = json.loads(json.dumps(CONFIG)) | {"back_kinds": {"b01": ["card", "tile"]}}
    build(ws, cfg)
    assert "back group b01" not in run_check(ws).replace("items per back group", "")


def test_override_settles_the_conflict(ws: Workspace):
    cfg = json.loads(json.dumps(CONFIG)) | {
        "overrides": {"d002": {"set": {"fields.value": 2}, "reason": "counted 2 pips"}}
    }
    build(ws, cfg)
    out = run_check(ws)
    assert "CONFLICT" not in out
    assert "overridden: 1" in out


def test_expect_distribution_and_count(ws: Workspace):
    cfg = json.loads(json.dumps(CONFIG)) | {
        "expect": [
            {
                "kind": "card",
                "where": {"title": "Gold"},
                "count": 4,
                "distribution": {"value": {"1": 2, "2": 2}},
            }
        ]
    }
    build(ws, cfg, d002_values=(2, 2))
    out = run_check(ws)
    assert "expected 4 items, found 3" in out
    assert "value expected {'1': 2, '2': 2}, found {'1': 2, '2': 1}" in out
