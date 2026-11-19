"""Rules regions: where they are on a page, which text lies outside them, and a preview."""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from .images import PREVIEW_SIDE, page_background, shrunk
from .models import ExtractionConfig
from .workspace import Workspace

Coverage = dict[tuple[str, int], list[tuple[list[float], int]]]
"""Per (file stem, page): the text blocks outside every region, as (box in fractions, letters)."""


def region_box(box, size: tuple[int, int]) -> tuple[int, int, int, int]:
    """[x0, y0, x1, y1] in page-render pixels, or as fractions of the page if all are <= 1."""
    x0, y0, x1, y1 = box
    if max(box) <= 1:
        x0, x1, y0, y1 = x0 * size[0], x1 * size[0], y0 * size[1], y1 * size[1]
    return int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1))


# ---------------------------------------------------------------- text outside the regions


def uncovered_text(img: Image.Image, boxes, min_glyphs: int = 15) -> list[tuple[list[float], int]]:
    """Blocks of print outside every box: glyph-sized marks grouped into lines and paragraphs, on a
    plain background (texture in pictures has little of it). Returns (box in fractions, letters)."""
    arr = np.asarray(img.convert("RGB")).astype(np.int16)
    ink = np.abs(arr - page_background(arr)).max(-1) > 80
    height, width = ink.shape
    labels, _ = ndimage.label(ink)
    objects = ndimage.find_objects(labels)
    if not objects:
        return []
    heights = np.array([s[0].stop - s[0].start for s in objects])
    widths = np.array([s[1].stop - s[1].start for s in objects])
    centre_y = np.array([(s[0].start + s[0].stop) // 2 for s in objects])
    centre_x = np.array([(s[1].start + s[1].stop) // 2 for s in objects])

    covered = np.zeros(ink.shape, bool)
    for box in boxes:
        x0, y0, x1, y1 = region_box(box, img.size)
        covered[y0:y1, x0:x1] = True
    is_glyph = (
        (heights >= 0.003 * height)
        & (heights <= 0.03 * height)
        & (widths <= 4 * heights)
        & ~covered[centre_y, centre_x]
    )
    if not is_glyph.any():
        return []

    glyphs = np.isin(labels, np.flatnonzero(is_glyph) + 1)
    glyph_height = int(np.median(heights[is_glyph]))
    blocks, _ = ndimage.label(ndimage.maximum_filter(glyphs, size=(glyph_height, 2 * glyph_height)))
    counts = np.bincount(blocks[centre_y[is_glyph], centre_x[is_glyph]], minlength=blocks.max() + 1)
    plain = ~ndimage.maximum_filter(ink, size=7)
    return [
        (
            [
                round(sl[1].start / width, 3),
                round(sl[0].start / height, 3),
                round(sl[1].stop / width, 3),
                round(sl[0].stop / height, 3),
            ],
            int(counts[i]),
        )
        for i, sl in enumerate(ndimage.find_objects(blocks), 1)
        if counts[i] >= min_glyphs and plain[sl].mean() >= 0.3
    ]


def rules_pages(ws: Workspace, cfg: ExtractionConfig) -> list[tuple[str, int]]:
    """Every page of the files that have rules regions, except component pages."""
    stems = {Path(r.file).stem for r in cfg.rules_regions}
    components = set()
    for layout in cfg.layouts:
        if layout.file is not None and layout.page is not None:
            stem = Path(layout.file).stem
            components |= {(stem, layout.page), (stem, layout.back_page)}
    pages = []
    for path in ws.work.glob("pages/*.png"):
        stem, _, number = path.stem.rpartition("_p")
        if stem in stems and number.isdigit() and (stem, int(number)) not in components:
            pages.append((stem, int(number)))
    return sorted(pages)


def _on_page(entry, stem: str, page: int) -> bool:
    return Path(entry.file).stem == stem and entry.page == page


def coverage(ws: Workspace, cfg: ExtractionConfig) -> Coverage:
    """Text blocks outside every rules region and every `rules_excluded` box, per page."""
    found: Coverage = {}
    for stem, page in rules_pages(ws, cfg):
        excluded = [e for e in cfg.rules_excluded if _on_page(e, stem, page)]
        if any(e.box is None for e in excluded):
            continue  # the whole page is excluded
        boxes = [r.box for r in cfg.rules_regions if _on_page(r, stem, page)]
        boxes += [e.box for e in excluded]
        blocks = uncovered_text(Image.open(ws.page_image(stem, page)), boxes)
        if blocks:
            found[(stem, page)] = blocks
    return found


# ---------------------------------------------------------------- preview


def _draw_box(draw: ImageDraw.ImageDraw, box, size, scale: float, colour: str, label: str = ""):
    x0, y0, x1, y1 = (v * scale for v in region_box(box, size))
    draw.rectangle([x0, y0, x1, y1], outline=colour, width=3)
    if label:
        draw.text((x0 + 5, y0 + 5), label, fill=colour)


def preview_regions(ws: Workspace) -> str:
    """Rules regions drawn on their pages, with text left outside them."""
    cfg = ws.load_config()
    uncovered = coverage(ws, cfg)
    lines: list[str] = []
    for stem, page in rules_pages(ws, cfg):
        full = Image.open(ws.page_image(stem, page))
        image = shrunk(full.convert("RGB"), PREVIEW_SIDE)
        scale = image.width / full.width
        draw = ImageDraw.Draw(image)
        for i, region in enumerate(cfg.rules_regions):
            if _on_page(region, stem, page):
                _draw_box(draw, region.box, full.size, scale, "blue", f"#{i}")
        for excluded in cfg.rules_excluded:
            if _on_page(excluded, stem, page) and excluded.box is not None:
                _draw_box(draw, excluded.box, full.size, scale, "gray")
        for n, (box, _) in enumerate(uncovered.get((stem, page), [])):
            _draw_box(draw, box, full.size, scale, "red", f"u{n}")
        out = ws.work / "preview" / f"regions_{stem}_p{page}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        image.save(out)
        lines.append(ws.rel(out))
    for (stem, page), blocks in uncovered.items():
        found = "; ".join(f"u{n} {box} ({count} letters)" for n, (box, count) in enumerate(blocks))
        lines.append(
            f"UNCOVERED {stem} page {page}: text outside every region, in red on "
            f"regions_{stem}_p{page}.png: {found}"
        )
    if uncovered:
        lines.append(
            "Cover each UNCOVERED block with a rules region, or list it in `rules_excluded` with "
            "the reason (leave out `box` to exclude a whole page, such as a cover). `assemble` "
            "refuses while any are left."
        )
    lines.append(
        "This check misses page numbers, very short lines, and light text on dark or coloured "
        "bands: check the previews for headings yourself. No line of text may be cut by a region "
        "edge."
    )
    return "\n".join(lines)
