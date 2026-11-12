from PIL import Image, ImageDraw, ImageFont

from app.extraction.regions import (
    coverage,
    preview_regions,
    region_box,
    rules_pages,
    uncovered_text,
)
from app.extraction.workspace import Workspace

PAGE = (800, 1000)
SENTENCE = "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG AGAIN"


def save_rules_page(ws: Workspace, text_ys: list[int], stem: str = "rules", page: int = 1):
    """A white page with a line of text at each y."""
    img = Image.new("RGB", PAGE, "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=20)
    for y in text_ys:
        draw.text((50, y), SENTENCE, fill="black", font=font)
    path = ws.page_image(stem, page)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def region(box, page=1, file="rules.pdf") -> dict:
    return {"file": file, "page": page, "box": box}


def test_region_box_fractions_and_pixels():
    assert region_box([0.1, 0.2, 0.5, 1], (800, 1000)) == (80, 200, 400, 1000)
    assert region_box([10, 20, 500.4, 900], (800, 1000)) == (10, 20, 500, 900)
    # One value above 1 makes the whole box pixels.
    assert region_box([0, 0, 1, 2], (800, 1000)) == (0, 0, 1, 2)


def test_coverage_flags_text_outside_every_region_only(ws: Workspace):
    save_rules_page(ws, [100, 600])
    ws.update_config({"rules_regions": [region([0, 50, 800, 200])]})

    found = coverage(ws, ws.load_config())

    assert list(found) == [("rules", 1)]
    [(box, letters)] = found[("rules", 1)]
    assert 0.55 < box[1] < 0.62 and box[3] < 0.66
    assert letters >= 15


def test_coverage_is_empty_when_all_text_is_inside(ws: Workspace):
    save_rules_page(ws, [100, 600])
    ws.update_config({"rules_regions": [region([0.0, 0.0, 1.0, 1.0]), region([0, 0, 800, 100])]})

    assert coverage(ws, ws.load_config()) == {}


def test_excluded_box_and_excluded_page(ws: Workspace):
    save_rules_page(ws, [100, 600])
    regions = [region([0, 50, 800, 200])]
    ws.update_config(
        {
            "rules_regions": regions,
            "rules_excluded": [
                {"file": "rules.pdf", "page": 1, "box": [0, 550, 800, 700], "reason": "ad"}
            ],
        }
    )
    assert coverage(ws, ws.load_config()) == {}

    ws.update_config({"rules_excluded": [{"file": "rules.pdf", "page": 1, "reason": "cover"}]})
    assert coverage(ws, ws.load_config()) == {}


def test_rules_pages_skip_component_pages_and_other_files(ws: Workspace):
    for stem, page in (("rules", 1), ("rules", 2), ("rules", 3), ("other", 1)):
        save_rules_page(ws, [], stem, page)
    ws.update_config(
        {
            "rules_regions": [region([0, 0, 1, 1])],
            "layouts": [{"file": "rules.pdf", "page": 2, "back_page": 3}],
        }
    )

    assert rules_pages(ws, ws.load_config()) == [("rules", 1)]


def test_uncovered_text_ignores_a_blank_page():
    assert uncovered_text(Image.new("RGB", PAGE, "white"), []) == []


def test_preview_regions_draws_and_reports(ws: Workspace):
    save_rules_page(ws, [100, 600])
    ws.update_config({"rules_regions": [region([0, 50, 800, 200])]})

    out = preview_regions(ws)

    assert (ws.work / "preview" / "regions_rules_p1.png").exists()
    assert "work/preview/regions_rules_p1.png" in out
    assert "UNCOVERED rules page 1" in out
    assert "u0 [" in out
    assert "`assemble` refuses" in out
    assert out.splitlines()[-1].startswith("This check misses page numbers")


def test_preview_regions_without_uncovered_text(ws: Workspace):
    save_rules_page(ws, [100])
    ws.update_config({"rules_regions": [region([0, 50, 800, 200])]})

    out = preview_regions(ws)

    assert "UNCOVERED" not in out
