import asyncio

import pytest
from PIL import Image

from app.extraction.orient import (
    TURN,
    image_id,
    orient_designs,
    orientation,
    orientation_report,
)
from app.extraction.queue import ReadLimits
from app.extraction.reader import RecordedReader
from app.extraction.workspace import Workspace, save_json


def read(direction):
    return {"output": {"text_direction": direction}}


@pytest.fixture
def tiny(ws: Workspace) -> Workspace:
    """Design d001 with k1 and k2 (row 0 of cards.pdf page 1), design d002 with k3 (row 1)."""
    keys = ["k1", "k2", "k3"]
    save_json(
        ws.work / "groups.json",
        {"designs": {"d001": ["k1", "k2"], "d002": ["k3"]}, "backs": {}},
    )
    save_json(
        ws.work / "items.json",
        [
            {"key": "k1", "file": "cards.pdf", "page": 1, "row": 0, "col": 0},
            {"key": "k2", "file": "cards.pdf", "page": 1, "row": 0, "col": 1},
            {"key": "k3", "file": "cards.pdf", "page": 1, "row": 1, "col": 0},
        ],
    )
    for key in keys:
        (ws.work / "items" / key).mkdir(parents=True)
        Image.new("RGB", (20, 20), "white").save(ws.work / "items" / key / "front.png")
    return ws


def test_orientation_is_the_sideways_direction_most_reads_see():
    assert orientation([read("bottom to top"), read("bottom to top"), read("upright")]) == (
        "bottom to top"
    )
    assert orientation([read("upright"), read("upright"), read("upside down")]) is None
    assert orientation([read("upside down"), read("upright")]) is None
    assert orientation([]) is None


def test_two_agreeing_reads_are_enough(tiny):
    reader = RecordedReader(lambda *_: {"text_direction": "upright"})
    text = asyncio.run(orient_designs(tiny, reader, ReadLimits()))
    assert len(reader.calls) == 4
    assert "All designs read upright" in text
    assert "spent $0.0040" in text
    assert (tiny.work / "orient" / "d001" / "01.json").exists()


def test_a_third_read_settles_a_difference(tiny):
    save_json(tiny.work / "groups.json", {"designs": {"d001": ["k1", "k2"]}, "backs": {}})
    answers = iter(["upright", "upside down", "upright"])
    reader = RecordedReader(lambda *_: {"text_direction": next(answers)})
    text = asyncio.run(orient_designs(tiny, reader, ReadLimits()))
    assert len(reader.calls) == 3
    assert "All designs read upright" in text


def test_disagreement_after_three_reads_is_reported_as_unsure(tiny):
    save_json(tiny.work / "groups.json", {"designs": {"d001": ["k1", "k2"]}, "backs": {}})
    answers = iter(["upright", "upside down", "no text"] * 4)
    reader = RecordedReader(lambda *_: {"text_direction": next(answers)})
    text = asyncio.run(orient_designs(tiny, reader, ReadLimits()))
    assert "UNSURE" in text


def test_a_sideways_design_is_reported_with_its_turn(tiny):
    reader = RecordedReader(lambda *_: {"text_direction": "bottom to top"})
    text = asyncio.run(orient_designs(tiny, reader, ReadLimits()))
    assert (
        "ORIENTATION cards.pdf page 1: readers see the text running bottom to top on 3 items"
        in text
    )
    assert "r0 r1" in text
    assert "90 degrees clockwise" in text


def test_reads_of_a_changed_crop_are_not_reused(tiny):
    reader = RecordedReader(lambda *_: {"text_direction": "upright"})
    asyncio.run(orient_designs(tiny, reader, ReadLimits()))
    first = len(reader.calls)
    asyncio.run(orient_designs(tiny, reader, ReadLimits()))
    assert len(reader.calls) == first  # nothing changed: no new reads
    Image.new("RGB", (30, 30), "black").save(tiny.work / "items" / "k3" / "front.png")
    asyncio.run(orient_designs(tiny, reader, ReadLimits()))
    assert len(reader.calls) == first + 2  # only d002 is read again


def test_image_id_depends_on_the_crop(tiny):
    before = image_id(tiny, "k1")
    Image.new("RGB", (30, 30), "black").save(tiny.work / "items" / "k1" / "front.png")
    assert image_id(tiny, "k1") != before


def test_orientation_report_lists_cells_or_whole_rows(tiny):
    designs = {
        "d001": {"members": ["k1", "k2"], "orientation": "upside down", "kind": "card"},
        "d002": {"members": ["k3"], "orientation": None},
    }
    lines = orientation_report(tiny, designs)
    assert len(lines) == 1
    assert "on 2 items: r0." in lines[0]
    assert f"{TURN['upside down']} degrees" in lines[0]
    assert "Read as: card." in lines[0]
    designs["d001"]["members"] = ["k1"]
    assert "r0c0" in orientation_report(tiny, designs)[0]


def test_orientation_report_names_items_from_image_files(ws):
    save_json(
        ws.work / "items.json", [{"key": "a_png", "label": "a.png", "file": "a.png", "page": 1}]
    )
    designs = {"d001": {"members": ["a_png"], "orientation": "top to bottom"}}
    (line,) = orientation_report(ws, designs)
    assert line.startswith("ORIENTATION item files:")
    assert "a.png" in line and "270 degrees" in line
