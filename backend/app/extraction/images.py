"""Small image helpers shared by the steps."""

import base64
import io
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

MAX_SIDE = 1568
"""The API shrinks larger images anyway, so images sent to a model are never larger."""

PREVIEW_SIDE = 1400


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
