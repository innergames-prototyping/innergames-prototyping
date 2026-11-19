import json

import numpy as np
from PIL import Image, ImageDraw

from app.extraction.grouping import cluster, differs_small, group_designs, similar
from app.extraction.workspace import Workspace


def card(symbol: bool = False, colour: str = "navy", size: int = 15) -> Image.Image:
    """A 200 x 200 card; `symbol` adds one small black mark of `size` px."""
    img = Image.new("RGB", (200, 200), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, 190, 60], fill=colour)
    draw.rectangle([10, 90, 120, 180], fill="darkgreen")
    if symbol:
        draw.rectangle([150, 130, 150 + size, 130 + size], fill="black")
    return img


def add_item(ws: Workspace, key: str, front: Image.Image, back: Image.Image | None = None):
    folder = ws.item_dir(key)
    folder.mkdir(parents=True)
    front.save(folder / "front.png")
    if back is not None:
        back.save(folder / "back.png")


def write_items(ws: Workspace, keys: list[str]) -> None:
    (ws.work / "items.json").write_text(json.dumps([{"key": k} for k in keys]))


def test_identical_crops_group_and_changed_symbol_stays_apart(ws: Workspace):
    add_item(ws, "a1", card())
    add_item(ws, "a2", card())
    add_item(ws, "b1", card(symbol=True))
    add_item(ws, "c1", card(colour="firebrick"))
    write_items(ws, ["a1", "a2", "b1", "c1"])
    ws.update_config({})

    out = group_designs(ws)

    groups = json.loads((ws.work / "groups.json").read_text())
    assert groups["designs"] == {
        "d001": ["a1", "a2"],
        "d002": ["b1"],
        "d003": ["c1"],
    }
    assert groups["backs"] == {}
    assert "4 items -> 3 designs, 0 back groups" in out
    assert "back contact sheet: None" in out
    assert (ws.work / "contact" / "designs_1.png").exists()


def test_backs_group_loosely_and_separate_items_stay_alone(ws: Workspace):
    add_item(ws, "a1", card(), card(colour="gray"))
    add_item(ws, "a2", card(), card(symbol=True, colour="gray", size=8))
    add_item(ws, "a3", card())
    write_items(ws, ["a1", "a2", "a3"])
    ws.update_config(
        {"separate": ["a3"], "overrides": {"d001": {"set": {"title": "x"}, "reason": "r"}}}
    )

    out = group_designs(ws)

    groups = json.loads((ws.work / "groups.json").read_text())
    assert groups["designs"] == {"d001": ["a1", "a2"], "d002": ["a3"]}
    # A back with one small changed symbol is near-identical, which is enough for backs.
    assert groups["backs"] == {"b01": ["a1", "a2"]}
    assert "numbered afresh" in out
    assert (ws.work / "contact" / "backs.png").exists()


def test_similar_tolerates_a_shift_but_not_a_changed_block():
    base = np.asarray(card()).astype(np.int16)
    shifted = np.roll(base, 2, axis=1)
    changed = np.asarray(card(symbol=True)).astype(np.int16)

    assert similar(base, shifted, tol=0.05)[0]
    same, fraction = similar(base, changed)
    assert not same and fraction > 0


def test_differs_small_only_for_clear_differences():
    base = np.asarray(card().resize((25, 25))).astype(np.int16)
    other = np.asarray(card(colour="firebrick").resize((25, 25))).astype(np.int16)
    assert not differs_small(base, base)
    assert differs_small(base, other)
    assert differs_small(base, base[:10])  # sizes far apart


def test_cluster_keeps_first_match_order(ws: Workspace):
    paths = {}
    for key in ("x", "y", "z"):
        add_item(ws, key, card() if key != "y" else card(colour="firebrick"))
        paths[key] = ws.item_dir(key) / "front.png"
    assert cluster(paths) == [["x", "z"], ["y"]]
