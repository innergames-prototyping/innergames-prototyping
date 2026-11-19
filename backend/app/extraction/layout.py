"""Finding the items on component pages, cutting them out, and pairing fronts with backs.

Four layout methods (see `models.Layout`): `segment` finds every separate object, `grid` cuts
along lines, `boxes` takes one box per item, and `files` takes one image file per item.
"""

import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from .images import PREVIEW_SIDE, contact_sheet, ink_mask, page_background, rotate, trim
from .models import Layout
from .regions import region_box
from .workspace import ExtractionError, Workspace, save_json

Box = tuple[int, int, int, int]
Mask = np.ndarray | None
Found = tuple[Box, Mask, int, int]
"""One item on a page: (box, mask, row, col). The mask is None when the box is the item."""

CONTACT_SHEET_ITEMS = 100


def item_key(stem: str, page: int, row: int, col: int) -> str:
    """The folder name of an item under work/items. B and C use this format."""
    return f"{stem}_p{page}_r{row:02d}_c{col:02d}"


# ---------------------------------------------------------------- detection


def detect_segment(page: Image.Image, layout: Layout) -> list[tuple[Box, np.ndarray]]:
    """Every separate object on the page, whatever its shape. Works on a reduced copy. Thin lines
    (cut lines, crop marks, dashes) are dropped: an opening finds the solid cores, and only ink
    close to a core is kept, so an object keeps its own thin outlines. Nearby parts of one object
    are joined by a closing and holes are filled. Returns [(bbox, mask)] at full resolution."""
    f = layout.scale
    small = np.asarray(page.reduce(f))
    ink = ink_mask(small, page_background(small))
    k = max(1, round(layout.line_width / f))
    cores = ndimage.binary_opening(ink, structure=np.ones((k + 1, k + 1)))
    ink &= ndimage.binary_dilation(cores, iterations=k + 1)
    m = max(1, round(layout.merge / f))
    ink = ndimage.binary_closing(ink, structure=np.ones((m, m)), iterations=1)
    ink = ndimage.binary_fill_holes(ink)
    labels, _ = ndimage.label(ink)
    sizes = np.bincount(labels.ravel())
    found = []
    pad = k + 2
    for n, (ys, xs) in enumerate(ndimage.find_objects(labels), 1):
        if sizes[n] < layout.min_area * ink.size:
            continue
        y0, x0 = max(0, ys.start - pad), max(0, xs.start - pad)
        y1, x1 = min(ink.shape[0], ys.stop + pad), min(ink.shape[1], xs.stop + pad)
        # Grown by more than the opening removed, so thin outer outlines are not clipped.
        mask = ndimage.binary_dilation(labels[y0:y1, x0:x1] == n, iterations=pad)
        mask = np.kron(mask, np.ones((f, f), bool))
        found.append(((x0 * f, y0 * f, x1 * f, y1 * f), mask))
    return found


def detect_grid(page: Image.Image, layout: Layout) -> list[Found]:
    """Cells between the lines `xs` / `ys`, or an equal grid of `rows` x `cols` inside `box`."""
    if layout.xs is not None and layout.ys is not None:
        xs, ys = layout.xs, layout.ys
    else:
        x0, y0, x1, y1 = region_box(layout.box, page.size)
        xs = [x0 + (x1 - x0) * c / layout.cols for c in range(layout.cols + 1)]
        ys = [y0 + (y1 - y0) * r / layout.rows for r in range(layout.rows + 1)]
    inset = layout.inset
    return [
        (
            (
                round(xs[c]) + inset,
                round(ys[r]) + inset,
                round(xs[c + 1]) - inset,
                round(ys[r + 1]) - inset,
            ),
            None,
            r,
            c,
        )
        for r in range(len(ys) - 1)
        for c in range(len(xs) - 1)
    ]


def assign_rows(found: list[tuple[Box, Mask]]) -> list[Found]:
    """Row = band of similar centre height (offset hex rows included), col = order in the row."""
    if not found:
        return []

    def centre(item: tuple[Box, Mask]) -> float:
        return (item[0][1] + item[0][3]) / 2

    found = sorted(found, key=centre)
    height = np.median([box[3] - box[1] for box, _ in found])
    rows, current = [], [found[0]]
    for item in found[1:]:
        if centre(item) - np.mean([centre(i) for i in current]) > height / 2:
            rows.append(current)
            current = []
        current.append(item)
    rows.append(current)
    return [
        (box, mask, r, c)
        for r, row in enumerate(rows)
        for c, (box, mask) in enumerate(sorted(row, key=lambda item: item[0][0]))
    ]


def detect(page: Image.Image, layout: Layout) -> list[Found]:
    if layout.method == "grid":
        return detect_grid(page, layout)
    if layout.method == "boxes":
        return assign_rows([(region_box(b, page.size), None) for b in layout.boxes])
    return assign_rows(detect_segment(page, layout))


def cut(page: Image.Image, box: Box, mask: Mask) -> Image.Image | None:
    """The item inside `box`, with everything outside its outline made white. None if empty."""
    img = page.crop(box)
    if mask is None:
        return trim(img)
    arr = np.asarray(img).copy()
    arr[~mask[: arr.shape[0], : arr.shape[1]]] = 255
    return trim(Image.fromarray(arr))


# ---------------------------------------------------------------- items that come as files


def crop_files(ws: Workspace, layout: Layout, number: int) -> tuple[list[dict], list[str]]:
    """Items that come as one image file each. The part of the file name matched by the `*` in
    `fronts` names the item, and finds its back through the `*` in `backs`. Patterns are relative
    to the input folder."""
    prefix, _, suffix = layout.fronts.partition("*")
    back_prefix, _, back_suffix = (layout.backs or "").partition("*")
    entries, thumbs, no_back = [], [], []
    for path in sorted(ws.input.glob(layout.fronts)):
        relative = path.relative_to(ws.input).as_posix()
        name = relative[len(prefix) : len(relative) - len(suffix)]
        if name in layout.skip:
            continue
        degrees = layout.rotate_items.get(name, layout.rotate)
        key = re.sub(r"[^\w.-]", "_", name)
        folder = ws.item_dir(key)
        if folder.exists():
            raise ExtractionError(
                f"two items get the key {key!r}; rename the files or use another `fronts` pattern"
            )
        folder.mkdir(parents=True)
        front = rotate(Image.open(path).convert("RGB"), degrees)
        front.save(folder / "front.png")
        if layout.backs:
            back_path = ws.input / (back_prefix + name + back_suffix)
            if back_path.exists():
                rotate(Image.open(back_path).convert("RGB"), degrees).save(folder / "back.png")
            else:
                no_back.append(name)
        entries.append({"key": key, "label": name, "file": relative, "page": 1, "rotate": degrees})
        thumbs.append((name, front))
    sheets = [
        contact_sheet(
            thumbs[i : i + CONTACT_SHEET_ITEMS],
            ws.work / "contact" / f"files{number}_{i // CONTACT_SHEET_ITEMS + 1}.png",
        )
        for i in range(0, len(thumbs), CONTACT_SHEET_ITEMS)
    ]
    lines = [
        f"{layout.fronts}: {len(entries)} items",
        f"    contact sheets: {' '.join(ws.rel(s) for s in sheets)}",
    ]
    if no_back:
        lines.append(f"    no back found for: {' '.join(no_back)}")
    return entries, lines


# ---------------------------------------------------------------- items on a page


def back_position(
    box: Box,
    mask: Mask,
    row: int,
    col: int,
    row_len: Counter,
    n_rows: int,
    back_size: tuple[int, int],
    mirror: str,
) -> tuple[Box, Mask, int, int]:
    """Where the back of an item sits on the back page: (box, mask, row, col).

    Printed double-sided, the back is at the mirrored position, with a mirrored outline.
    `horizontal` flips left-right (the usual case), `vertical` flips top-bottom, `none` keeps it."""
    width, height = back_size
    if mirror == "horizontal":
        flipped = mask[:, ::-1] if mask is not None else None
        back_box = (width - box[2], box[1], width - box[0], box[3])
        return back_box, flipped, row, row_len[row] - 1 - col
    if mirror == "vertical":
        flipped = mask[::-1] if mask is not None else None
        back_box = (box[0], height - box[3], box[2], height - box[1])
        return back_box, flipped, n_rows - 1 - row, col
    return box, mask, row, col


def outline_overlay(front: Image.Image) -> tuple[Image.Image, float]:
    """A reduced copy of the page to draw outlines on, and its scale to the full page."""
    overlay = front.copy()
    overlay.thumbnail((PREVIEW_SIDE * 2, PREVIEW_SIDE * 2))
    return overlay, overlay.width / front.width


def size_outliers(found: list[Found]) -> dict[str, float]:
    """Items whose area is far from the median: signs of split or merged objects."""
    areas = {f"r{r}c{c}": (b[2] - b[0]) * (b[3] - b[1]) for b, _, r, c in found}
    median = np.median(list(areas.values())) if areas else 0
    return {
        key: round(area / median, 2)
        for key, area in areas.items()
        if area < median / 3 or area > median * 3
    }


def page_image(ws: Workspace, stem: str, page: int) -> Image.Image:
    path = ws.page_image(stem, page)
    if not path.exists():
        raise ExtractionError(f"{ws.rel(path)} does not exist; call `render_pdfs` first")
    return Image.open(path).convert("RGB")


def crop_page(ws: Workspace, layout: Layout) -> tuple[list[dict], list[str]]:
    """Cuts every item out of one layout's page (and its back page). Returns manifest entries and
    the lines for the tool output."""
    stem = Path(layout.file).stem
    front = page_image(ws, stem, layout.page)
    back = page_image(ws, stem, layout.back_page) if layout.back_page else None
    found = [item for item in detect(front, layout) if f"r{item[2]}c{item[3]}" not in layout.skip]
    row_len = Counter(row for _, _, row, _ in found)
    n_rows = max(row_len, default=-1) + 1
    overlay, scale = outline_overlay(front)
    draw = ImageDraw.Draw(overlay)
    entries, thumbs = [], []
    for box, mask, r, c in found:
        cell = cut(front, box, mask)
        if cell is None:
            continue
        rot = layout.rotate_items
        degrees = rot.get(f"r{r}c{c}", rot.get(f"r{r}", layout.rotate))
        key = item_key(stem, layout.page, r, c)
        folder = ws.item_dir(key)
        folder.mkdir(parents=True, exist_ok=True)
        rotate(cell, degrees).save(folder / "front.png")
        entry: dict[str, Any] = {
            "key": key,
            "file": layout.file,
            "page": layout.page,
            "row": r,
            "col": c,
            "rotate": degrees,
            "box": box,
        }
        if back is not None:
            entry |= _save_back(back, layout, folder, (box, mask, r, c), degrees, row_len, n_rows)
        entries.append(entry)
        thumbs.append((f"r{r}c{c}", rotate(cell, degrees)))
        scaled = [v * scale for v in box]
        draw.rectangle(scaled, outline="red", width=2)
        draw.text((scaled[0] + 4, scaled[1] + 3), f"r{r}c{c}", fill="red")

    overlay_path = ws.work / "preview" / f"items_{stem}_p{layout.page}.png"
    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    overlay.save(overlay_path)
    sheet = contact_sheet(thumbs, ws.work / "contact" / f"{stem}_p{layout.page}.png")
    lines = [
        f"{stem} p{layout.page}: {len(thumbs)} items in {len(row_len)} rows "
        f"{dict(sorted(row_len.items()))}",
        f"    outlines on the page: {ws.rel(overlay_path)}",
        f"    contact sheet: {ws.rel(sheet)}",
    ]
    if odd := size_outliers(found):
        lines.append(
            f"    size outliers (area / median): {odd} - split or merged objects? "
            "Check the outlines; adjust merge/line_width or use a grid or boxes layout."
        )
    return entries, lines


def _save_back(
    back: Image.Image,
    layout: Layout,
    folder: Path,
    item: tuple[Box, Mask, int, int],
    degrees: int,
    row_len: Counter,
    n_rows: int,
) -> dict[str, Any]:
    """Cuts and saves the back of one item. Returns the manifest keys for it (empty if no back)."""
    box, mask, r, c = item
    back_box, back_mask, back_row, back_col = back_position(
        box, mask, r, c, row_len, n_rows, back.size, layout.back_mirror
    )
    cell = cut(back, back_box, back_mask)
    if cell is None:
        return {}
    rotate(cell, degrees).save(folder / "back.png")
    return {"back_page": layout.back_page, "back_row": back_row, "back_col": back_col}


# ---------------------------------------------------------------- the tool


def crop_items(ws: Workspace) -> str:
    """Finds every item on the configured pages, cuts it out and writes work/items.json."""
    config = ws.load_config()
    items_folder = ws.work / "items"
    if items_folder.exists():
        shutil.rmtree(items_folder)
    manifest: list[dict] = []
    lines: list[str] = []
    for number, layout in enumerate(config.layouts, 1):
        if layout.method == "files":
            entries, layout_lines = crop_files(ws, layout, number)
        else:
            entries, layout_lines = crop_page(ws, layout)
        manifest += entries
        lines += layout_lines
    save_json(ws.work / "items.json", manifest)
    lines.append(f"{len(manifest)} items")
    return "\n".join(lines)
