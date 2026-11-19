"""Page renders, their previews and text layers, and the `lines` tool for `grid` layouts."""

import json
import threading
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium
from PIL import Image

from .images import PREVIEW_SIDE, shrunk
from .workspace import ExtractionError, Workspace

POINTS_PER_INCH = 72
LINES_BLOCK = 512
"""`page_lines` reads this many pixel columns at a time, to keep the arrays small."""


# ---------------------------------------------------------------- render


PDFIUM_LOCK = threading.Lock()
"""pypdfium2 is not thread-safe, and the OCR of rules regions renders pages from threads."""


def render_page(pdf: Path, page: int, dpi: int) -> Image.Image:
    """One page (counted from 1) of a PDF as an RGB image."""
    with PDFIUM_LOCK:
        return _render_page(pdf, page, dpi)


def _render_page(pdf: Path, page: int, dpi: int) -> Image.Image:
    document = pdfium.PdfDocument(str(pdf))
    try:
        if not 1 <= page <= len(document):
            raise ExtractionError(f"{pdf.name} has {len(document)} pages, not page {page}")
        return document[page - 1].render(scale=dpi / POINTS_PER_INCH).to_pil().convert("RGB")
    finally:
        document.close()


def render_pdfs(ws: Workspace, dpi: int = 300) -> str:
    """Renders every PDF in the input folder: full pages, small previews and the text layer."""
    pdfs = ws.pdfs()
    if not pdfs:
        raise ExtractionError("there is no PDF in the input folder")
    for folder in ("pages", "preview", "text"):
        (ws.work / folder).mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for pdf in pdfs:
        lines += _render_pdf(ws, pdf, dpi)
    lines.append(
        f"Previews (max {PREVIEW_SIDE} px) in {ws.rel(ws.work / 'preview')}; "
        f"text layer in {ws.rel(ws.work / 'text')}."
    )
    return "\n".join(lines)


def _render_pdf(ws: Workspace, pdf: Path, dpi: int) -> list[str]:
    document = pdfium.PdfDocument(str(pdf))
    lines: list[str] = []
    texts: list[str] = []
    try:
        for number, page in enumerate(document, 1):
            width_pt, height_pt = page.get_size()
            image = page.render(scale=dpi / POINTS_PER_INCH).to_pil().convert("RGB")
            out = ws.page_image(pdf.stem, number)
            image.save(out)
            shrunk(image, PREVIEW_SIDE).save(ws.work / "preview" / out.name)
            texts.append(page.get_textpage().get_text_range())
            lines.append(
                f"{pdf.name} page {number}: {image.width}x{image.height} px at {dpi} dpi "
                f"({width_pt:.0f} x {height_pt:.0f} pt) -> {ws.rel(out)}"
            )
    finally:
        document.close()
    # Pages are separated by a form feed, as `pdftotext` does.
    (ws.work / "text" / f"{pdf.stem}.txt").write_text("\f".join(texts))
    return lines


# ---------------------------------------------------------------- lines


def longest_runs(continuous: np.ndarray) -> np.ndarray:
    """Longest run of True down each column of a 2-D boolean array."""
    run = np.zeros(continuous.shape[1], np.int32)
    best = np.zeros(continuous.shape[1], np.int32)
    for row in continuous:
        run = (run + 1) * row
        np.maximum(best, run, out=best)
    return best


def clusters(mask: np.ndarray) -> list[tuple[float, int]]:
    """(centre, width) of every run of True in a 1-D boolean array."""
    found: list[tuple[float, int]] = []
    start = None
    for i, value in enumerate([*mask, False]):
        if value and start is None:
            start = i
        elif not value and start is not None:
            found.append(((start + i - 1) / 2, i - start))
            start = None
    return found


def _page_file(ws: Workspace, page: str) -> Path:
    """`page` is a path in the run folder, or a page name such as `board_p3`."""
    try:
        direct = ws.resolve(page)
    except ExtractionError:
        direct = None
    if direct is not None and direct.is_file():
        return direct
    named = ws.work / "pages" / f"{page}.png"
    if not named.exists():
        raise ExtractionError(f"no page image {page!r}; call `render_pdfs` first")
    return named


def _line_profile(arr: np.ndarray, min_frac: float) -> tuple[list[dict], list[dict]]:
    """Cut lines and blank gutters across the columns of `arr`, as {pos, width} dicts."""
    fraction, ink = [], []
    # Full resolution, in blocks: cut lines are often 1 px wide and vanish when downscaled.
    for i in range(0, arr.shape[1], LINES_BLOCK):
        block = arr[:, i : i + LINES_BLOCK].astype(np.int16)
        not_white = block.min(-1) < 200
        same_colour = np.abs(block[1:] - block[:-1]).sum(-1) < 40
        continuous = not_white[1:] & not_white[:-1] & same_colour
        fraction.append(longest_runs(continuous) / continuous.shape[0])
        ink.append(not_white.mean(0))
    fraction, ink = np.concatenate(fraction), np.concatenate(ink)
    lines = [{"pos": round(p), "width": w} for p, w in clusters(fraction >= min_frac)]
    gaps = [{"pos": round(p), "width": w} for p, w in clusters(ink < 0.003) if w >= 8]
    return lines, gaps


def page_lines(ws: Workspace, page: str, min_frac: float = 0.5) -> str:
    """Cut lines and gutters on a page, for a `grid` layout: JSON plus a line that explains it."""
    path = _page_file(ws, page)
    arr = np.asarray(Image.open(path).convert("RGB"))
    result: dict = {"page": ws.rel(path), "width": arr.shape[1], "height": arr.shape[0]}
    for name, view in (("x", arr), ("y", arr.transpose(1, 0, 2))):
        result[f"{name}_lines"], result[f"{name}_gaps"] = _line_profile(view, min_frac)
    explanation = (
        "x_lines/y_lines: straight lines spanning at least "
        f"{min_frac:.0%} of the page (cut lines); *_gaps: blank gutters. "
        "Positions in page-render pixels."
    )
    return json.dumps(result, indent=1) + "\n" + explanation
