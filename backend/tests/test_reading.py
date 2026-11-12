import asyncio

import pytest
from PIL import Image

from app.extraction import rules
from app.extraction.orient import ORIENTATION_NEXT
from app.extraction.queue import ReadLimits
from app.extraction.reader import RecordedReader
from app.extraction.reading import read_all
from app.extraction.rules import PROOF_SCHEMA
from app.extraction.workspace import Workspace, save_json

CONFIG = {
    "game": {"title": "Test"},
    "kinds": [
        {
            "id": "card",
            "name": "Card",
            "description": "A card with gold.",
            "fields": [{"name": "gold", "type": "integer", "description": "Coins."}],
        }
    ],
    "rules_regions": [{"file": "rules.pdf", "page": 1, "box": [0, 0, 1, 0.5]}],
}


def card(direction="upright"):
    return {
        "observations": "",
        "text_direction": direction,
        "kind": "card",
        "title": "Axe",
        "fields": {"card": {"gold": 2}},
        "mismatch": "none",
        "text": None,
        "misspelled": [],
        "unreadable": "",
    }


def respond_with(direction="upright"):
    def respond(images, prompt, schema):
        if schema == PROOF_SCHEMA:
            return {"misspelled": []}
        if schema is None:
            return "Draw two cards."
        return card(direction)

    return RecordedReader(respond)


@pytest.fixture
def tiny(ws: Workspace, monkeypatch) -> Workspace:
    save_json(ws.config_path, CONFIG)
    save_json(ws.work / "groups.json", {"designs": {"d001": ["k1", "k2"]}, "backs": {}})
    save_json(
        ws.work / "items.json",
        [
            {"key": k, "file": "c.pdf", "page": 1, "row": 0, "col": i}
            for i, k in enumerate(["k1", "k2"])
        ],
    )
    for key in ("k1", "k2"):
        (ws.work / "items" / key).mkdir(parents=True)
        Image.new("RGB", (20, 20), "white").save(ws.work / "items" / key / "front.png")
    ws.page_image("rules", 1).parent.mkdir(parents=True)
    Image.new("RGB", (200, 300), "white").save(ws.page_image("rules", 1))
    monkeypatch.setattr(rules, "tesseract_installed", lambda: False)
    return ws


def test_read_all_reads_designs_and_rules_then_checks(tiny):
    reader = respond_with()
    text = asyncio.run(read_all(tiny, reader, ReadLimits()))
    assert text.startswith("reading with 12 parallel readers\nspent $")
    assert "1 regions transcribed" in text
    assert ORIENTATION_NEXT not in text
    assert (tiny.work / "check.json").exists()
    assert len(list((tiny.work / "reads" / "d001").glob("*.json"))) == 2


def test_the_designs_filter_skips_the_rules(tiny):
    reader = respond_with()
    text = asyncio.run(read_all(tiny, reader, ReadLimits(), designs=["d001"]))
    assert "regions transcribed" not in text
    assert not (tiny.work / "rules").exists()


def test_sideways_designs_end_the_step_with_what_to_turn(tiny):
    reader = respond_with("bottom to top")
    text = asyncio.run(read_all(tiny, reader, ReadLimits()))
    assert "ORIENTATION c.pdf page 1" in text
    assert text.endswith(ORIENTATION_NEXT)
    assert not (tiny.work / "check.json").exists()
