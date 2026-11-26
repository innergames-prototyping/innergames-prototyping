"""Small image helpers shared by the steps."""

import base64
import io
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

MAX_SIDE = 1568
"""The API shrinks larger images anyway, so images sent to a model are never larger."""

TILE_SIDE = 2000
"""A component more than twice MAX_SIDE is also read in tiles of about this size."""

PREVIEW_SIDE = 1400

TILT_SIDE = 300
"""Crops are measured for tilt at this size."""

TILT_CUTOFF = 1.5
"""How many times sharper than at 0 degrees a turn must be to count as a tilt. Tilted labels score
at least 1.8 times their score at 0; on upright cards no angle beats 0."""


def page_background(arr: np.ndarray) -> np.ndarray:
    """The median colour of the image border."""
    border = np.concatenate([arr[0], arr[-1], arr[:, 0], arr[:, -1]])
    return np.median(border, axis=0).astype(np.int16)


def ink_mask(arr: np.ndarray, background: np.ndarray) -> np.ndarray:
    """True where a pixel clearly differs from the background colour."""
    return np.abs(arr.astype(np.int16) - background).max(-1) > 40


def trim(img: Image.Image, background=(255, 255, 255), min_frac=0.01) -> Image.Image | None:
    """Crop to the connected ink regions that are not small, which drops cut marks, dashes and
    thin lines in the margins. Regions close to each other count together, so the letters of a
    card printed in plain text are kept; long thin or sparse marks (lines, brackets, crop marks)
    don't join a group. Returns None for an empty cell."""
    ink = ink_mask(np.asarray(img.convert("RGB")), np.array(background, np.int16))
    if ink.mean() < min_frac:
        return None
    labels, _ = ndimage.label(ink, structure=np.ones((3, 3)))
    sizes = np.bincount(labels.ravel())
    min_size, side = 0.005 * ink.size, min(ink.shape)
    is_line = np.zeros(len(sizes), bool)
    for n, (ys, xs) in enumerate(ndimage.find_objects(labels), 1):
        h, w = ys.stop - ys.start, xs.stop - xs.start
        long = max(h, w) >= 0.1 * side
        thin_or_sparse = min(h, w) <= 0.01 * side or sizes[n] < 0.25 * h * w
        is_line[n] = long and thin_or_sparse
    near = ink & ~is_line[labels]
    r = max(1, round(0.015 * side))
    groups, _ = ndimage.label(ndimage.maximum_filter(near, size=2 * r + 1))
    group_sizes = np.bincount(groups[near], minlength=groups.max() + 1)
    kept = (sizes[labels] >= min_size) & ink | near & (group_sizes[groups] >= min_size)
    if not kept.any():
        return None
    ys, xs = np.flatnonzero(kept.any(1)), np.flatnonzero(kept.any(0))
    return img.crop((xs[0], ys[0], xs[-1] + 1, ys[-1] + 1))


def rotate(img: Image.Image, degrees_clockwise: int) -> Image.Image:
    return img.rotate(-degrees_clockwise, expand=True) if degrees_clockwise % 360 else img


def _line_sharpness(mask: Image.Image, degrees: float) -> float:
    turned = np.asarray(mask.rotate(degrees, expand=True), np.float32)
    return float(sum(np.sum(np.diff(turned.sum(axis)) ** 2) for axis in (0, 1)))


def _thin_strokes(img: Image.Image) -> np.ndarray:
    """True on letters and other thin strokes, not on the long edges of coloured areas, which
    would outweigh the letters."""
    gray = img.convert("L")
    gray.thumbnail((TILT_SIDE, TILT_SIDE))
    arr = np.asarray(gray, np.float32)
    size = max(5, min(arr.shape) // 40)
    return (
        np.maximum(ndimage.white_tophat(arr, size=size), ndimage.black_tophat(arr, size=size)) > 40
    )


def text_tilt(img: Image.Image) -> float:
    """Degrees counterclockwise, within 45 of level, that the image's lines of text run at: the
    turn at which rows or columns of thin strokes are sharpest. Columns count too, because
    near-vertical single words have few rows. 0 when no angle stands out, as on a crop with text
    in several directions."""
    strokes = _thin_strokes(img)
    if strokes.mean() < 0.005:
        return 0.0
    mask = Image.fromarray(strokes.astype(np.uint8) * 255)
    coarse = {d: _line_sharpness(mask, d) for d in range(-45, 46)}
    best = max(coarse, key=coarse.get)
    near_best = np.arange(max(best - 1, -45), min(best + 1, 45) + 0.01, 0.25)
    fine = {float(d): _line_sharpness(mask, float(d)) for d in near_best}
    best = max(fine, key=fine.get)
    if abs(best) < 1 or fine[best] < TILT_CUTOFF * coarse[0]:
        return 0.0
    return -best


def level(img: Image.Image) -> tuple[Image.Image, float]:
    """The image with its text turned to the nearest of level, sideways or upside down, and the
    tilt it had in degrees counterclockwise. An image without a clear tilt comes back as it is."""
    tilt = text_tilt(img)
    if not tilt:
        return img, 0.0
    rgb = img.convert("RGB")
    background = tuple(int(v) for v in page_background(np.asarray(rgb)))
    levelled = rgb.rotate(
        -tilt, expand=True, resample=Image.Resampling.BICUBIC, fillcolor=background
    )
    return levelled, tilt


def shrunk(img: Image.Image, max_side: int) -> Image.Image:
    """A copy no larger than `max_side` on its longest side."""
    small = img.copy()
    small.thumbnail((max_side, max_side))
    return small


def enlarged(img: Image.Image) -> Image.Image:
    """Scaled up so the longest side is MAX_SIDE; readers read small print better that way."""
    f = MAX_SIDE / max(img.size)
    if f <= 1:
        return img
    return img.resize((round(img.width * f), round(img.height * f)), Image.Resampling.LANCZOS)


def halves(img: Image.Image) -> list[Image.Image]:
    """Two overlapping halves along the longer side. Readers spot misspellings far more reliably
    in an enlarged half than in the whole region."""
    w, h = img.size
    n = max(w, h)
    spans = [(0, int(n * 0.55)), (int(n * 0.45), n)]
    return [img.crop((a, 0, b, h) if w >= h else (0, a, w, b)) for a, b in spans]


def tiles(img: Image.Image, overlap=0.08) -> tuple[int, int, list[Image.Image]]:
    """A large component cut into a grid of overlapping tiles, so small print survives the API's
    downsizing. Returns (rows, cols, tiles row by row), or (0, 0, []) when the image is not large
    enough to need it."""
    width, height = img.size
    if max(width, height) <= 2 * MAX_SIDE:
        return 0, 0, []
    rows, cols = math.ceil(height / TILE_SIDE), math.ceil(width / TILE_SIDE)
    tile_width, tile_height = width / cols, height / rows
    margin_x, margin_y = tile_width * overlap, tile_height * overlap
    parts = []
    for row in range(rows):
        for col in range(cols):
            left = int(max(0, col * tile_width - margin_x))
            top = int(max(0, row * tile_height - margin_y))
            right = int(min(width, (col + 1) * tile_width + margin_x))
            bottom = int(min(height, (row + 1) * tile_height + margin_y))
            parts.append(img.crop((left, top, right, bottom)))
    return rows, cols, parts


def png_base64(img: Image.Image) -> str:
    """PNG for a model call, no larger than MAX_SIDE."""
    if max(img.size) > MAX_SIDE:
        img = shrunk(img, MAX_SIDE)
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def contact_sheet(entries: list[tuple[str, Image.Image]], out: Path, width=1600, thumb=150) -> Path:
    """Thumbnails in a grid, each with its label above it."""
    per_row = max(1, width // (thumb + 10))
    rows = (len(entries) + per_row - 1) // per_row
    sheet = Image.new("RGB", (per_row * (thumb + 10), max(1, rows) * (thumb + 26)), "white")
    draw = ImageDraw.Draw(sheet)
    for i, (label, img) in enumerate(entries):
        x, y = (i % per_row) * (thumb + 10) + 5, (i // per_row) * (thumb + 26) + 3
        draw.text((x, y), label, fill="red")
        sheet.paste(shrunk(img, thumb), (x, y + 14))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out
