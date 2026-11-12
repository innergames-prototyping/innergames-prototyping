import asyncio

import pytest
from PIL import Image

from app.extraction import rules
from app.extraction.models import ExtractionConfig
from app.extraction.queue import ReadLimits, run_reads
from app.extraction.reader import RecordedReader
from app.extraction.rules import (
    PROOF_SCHEMA,
    RegionTarget,
    read_rules,
    region_keys,
    region_reads,
    region_targets,
    rules_report,
)
from app.extraction.workspace import Workspace, save_json

CONFIG = {
    "game": {"title": "Test"},
    "rules_regions": [
        {"file": "rules.pdf", "page": 1, "box": [0, 0, 1, 0.5], "note": "two columns"}
    ],
}


@pytest.fixture
def tiny(ws: Workspace, monkeypatch) -> Workspace:
    """A rules page render and a config with one region; Tesseract is not installed."""
    save_json(ws.config_path, CONFIG)
    ws.page_image("rules", 1).parent.mkdir(parents=True)
    Image.new("RGB", (200, 300), "white").save(ws.page_image("rules", 1))
    monkeypatch.setattr(rules, "tesseract_installed", lambda: False)
    return ws


def recorded(texts, proof=None):
    """Transcriptions come from `texts` in order; every proofreading answers `proof`."""
    queue = iter(texts)

    def respond(images, prompt, schema):
        if schema == PROOF_SCHEMA:
            return {"misspelled": proof or []}
        return next(queue)

    return RecordedReader(respond)


def run(ws, reader, limits=None):
    cfg = ws.load_config()
    limits = limits or ReadLimits()
    targets = region_targets(ws, cfg, reader, limits)
    asyncio.run(run_reads(list(targets), limits.parallel))
    return targets


def proof_calls(reader):
    return [c for c in reader.calls if c.startswith("Proofread")]


def test_region_keys_follow_the_definition_of_the_region():
    cfg = ExtractionConfig.model_validate(CONFIG)
    moved = ExtractionConfig.model_validate(
        {"rules_regions": [{"file": "rules.pdf", "page": 1, "box": [0, 0, 1, 0.6]}]}
    )
    assert region_keys(cfg)[0] != region_keys(moved)[0]
    assert region_keys(cfg) == region_keys(cfg)


def test_two_identical_reads_then_proofreading_of_both_halves(tiny):
    reader = recorded(["Draw two cards."] * 5)
    (target,) = run(tiny, reader)
    assert len(reader.calls) - len(proof_calls(reader)) == 2
    assert len(proof_calls(reader)) == 4  # 2 halves x min_reads
    assert target.cost_usd == pytest.approx(0.006)
    assert "Note for this region: two columns" in reader.calls[0]


def test_a_majority_of_three_stops_the_reading(tiny):
    reader = recorded(["Draw two cards.", "Draw too cards.", "Draw two cards."])
    run(tiny, reader)
    assert len(reader.calls) - len(proof_calls(reader)) == 3
    assert len(proof_calls(reader)) == 4


def test_reads_go_on_to_max_reads_without_a_majority(tiny):
    texts = [f"Pay {n} gold." for n in range(1, 10)]
    reader = recorded(texts)
    run(tiny, reader, ReadLimits(min_reads=2, max_reads=4))
    assert len(reader.calls) - len(proof_calls(reader)) == 4
    assert len(proof_calls(reader)) == 4


def test_proofreading_is_not_repeated_on_a_second_run(tiny):
    run(tiny, recorded(["Draw two cards."] * 5))
    reader = recorded([])
    run(tiny, reader)
    assert reader.calls == []


def test_tesseract_agreeing_with_the_first_read_ends_the_region(tiny, monkeypatch):
    monkeypatch.setattr(rules, "tesseract_installed", lambda: True)
    monkeypatch.setattr(rules, "ocr_region", lambda ws, region: "# Draw two cards")
    reader = recorded(["# Draw two cards."])
    (target,) = run(tiny, reader)
    assert len(reader.calls) == 1
    assert target.ocr == "# Draw two cards"
    report = rules_report(tiny, tiny.load_config())
    assert "1 confirmed by Tesseract after one read" in report
    assert "Tesseract is not installed" not in report


def test_tesseract_disagreeing_with_the_first_read_asks_for_more_reads(tiny, monkeypatch):
    monkeypatch.setattr(rules, "tesseract_installed", lambda: True)
    monkeypatch.setattr(rules, "ocr_region", lambda ws, region: "Draw too cards")
    reader = recorded(["Draw two cards."] * 3)
    run(tiny, reader)
    assert len(reader.calls) - len(proof_calls(reader)) == 2


def test_a_failed_ocr_counts_as_no_text(tiny, monkeypatch):
    def broken(ws, region):
        raise OSError("tesseract crashed")

    monkeypatch.setattr(rules, "tesseract_installed", lambda: True)
    monkeypatch.setattr(rules, "ocr_region", broken)
    (target,) = run(tiny, recorded(["Draw two cards."] * 3))
    assert target.ocr == ""
    assert len(target.reads) == 2


def test_region_reads_are_stored_in_order(tiny):
    run(tiny, recorded(["one", "one"]))
    cfg = tiny.load_config()
    assert region_reads(tiny.work / "rules", region_keys(cfg)[0]) == ["one", "one"]


def test_a_target_is_settled_after_its_reads(tiny):
    (target,) = run(tiny, recorded(["Draw two cards."] * 2))
    assert isinstance(target, RegionTarget)
    assert target.next_reads() == []


def test_the_report_says_once_that_tesseract_is_missing(tiny):
    run(tiny, recorded(["Draw two cards."] * 2))
    report = rules_report(tiny, tiny.load_config())
    assert report.count("Tesseract is not installed") == 1
    assert (
        "1 regions transcribed; 0 confirmed by Tesseract after one read, 1 with all reads" in report
    )
    assert (tiny.work / "rules" / "region_00.txt").read_text() == "Draw two cards.\n"


def test_the_report_lists_conflicts_and_spelling_flags(tiny):
    reader = recorded(["Pay 3 gold.", "Pay 5 gold.", "Pay 7 gold.", "Pay 9 gold.", "Pay 1 gold."])
    run(tiny, reader)
    assert "NO MAJORITY after" in rules_report(tiny, tiny.load_config())

    spelling = recorded(["Receive two cards."] * 3, proof=[{"printed": "Recieve", "context": "x"}])
    run_dir = tiny.work / "rules"
    for p in (run_dir / "reads").glob("*"):
        p.unlink()
    run(tiny, spelling)
    report = rules_report(tiny, tiny.load_config())
    assert "SPELLING: proofreaders saw 'Recieve'" in report


def test_read_rules_runs_the_reads_and_ends_with_the_preview(tiny):
    reader = recorded(["Draw two cards."] * 2)
    text = asyncio.run(read_rules(tiny, reader, ReadLimits()))
    assert text.startswith("spent $0.006")
    assert "regions transcribed" in text
    assert "total cost so far" in text
