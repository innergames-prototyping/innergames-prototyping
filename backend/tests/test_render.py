import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from app.extraction.render import clusters, longest_runs, page_lines, render_page, render_pdfs
from app.extraction.workspace import ExtractionError, Workspace


def make_pdf(path: Path, pages: int = 2) -> None:
    """A PDF of `pages` pages, 200 x 300 pt, each with a different black block."""
    images = []
    for n in range(pages):
        img = Image.new("RGB", (200, 300), "white")
        ImageDraw.Draw(img).rectangle([20, 20 + 40 * n, 80, 60 + 40 * n], fill="black")
        images.append(img)
    images[0].save(path, "PDF", resolution=72, save_all=True, append_images=images[1:])


def test_render_pdfs_writes_pages_previews_and_text_layer(ws: Workspace):
    make_pdf(ws.input / "game.pdf")

    out = render_pdfs(ws, dpi=36)

    assert "game.pdf page 1: 100x150 px at 36 dpi (200 x 300 pt)" in out
    assert "game.pdf page 2" in out
    for page in (1, 2):
        assert ws.page_image("game", page).exists()
        assert (ws.work / "preview" / f"game_p{page}.png").exists()
    assert Image.open(ws.page_image("game", 1)).size == (100, 150)
    assert (ws.work / "text" / "game.txt").exists()


def test_render_pdfs_without_pdf_fails(ws: Workspace):
    with pytest.raises(ExtractionError):
        render_pdfs(ws)


def test_render_page_returns_one_page(ws: Workspace):
    make_pdf(ws.input / "game.pdf")

    img = render_page(ws.input / "game.pdf", 2, dpi=72)

    assert img.size == (200, 300)
    assert img.getpixel((50, 100)) == (0, 0, 0)  # the block of page 2
    with pytest.raises(ExtractionError):
        render_page(ws.input / "game.pdf", 3, dpi=72)


def test_page_lines_finds_a_cut_line(ws: Workspace):
    img = Image.new("RGB", (300, 200), "white")
    ImageDraw.Draw(img).line([(100, 0), (100, 199)], fill="black", width=1)
    out_path = ws.page_image("cards", 1)
    out_path.parent.mkdir(parents=True)
    img.save(out_path)

    out = page_lines(ws, "cards_p1")

    data = json.loads(out.split("\nx_lines/y_lines")[0])
    assert data["width"] == 300
    assert data["x_lines"] == [{"pos": 100, "width": 1}]
    assert data["y_lines"] == []
    assert out.splitlines()[-1].startswith("x_lines/y_lines: straight lines")


def test_page_lines_accepts_a_path_and_refuses_an_unknown_page(ws: Workspace):
    Image.new("RGB", (20, 20), "white").save(ws.work / "p.png")

    assert '"page": "work/p.png"' in page_lines(ws, "work/p.png")
    with pytest.raises(ExtractionError):
        page_lines(ws, "nothing")


def test_longest_runs_and_clusters():
    import numpy as np

    grid = np.array([[1, 1, 0], [1, 0, 0], [1, 1, 0]], bool)
    assert longest_runs(grid).tolist() == [3, 1, 0]
    assert clusters(np.array([0, 1, 1, 0, 1], bool)) == [(1.5, 2), (4.0, 1)]
