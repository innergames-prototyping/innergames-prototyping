"""Grouping of identical items into designs, and of near-identical backs."""

import os
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

from .images import contact_sheet
from .workspace import Workspace, load_json, save_json

SHIFT_POOL = ThreadPoolExecutor(os.cpu_count())
"""Shared by `similar`, which compares the shifted copies of two items at the same time."""

DESIGN_SHEET_ITEMS = 60
COLOUR_DIFFERENCE = 80
"""A pixel counts as different when one colour channel differs by more than this."""

Pixels = np.ndarray


def _different_pixels(a: Pixels, b: Pixels, dy: int, dx: int, shift: int) -> Pixels:
    """Where `a` and `b` differ when `b` is moved by (dy, dx); `a` is cut by `shift` per side."""
    h, w = min(a.shape[0], b.shape[0]) - 2 * shift, min(a.shape[1], b.shape[1]) - 2 * shift
    ref = a[shift : shift + h, shift : shift + w]
    return np.abs(ref - b[dy : dy + h, dx : dx + w]).max(-1) > COLOUR_DIFFERENCE


def similar(a, b, shift=3, tol=0.001, block=12, block_tol=0.05) -> tuple[bool, float]:
    """Pixel comparison of two RGB arrays, allowing a small misalignment. Identical only if few
    pixels differ overall AND no small block differs much: a single changed symbol (a pip, a
    sign) is a tiny fraction of the whole item but fills a block.
    Colour, not grey: printed reds and greens can have the same brightness."""
    if abs(a.shape[0] - b.shape[0]) > 2 * shift or abs(a.shape[1] - b.shape[1]) > 2 * shift:
        return False, 1.0
    h, w = min(a.shape[0], b.shape[0]) - 2 * shift, min(a.shape[1], b.shape[1]) - 2 * shift
    shifts = [(dy, dx) for dy in range(2 * shift + 1) for dx in range(2 * shift + 1)]
    diffs = SHIFT_POOL.map(lambda s: _different_pixels(a, b, s[0], s[1], shift), shifts)
    best = min(diffs, key=lambda d: d.mean())
    hb, wb = h // block * block, w // block * block
    worst_block = best[:hb, :wb].reshape(hb // block, block, wb // block, block).mean((1, 3)).max()
    return bool(best.mean() <= tol and worst_block <= block_tol), float(best.mean())


def differs_small(a, b, shift=1, frac=0.01) -> bool:
    """Cheap first test on 1/8-size images: True only when the items clearly differ. Identical
    prints differ in no pixel at this size; items that differ only in a small symbol look
    identical here and are left to `similar`."""
    if abs(a.shape[0] - b.shape[0]) > 2 * shift or abs(a.shape[1] - b.shape[1]) > 2 * shift:
        return True
    h, w = min(a.shape[0], b.shape[0]) - 2 * shift, min(a.shape[1], b.shape[1]) - 2 * shift
    if h < 1 or w < 1:
        return False
    smallest = min(
        _different_pixels(a, b, dy, dx, shift).mean()
        for dy in range(2 * shift + 1)
        for dx in range(2 * shift + 1)
    )
    return smallest > frac


def _versions(path: Path) -> tuple[Pixels, Pixels, Pixels]:
    """An image at half size (for `similar`), 16x16 (a colour signature) and 1/8 size."""
    img = Image.open(path).convert("RGB")

    def at(size: tuple[int, int]) -> Pixels:
        return np.asarray(img.resize(size)).astype(np.int16)

    return (
        at((img.width // 2, img.height // 2)),
        at((16, 16)),
        at((max(1, img.width // 8), max(1, img.height // 8))),
    )


def cluster(paths: dict[str, Path], **tol) -> list[list[str]]:
    """Groups of keys whose images are the same. The first group that matches wins."""
    versions = {key: _versions(path) for key, path in paths.items()}
    groups: list[list[str]] = []
    # numpy releases the GIL, so threads compare against several groups at once; the first matching
    # group in order still wins, as in a sequential search.
    with ThreadPoolExecutor(os.cpu_count()) as pool:
        for key, (arr, signature, small) in versions.items():
            candidates = [
                g
                for g in groups
                if np.abs(signature - versions[g[0]][1]).mean() < 25
                and not differs_small(versions[g[0]][2], small)
            ]

            def is_same(group: list[str], arr: Pixels = arr) -> bool:
                return similar(versions[group[0]][0], arr, **tol)[0]

            hits = pool.map(is_same, candidates)
            match = next((g for g, hit in zip(candidates, hits, strict=True) if hit), None)
            if match:
                match.append(key)
            else:
                groups.append([key])
    return groups


def group_designs(ws: Workspace) -> str:
    """Groups pixel-identical fronts (designs) and near-identical backs; writes work/groups.json."""
    config = ws.load_config()
    items = load_json(ws.work / "items.json", [])
    separate = set(config.separate)
    fronts = {
        i["key"]: ws.item_dir(i["key"]) / "front.png" for i in items if i["key"] not in separate
    }
    designs = cluster(fronts) + [[key] for key in sorted(separate)]
    # Backs only drive a consistency check, so near-identical is close enough.
    back_paths = {
        i["key"]: ws.item_dir(i["key"]) / "back.png"
        for i in items
        if (ws.item_dir(i["key"]) / "back.png").exists()
    }
    backs = cluster(back_paths, tol=0.02, block_tol=0.4)
    groups = {
        "designs": {f"d{n:03d}": g for n, g in enumerate(designs, 1)},
        "backs": {f"b{n:02d}": g for n, g in enumerate(backs, 1)},
    }
    save_json(ws.work / "groups.json", groups)

    design_sheets = _design_sheets(ws, groups["designs"])
    back_sheet = _back_sheet(ws, groups["backs"])
    lines = [f"{len(items)} items -> {len(designs)} designs, {len(backs)} back groups"]
    if any(re.fullmatch(r"d\d{3}", key) for key in config.overrides):
        lines.append(
            "Designs are numbered afresh on every `group`: check that each override keyed by a "
            "design id (dNNN) still points at the design it was written for."
        )
    lines.append("design contact sheets: " + " ".join(ws.rel(s) for s in design_sheets))
    lines.append("back contact sheet: " + (ws.rel(back_sheet) if back_sheet else "None"))
    return "\n".join(lines)


def _design_sheets(ws: Workspace, designs: dict[str, list[str]]) -> list[Path]:
    entries = [
        (f"{design} x{len(members)}", Image.open(ws.item_dir(members[0]) / "front.png"))
        for design, members in designs.items()
    ]
    return [
        contact_sheet(
            entries[i : i + DESIGN_SHEET_ITEMS],
            ws.work / "contact" / f"designs_{i // DESIGN_SHEET_ITEMS + 1}.png",
        )
        for i in range(0, len(entries), DESIGN_SHEET_ITEMS)
    ]


def _back_sheet(ws: Workspace, backs: dict[str, list[str]]) -> Path | None:
    if not backs:
        return None
    entries = [
        (f"{back} x{len(members)}", Image.open(ws.item_dir(members[0]) / "back.png"))
        for back, members in backs.items()
    ]
    return contact_sheet(entries, ws.work / "contact" / "backs.png")
