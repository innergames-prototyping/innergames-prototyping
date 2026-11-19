import json

import pytest
from PIL import Image, ImageDraw

from app.extraction.layout import assign_rows, back_position, crop_items, item_key
from app.extraction.workspace import ExtractionError, Workspace

PAGE = (900, 600)
RECT = (150, 100)
XS = (100, 350, 600)
YS = (100, 350)


def save_page(ws: Workspace, stem: str, page: int, rects: list[tuple[int, int]]) -> None:
    """A white page with a black rectangle (with a white hole) at every (x, y)."""
    img = Image.new("RGB", PAGE, "white")
    draw = ImageDraw.Draw(img)
    for x, y in rects:
        draw.rectangle([x, y, x + RECT[0], y + RECT[1]], fill="black")
        draw.rectangle([x + 30, y + 30, x + 60, y + 60], fill="white")
    path = ws.page_image(stem, page)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def six_cards() -> list[tuple[int, int]]:
    return [(x, y) for y in YS for x in XS]


def manifest(ws: Workspace) -> dict[str, dict]:
    return {e["key"]: e for e in json.loads((ws.work / "items.json").read_text())}


def test_segment_finds_rows_and_columns_with_keys(ws: Workspace):
    save_page(ws, "cards", 1, six_cards())
    ws.update_config({"layouts": [{"file": "cards.pdf", "page": 1}]})

    out = crop_items(ws)

    items = manifest(ws)
    assert sorted(items) == [item_key("cards", 1, r, c) for r in range(2) for c in range(3)]
    assert items["cards_p1_r01_c02"]["box"][0] < 600 < items["cards_p1_r01_c02"]["box"][2]
    assert (ws.item_dir("cards_p1_r00_c00") / "front.png").exists()
    assert "cards p1: 6 items in 2 rows {0: 3, 1: 3}" in out
    assert out.splitlines()[-1] == "6 items"
    assert (ws.work / "preview" / "items_cards_p1.png").exists()
    assert (ws.work / "contact" / "cards_p1.png").exists()
    assert "size outliers" not in out


def test_back_is_cut_at_the_mirrored_position(ws: Workspace):
    save_page(ws, "cards", 1, six_cards())
    # Only the mirror of r0c0 (x 100..250 on a page 900 wide) has a back.
    save_page(ws, "cards", 2, [(PAGE[0] - 100 - RECT[0], 100)])
    ws.update_config({"layouts": [{"file": "cards.pdf", "page": 1, "back_page": 2}]})

    crop_items(ws)

    items = manifest(ws)
    assert (ws.item_dir("cards_p1_r00_c00") / "back.png").exists()
    assert not (ws.item_dir("cards_p1_r00_c01") / "back.png").exists()
    first = items["cards_p1_r00_c00"]
    assert (first["back_page"], first["back_row"], first["back_col"]) == (2, 0, 2)


def test_back_position_mirrors():
    row_len = {0: 3}
    box = (100, 100, 250, 200)
    assert back_position(box, None, 0, 0, row_len, 1, (900, 600), "horizontal") == (
        (650, 100, 800, 200),
        None,
        0,
        2,
    )
    assert back_position(box, None, 0, 0, row_len, 2, (900, 600), "vertical") == (
        (100, 400, 250, 500),
        None,
        1,
        0,
    )
    assert back_position(box, None, 0, 0, row_len, 1, (900, 600), "none") == (box, None, 0, 0)


def test_skip_and_rotate(ws: Workspace):
    save_page(ws, "cards", 1, six_cards())
    ws.update_config(
        {
            "layouts": [
                {
                    "file": "cards.pdf",
                    "page": 1,
                    "skip": ["r0c1"],
                    "rotate_items": {"r1": 90},
                }
            ]
        }
    )

    crop_items(ws)

    items = manifest(ws)
    assert len(items) == 5
    assert "cards_p1_r00_c01" not in items
    assert items["cards_p1_r01_c00"]["rotate"] == 90
    assert items["cards_p1_r00_c00"]["rotate"] == 0
    upright = Image.open(ws.item_dir("cards_p1_r00_c00") / "front.png")
    turned = Image.open(ws.item_dir("cards_p1_r01_c00") / "front.png")
    assert turned.size == upright.size[::-1]


def test_grid_with_box_rows_and_cols(ws: Workspace):
    save_page(ws, "cards", 1, [(100, 100), (500, 100), (100, 350), (500, 350)])
    ws.update_config(
        {
            "layouts": [
                {
                    "method": "grid",
                    "file": "cards.pdf",
                    "page": 1,
                    "box": [0, 0, 1, 1],
                    "rows": 2,
                    "cols": 2,
                }
            ]
        }
    )

    crop_items(ws)

    items = manifest(ws)
    assert sorted(items) == [
        "cards_p1_r00_c00",
        "cards_p1_r00_c01",
        "cards_p1_r01_c00",
        "cards_p1_r01_c01",
    ]
    assert items["cards_p1_r01_c01"]["box"] == [454, 304, 896, 596]


def test_grid_with_lines_leaves_empty_cells_out(ws: Workspace):
    save_page(ws, "cards", 1, [(100, 100)])
    ws.update_config(
        {
            "layouts": [
                {
                    "method": "grid",
                    "file": "cards.pdf",
                    "page": 1,
                    "xs": [0, 450, 900],
                    "ys": [0, 300, 600],
                }
            ]
        }
    )

    out = crop_items(ws)

    assert list(manifest(ws)) == ["cards_p1_r00_c00"]
    assert "1 items" in out.splitlines()[-1]


def test_boxes_layout(ws: Workspace):
    save_page(ws, "cards", 1, [(100, 100), (500, 350)])
    ws.update_config(
        {
            "layouts": [
                {
                    "method": "boxes",
                    "file": "cards.pdf",
                    "page": 1,
                    "boxes": [[80, 80, 280, 240], [480, 330, 680, 490]],
                }
            ]
        }
    )

    crop_items(ws)

    assert sorted(manifest(ws)) == ["cards_p1_r00_c00", "cards_p1_r01_c00"]


def test_files_layout(ws: Workspace):
    (ws.input / "fronts").mkdir()
    (ws.input / "backs").mkdir()
    for name in ("a", "b", "skipme"):
        Image.new("RGB", (40, 20), "red").save(ws.input / "fronts" / f"{name}.png")
    Image.new("RGB", (40, 20), "blue").save(ws.input / "backs" / "a.png")
    ws.update_config(
        {
            "layouts": [
                {
                    "method": "files",
                    "fronts": "fronts/*.png",
                    "backs": "backs/*.png",
                    "skip": ["skipme"],
                    "rotate_items": {"a": 90},
                }
            ]
        }
    )

    out = crop_items(ws)

    items = manifest(ws)
    assert sorted(items) == ["a", "b"]
    assert items["a"]["rotate"] == 90 and items["a"]["file"] == "fronts/a.png"
    assert Image.open(ws.item_dir("a") / "front.png").size == (20, 40)
    assert (ws.item_dir("a") / "back.png").exists()
    assert not (ws.item_dir("b") / "back.png").exists()
    assert "fronts/*.png: 2 items" in out
    assert "no back found for: b" in out


def test_size_outlier_is_reported(ws: Workspace):
    save_page(ws, "cards", 1, six_cards())
    # A big block next to the cards makes one object much larger than the median.
    path = ws.page_image("cards", 1)
    img = Image.open(path)
    ImageDraw.Draw(img).rectangle([20, 450, 880, 590], fill="black")
    img.save(path)
    ws.update_config({"layouts": [{"file": "cards.pdf", "page": 1}]})

    assert "size outliers" in crop_items(ws)


def test_missing_page_render_is_an_error(ws: Workspace):
    ws.update_config({"layouts": [{"file": "cards.pdf", "page": 1}]})
    with pytest.raises(ExtractionError, match="render_pdfs"):
        crop_items(ws)


def test_assign_rows_handles_offset_rows():
    boxes = [((x, y, x + 50, y + 50), None) for x, y in [(0, 0), (60, 3), (30, 80), (90, 82)]]
    rows = [(r, c) for _, _, r, c in assign_rows(boxes)]
    assert rows == [(0, 0), (0, 1), (1, 0), (1, 1)]
