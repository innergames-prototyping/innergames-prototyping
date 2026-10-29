#!/usr/bin/env nix-shell
#!nix-shell -i python3 -p "python3.withPackages(p: [p.pillow p.numpy p.scipy p.jsonschema])" poppler-utils tesseract
"""Extract a tabletop game's rules text and components from its PDFs.

Layout, cropping, de-duplication, voting and checks are done here in code. Reading is done by
independent `claude -p` calls (Haiku by default) that each see one component or one rules region.

    extract.py render <pdf>...      page renders + small previews + text layer
    extract.py crop                 find every item on the configured pages (any shape), cut it out,
                                    or take items that come as one image file each
    extract.py lines <page>         cut lines and gutters on a page, for a `grid` layout
    extract.py group                group pixel-identical fronts (designs) and near-identical backs
    extract.py orient               read which way each design's text runs, and list what to turn
    extract.py read                 read every design until every value has a majority, and every
                                    rules region as `rules` does, in one queue; designs read sideways
                                    are not read further
    extract.py check                vote, apply overrides, run the consistency checks
    extract.py preview              draw the rules regions on their pages and flag text outside them
    extract.py rules                transcribe every rules region until every word has a majority
                                    (or one read matches Tesseract's), and proofread it for
                                    misspellings the transcription corrected
    extract.py assemble             write <work>/components.json (every item and where it came
                                    from), <output>/rules.txt, <output>/components.json and
                                    <work>/review.html (rules regions beside their text)
    extract.py cost                 total cost of all `claude -p` calls so far
    extract.py export [<in> <out>]  <work>/components.json without its paper trail, identical
                                    items merged: what assemble writes to <output>/components.json

Everything lives in --work (default ./work); the config is <work>/config.json.
"""
import argparse
import base64
import difflib
import hashlib
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict, deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

import numpy as np
from scipy import ndimage
from PIL import Image, ImageDraw

SKILL_DIR = Path(__file__).resolve().parent
MAX_SIDE = 1568  # the API downsizes larger images anyway
PREVIEW_SIDE = 1400

DIRECTIONS = ["upright", "bottom to top", "top to bottom", "upside down", "no text"]
TURN = {"bottom to top": 90, "top to bottom": 270, "upside down": 180}  # clockwise turn that makes it upright
ORIENTATION_NEXT = (
    "Designs read sideways were read only once. Check one crop per ORIENTATION line. If it is really not "
    "upright, fix `rotate` / `rotate_items` and run `crop && group`. Positions turn with the item (a strip "
    "on the left of a sideways card runs along the top of the upright one), so then open one turned crop of "
    "each kind named and rewrite every position in that kind's description and fields for the turned crop. "
    "Then run `read`; reads of unchanged crops are kept. If a crop is upright, record "
    "`{\"set\": {\"orientation\": \"upright\"}, \"reason\": \"...\"}` for its design in `overrides` and run `read` again.")
ONLY_THE_IMAGE = ("Decide only from the image: never guess, and never set a value to agree with the rules or a count "
                  "check. If the image doesn't settle it, leave it.")
HELP = {
    "conflict": "CONFLICT is a value without a majority. Record what the image shows in `overrides`: "
                "`\"d042\": {\"set\": {\"fields.gold\": 3}, \"reason\": \"counted 3 filled circles at full size\"}`. "
                "Keys are `kind`, `title`, `text`, `fields.<name>`; use an item key (`work/items/<key>`) instead of a "
                "design id when only one copy differs. Override `kind` only for a design or two that readers misjudge, "
                "and then also set its fields that stay in CONFLICT. " + ONLY_THE_IMAGE +
                " `assemble --force` marks what is left `low` confidence.",
    "text": "TEXT UNCERTAIN is text readers disagree on, often illegible decorative print. Set the text from the image "
            "with a `text` override, or drop the illegible part, with the reason.",
    "spelling": "SPELLING is a misspelled word a reader saw that the voted title or text has corrected. It is usually a "
                "real typo: if the image shows it, override `title` or `text` as printed.",
    "back": "Identical backs usually mean one kind. If the mix is real, record it in `back_kinds` "
            "(`{\"b02\": [\"kind_a\", \"kind_b\"]}`).",
    "count": "On a count mismatch, the total is the files' items plus `rules_items`. Re-check the designs involved at "
             "full size and fix only what the image shows. If the files really differ from the rules, leave it and say "
             "so in `extraction_notes`. A mismatch caused by `rules_items` is fixed there, not by overrides.",
    "no_majority": "NO MAJORITY includes passages only some readers transcribed: readers drop text far more often than "
                   "they invent it, so check the image before accepting the shorter version. Fix rules text with "
                   "`rules_fixes` (`{\"find\": \"...\", \"replace\": \"...\"}`, applied to the assembled text), with "
                   "`find` long enough to match only the intended place.",
    "rules_spelling": "SPELLING here is a misspelled word proofreaders saw that the transcription has corrected: usually "
                      "a real typo, almost always when Tesseract also reads it as printed. Open the region image and "
                      "restore it with `rules_fixes` if the image shows it; never dismiss one without looking.",
}

SYSTEM = (
    "You transcribe printed tabletop-game material exactly as printed. You report only what you "
    "can see in the images. You never use knowledge of the game, never guess, never correct "
    "spelling and never fill in what would make sense."
)


# ---------------------------------------------------------------- helpers

def load_json(path, default=None):
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else default


def save_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=1, ensure_ascii=False))


def page_path(work, stem, page):
    return work / "pages" / f"{stem}_p{page}.png"


def item_key(stem, page, row, col):
    return f"{stem}_p{page}_r{row:02d}_c{col:02d}"


def png_b64(img):
    if max(img.size) > MAX_SIDE:
        img = img.copy()
        img.thumbnail((MAX_SIDE, MAX_SIDE))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def ask(images, prompt, schema=None, model="haiku", tries=3):
    """One independent, tool-less `claude -p` call. Returns (structured output or text, cost)."""
    content = [{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": png_b64(im)}}
               for im in images]
    content.append({"type": "text", "text": prompt})
    msg = json.dumps({"type": "user", "message": {"role": "user", "content": content}})
    cmd = ["claude", "-p", "--model", model, "--safe-mode", "--tools", "", "--strict-mcp-config",
           "--no-session-persistence", "--system-prompt", SYSTEM, "--input-format", "stream-json",
           "--output-format", "stream-json", "--verbose"]
    if schema:
        cmd += ["--json-schema", json.dumps(schema)]
    cost, err, failures, pause = 0.0, None, 0, 30
    while failures < tries:
        try:
            p = subprocess.run(cmd, input=msg + "\n", capture_output=True, text=True, timeout=600)
        except subprocess.TimeoutExpired:
            err, failures = "timeout", failures + 1
            continue
        results = [json.loads(l) for l in p.stdout.splitlines() if l.startswith('{"') and '"type":"result"' in l]
        if not results:
            err, failures = (p.stderr or p.stdout)[-500:], failures + 1
            continue
        r = results[-1]
        cost += r.get("total_cost_usd") or 0
        out = r.get("structured_output") if schema else r.get("result")
        if not r.get("is_error") and out is not None:
            return out, cost
        err = r.get("result") or r.get("subtype")
        if r.get("api_error_status") == 429 and pause <= 480:
            # Rate limited even after claude's own retries: wait without using up a try.
            time.sleep(pause)
            pause *= 2
            continue
        failures += 1
    raise RuntimeError(f"claude -p failed: {err}")


def run_queue(start, jobs):
    """Runs reads `jobs` at a time. `start` holds (task, then) pairs: `task` runs in a worker, then
    `then(result)` runs in this thread (result None if the task failed) and returns follow-up pairs.
    Follow-ups run before pairs not yet started, so each design or region finishes as soon as its
    own reads agree, instead of everything waiting for the slowest read of a round."""
    pending, running = deque(start), {}
    with ThreadPoolExecutor(jobs) as ex:
        while pending or running:
            while pending and len(running) < jobs:
                task, then = pending.popleft()
                running[ex.submit(task)] = then
            done, _ = wait(running, return_when=FIRST_COMPLETED)
            for f in done:
                then = running.pop(f)
                try:
                    result = f.result()
                except RuntimeError as e:
                    print(e, file=sys.stderr, flush=True)
                    result = None
                pending.extendleft(reversed(then(result)))


def ink_mask(arr, bg):
    return np.abs(arr.astype(np.int16) - bg).max(-1) > 40


def page_background(arr):
    border = np.concatenate([arr[0], arr[-1], arr[:, 0], arr[:, -1]])
    return np.median(border, axis=0).astype(np.int16)


def trim(img, bg=(255, 255, 255), min_frac=0.01):
    """Crop to the connected ink regions that are not small, which drops cut marks, dashes and
    thin lines in the margins. Returns None for an empty cell."""
    ink = ink_mask(np.asarray(img.convert("RGB")), np.array(bg, np.int16))
    if ink.mean() < min_frac:
        return None
    labels, _ = ndimage.label(ink, structure=np.ones((3, 3)))
    sizes = np.bincount(labels.ravel())
    boxes = [s for n, s in enumerate(ndimage.find_objects(labels), 1) if sizes[n] >= 0.005 * ink.size]
    if not boxes:
        return None
    y0, y1 = min(b[0].start for b in boxes), max(b[0].stop for b in boxes)
    x0, x1 = min(b[1].start for b in boxes), max(b[1].stop for b in boxes)
    return img.crop((x0, y0, x1, y1))


def rotate(img, deg):
    return img.rotate(-deg, expand=True) if deg % 360 else img


def contact_sheet(entries, out, width=1600, thumb=150):
    """entries: [(label, image)]. Thumbnails in a grid, each labelled underneath."""
    per_row = max(1, width // (thumb + 10))
    rows = (len(entries) + per_row - 1) // per_row
    sheet = Image.new("RGB", (per_row * (thumb + 10), rows * (thumb + 26)), "white")
    d = ImageDraw.Draw(sheet)
    for i, (label, im) in enumerate(entries):
        t = im.copy()
        t.thumbnail((thumb, thumb))
        x, y = (i % per_row) * (thumb + 10) + 5, (i // per_row) * (thumb + 26) + 3
        d.text((x, y), label, fill="red")
        sheet.paste(t, (x, y + 14))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return out




# ---------------------------------------------------------------- render / lines / preview

def cmd_render(a):
    work = Path(a.work)
    for pdf in a.pdfs:
        pdf = Path(pdf)
        info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
        pages = int(re.search(r"Pages:\s+(\d+)", info).group(1))
        size = re.search(r"Page size:\s+(.*)", info).group(1)
        (work / "pages").mkdir(parents=True, exist_ok=True)
        (work / "preview").mkdir(parents=True, exist_ok=True)
        (work / "text").mkdir(parents=True, exist_ok=True)
        for n in range(1, pages + 1):
            out = page_path(work, pdf.stem, n)
            subprocess.run(["pdftoppm", "-r", str(a.dpi), "-f", str(n), "-l", str(n), "-png", "-singlefile",
                            str(pdf), str(out.with_suffix(""))], check=True)
            im = Image.open(out)
            small = im.copy()
            small.thumbnail((PREVIEW_SIDE, PREVIEW_SIDE))
            small.save(work / "preview" / out.name)
            print(f"{pdf.name} page {n}: {im.size[0]}x{im.size[1]} px at {a.dpi} dpi ({size}) -> {out}")
        subprocess.run(["pdftotext", "-layout", str(pdf), str(work / "text" / f"{pdf.stem}.txt")])
    print(f"Previews (max {PREVIEW_SIDE} px) in {work / 'preview'}; text layer in {work / 'text'}.")


def longest_runs(cont):
    """Longest run of True down each column of a 2-D boolean array."""
    run = np.zeros(cont.shape[1], np.int32)
    best = np.zeros(cont.shape[1], np.int32)
    for row in cont:
        run = (run + 1) * row
        np.maximum(best, run, out=best)
    return best


def clusters(mask):
    out, start = [], None
    for i, m in enumerate(list(mask) + [False]):
        if m and start is None:
            start = i
        elif not m and start is not None:
            out.append(((start + i - 1) / 2, i - start))
            start = None
    return out


def cmd_lines(a):
    work = Path(a.work)
    path = Path(a.page) if Path(a.page).exists() else work / "pages" / f"{a.page}.png"
    arr = np.asarray(Image.open(path).convert("RGB"))
    result = {"page": str(path), "width": arr.shape[1], "height": arr.shape[0]}
    for name, a2 in (("x", arr), ("y", arr.transpose(1, 0, 2))):
        # Full resolution, in blocks: cut lines are often 1 px wide and vanish when downscaled.
        frac, ink = [], []
        for i in range(0, a2.shape[1], 512):
            b = a2[:, i:i + 512].astype(np.int16)
            nw = b.min(-1) < 200
            cont = nw[1:] & nw[:-1] & (np.abs(b[1:] - b[:-1]).sum(-1) < 40)
            frac.append(longest_runs(cont) / cont.shape[0])
            ink.append(nw.mean(0))
        frac, ink = np.concatenate(frac), np.concatenate(ink)
        lines = [(round(p), w) for p, w in clusters(frac >= a.min_frac)]
        gaps = [(round(p), w) for p, w in clusters(ink < 0.003) if w >= 8]
        result[f"{name}_lines"] = [{"pos": p, "width": w} for p, w in lines]
        result[f"{name}_gaps"] = [{"pos": p, "width": w} for p, w in gaps]
    print(json.dumps(result, indent=1))
    print("x_lines/y_lines: straight lines spanning at least "
          f"{a.min_frac:.0%} of the page (cut lines); *_gaps: blank gutters. Positions in page-render pixels.",
          file=sys.stderr)


def region_box(box, size):
    """[x0, y0, x1, y1] in page-render pixels, or as fractions of the page if all values are <= 1."""
    x0, y0, x1, y1 = box
    if max(box) <= 1:
        x0, x1, y0, y1 = x0 * size[0], x1 * size[0], y0 * size[1], y1 * size[1]
    return tuple(int(round(v)) for v in (x0, y0, x1, y1))


def load_config(a):
    cfg = load_json(Path(a.work) / "config.json")
    if cfg is None:
        sys.exit(f"missing {Path(a.work) / 'config.json'}")
    return cfg


def detect_segment(page, L):
    """Every separate object on the page, whatever its shape. Works on a reduced copy. Thin lines
    (cut lines, crop marks, dashes) are dropped: an opening finds the solid cores, and only ink close
    to a core is kept, so an object keeps its own thin outlines. Nearby parts of
    one object are joined by a closing and holes are filled. Returns [(bbox, mask)] at full resolution."""
    f = L.get("scale", 4)
    small = np.asarray(page.reduce(f))
    ink = ink_mask(small, page_background(small))
    k = max(1, round(L.get("line_width", 8) / f))
    cores = ndimage.binary_opening(ink, structure=np.ones((k + 1, k + 1)))
    ink &= ndimage.binary_dilation(cores, iterations=k + 1)
    m = max(1, round(L.get("merge", 4) / f))
    ink = ndimage.binary_closing(ink, structure=np.ones((m, m)), iterations=1)
    ink = ndimage.binary_fill_holes(ink)
    labels, _ = ndimage.label(ink)
    sizes = np.bincount(labels.ravel())
    out = []
    pad = k + 2
    for n, (ys, xs) in enumerate(ndimage.find_objects(labels), 1):
        if sizes[n] < L.get("min_area", 0.0005) * ink.size:
            continue
        y0, x0 = max(0, ys.start - pad), max(0, xs.start - pad)
        y1, x1 = min(ink.shape[0], ys.stop + pad), min(ink.shape[1], xs.stop + pad)
        # Grown by more than the opening removed, so thin outer outlines are not clipped.
        mask = ndimage.binary_dilation(labels[y0:y1, x0:x1] == n, iterations=pad)
        mask = np.kron(mask, np.ones((f, f), bool))
        out.append(((x0 * f, y0 * f, x1 * f, y1 * f), mask))
    return out


def detect_grid(page, L):
    if "xs" in L:
        xs, ys = L["xs"], L["ys"]
    else:
        x0, y0, x1, y1 = region_box(L["box"], page.size)
        xs = [x0 + (x1 - x0) * c / L["cols"] for c in range(L["cols"] + 1)]
        ys = [y0 + (y1 - y0) * r / L["rows"] for r in range(L["rows"] + 1)]
    i = L.get("inset", 4)
    return [((round(xs[c]) + i, round(ys[r]) + i, round(xs[c + 1]) - i, round(ys[r + 1]) - i), None, r, c)
            for r in range(len(ys) - 1) for c in range(len(xs) - 1)]


def assign_rows(found):
    """Row = band of similar centre height (offset hex rows included), col = order within the row."""
    found = sorted(found, key=lambda t: (t[0][1] + t[0][3]) / 2)
    if not found:
        return []
    height = np.median([b[3] - b[1] for b, _ in found])
    rows, cur = [], [found[0]]
    for t in found[1:]:
        if (t[0][1] + t[0][3]) / 2 - np.mean([(b[1] + b[3]) / 2 for b, _ in cur]) > height / 2:
            rows.append(cur)
            cur = []
        cur.append(t)
    rows.append(cur)
    return [(b, m, r, c) for r, row in enumerate(rows) for c, (b, m) in enumerate(sorted(row, key=lambda t: t[0][0]))]


def detect(page, L):
    method = L.get("method", "segment")
    if method == "grid":
        return detect_grid(page, L)
    if method == "boxes":
        return assign_rows([(region_box(b, page.size), None) for b in L["boxes"]])
    return assign_rows(detect_segment(page, L))


def cut(page, box, mask):
    img = page.crop(box)
    if mask is None:
        return trim(img)
    arr = np.asarray(img).copy()
    arr[~mask[:arr.shape[0], :arr.shape[1]]] = 255
    return trim(Image.fromarray(arr))


def crop_files(work, L, n):
    """Items that come as one image file each. The part of the file name matched by the `*` in
    `fronts` names the item, and finds its back through the `*` in `backs`."""
    pre, _, post = L["fronts"].partition("*")
    bpre, _, bpost = L.get("backs", "").partition("*")
    rot = L.get("rotate_items", {})
    entries, thumbs, no_back = [], [], []
    for path in sorted(Path().glob(L["fronts"])):
        name = str(path)[len(pre):len(str(path)) - len(post)]
        if name in L.get("skip", []):
            continue
        deg = rot.get(name, L.get("rotate", 0))
        key = re.sub(r"[^\w.-]", "_", name)
        d = work / "items" / key
        d.mkdir(parents=True)
        front = rotate(Image.open(path).convert("RGB"), deg)
        front.save(d / "front.png")
        if L.get("backs"):
            if Path(bpre + name + bpost).exists():
                rotate(Image.open(bpre + name + bpost).convert("RGB"), deg).save(d / "back.png")
            else:
                no_back.append(name)
        entries.append({"key": key, "label": name, "file": str(path), "page": 1, "rotate": deg})
        thumbs.append((name, front))
    sheets = [contact_sheet(thumbs[i:i + 100], work / "contact" / f"files{n}_{i // 100 + 1}.png") for i in range(0, len(thumbs), 100)]
    print(f"{L['fronts']}: {len(entries)} items\n    contact sheets: {' '.join(map(str, sheets))}")
    if no_back:
        print(f"    no back found for: {' '.join(no_back)}")
    return entries


def cmd_crop(a):
    work, cfg = Path(a.work), load_config(a)
    if (work / "items").exists():
        shutil.rmtree(work / "items")
    manifest = []
    for n, L in enumerate(cfg["layouts"], 1):
        if L.get("method") == "files":
            manifest += crop_files(work, L, n)
            continue
        stem = Path(L["file"]).stem
        front = Image.open(page_path(work, stem, L["page"])).convert("RGB")
        back = Image.open(page_path(work, stem, L["back_page"])).convert("RGB") if L.get("back_page") else None
        found = [t for t in detect(front, L) if f"r{t[2]}c{t[3]}" not in L.get("skip", [])]
        row_len = Counter(r for _, _, r, _ in found)
        n_rows = max(row_len, default=-1) + 1
        mirror = L.get("back_mirror", "horizontal")
        overlay = front.copy()
        overlay.thumbnail((PREVIEW_SIDE * 2, PREVIEW_SIDE * 2))
        f = overlay.width / front.width
        draw = ImageDraw.Draw(overlay)
        thumbs = []
        for box, mask, r, c in found:
            cell = cut(front, box, mask)
            if cell is None:
                continue
            rot = L.get("rotate_items", {})
            deg = rot.get(f"r{r}c{c}", rot.get(f"r{r}", L.get("rotate", 0)))
            key = item_key(stem, L["page"], r, c)
            d = work / "items" / key
            d.mkdir(parents=True)
            rotate(cell, deg).save(d / "front.png")
            entry = {"key": key, "file": L["file"], "page": L["page"], "row": r, "col": c, "rotate": deg, "box": box}
            if back is not None:
                # The back of an item sits at the mirrored position, with a mirrored outline.
                W, H = back.size
                if mirror == "horizontal":
                    bbox, bm, br, bc = (W - box[2], box[1], W - box[0], box[3]), mask[:, ::-1] if mask is not None else None, r, row_len[r] - 1 - c
                elif mirror == "vertical":
                    bbox, bm, br, bc = (box[0], H - box[3], box[2], H - box[1]), mask[::-1] if mask is not None else None, n_rows - 1 - r, c
                else:
                    bbox, bm, br, bc = box, mask, r, c
                bcell = cut(back, bbox, bm)
                if bcell is not None:
                    rotate(bcell, deg).save(d / "back.png")
                    entry |= {"back_page": L["back_page"], "back_row": br, "back_col": bc}
            manifest.append(entry)
            thumbs.append((f"r{r}c{c}", rotate(cell, deg)))
            draw.rectangle([box[0] * f, box[1] * f, box[2] * f, box[3] * f], outline="red", width=2)
            draw.text((box[0] * f + 4, box[1] * f + 3), f"r{r}c{c}", fill="red")
        ov = work / "preview" / f"items_{stem}_p{L['page']}.png"
        overlay.save(ov)
        cs = contact_sheet(thumbs, work / "contact" / f"{stem}_p{L['page']}.png")
        print(f"{stem} p{L['page']}: {len(thumbs)} items in {len(row_len)} rows {dict(sorted(row_len.items()))}\n"
              f"    outlines on the page: {ov}\n    contact sheet: {cs}")
        areas = {f"r{r}c{c}": (b[2] - b[0]) * (b[3] - b[1]) for b, _, r, c in found}
        med = np.median(list(areas.values())) if areas else 0
        odd = {k: round(v / med, 2) for k, v in areas.items() if v < med / 3 or v > med * 3}
        if odd:
            print(f"    size outliers (area / median): {odd} - split or merged objects? "
                  "Check the outlines; adjust merge/line_width or use a grid or boxes layout.")
    save_json(work / "items.json", manifest)
    print(f"{len(manifest)} items")


def uncovered_text(img, boxes, min_glyphs=15):
    """Blocks of print outside every box: glyph-sized marks grouped into lines and paragraphs, on a
    plain background (texture in pictures has little of it)."""
    arr = np.asarray(img.convert("RGB")).astype(np.int16)
    ink = np.abs(arr - page_background(arr)).max(-1) > 80
    H = arr.shape[0]
    lab, _ = ndimage.label(ink)
    objs = ndimage.find_objects(lab)
    if not objs:
        return []
    hs = np.array([s[0].stop - s[0].start for s in objs])
    ws = np.array([s[1].stop - s[1].start for s in objs])
    cy = np.array([(s[0].start + s[0].stop) // 2 for s in objs])
    cx = np.array([(s[1].start + s[1].stop) // 2 for s in objs])
    covered = np.zeros(ink.shape, bool)
    for b in boxes:
        x0, y0, x1, y1 = region_box(b, img.size)
        covered[y0:y1, x0:x1] = True
    keep = (hs >= 0.003 * H) & (hs <= 0.03 * H) & (ws <= 4 * hs) & ~covered[cy, cx]
    if not keep.any():
        return []
    glyph = np.isin(lab, np.flatnonzero(keep) + 1)
    g = int(np.median(hs[keep]))
    blocks, _ = ndimage.label(ndimage.maximum_filter(glyph, size=(g, 2 * g)))
    counts = np.bincount(blocks[cy[keep], cx[keep]], minlength=blocks.max() + 1)
    plain = ~ndimage.maximum_filter(ink, size=7)
    W = arr.shape[1]
    return [([round(sl[1].start / W, 3), round(sl[0].start / H, 3), round(sl[1].stop / W, 3), round(sl[0].stop / H, 3)], int(counts[i]))
            for i, sl in enumerate(ndimage.find_objects(blocks), 1) if counts[i] >= min_glyphs and plain[sl].mean() >= 0.3]


def rules_pages(work, cfg):
    """Every page of the files that have rules regions, except component pages."""
    stems = {Path(r["file"]).stem for r in cfg.get("rules_regions", [])}
    components = {(Path(l["file"]).stem, p) for l in cfg.get("layouts", []) if "page" in l for p in (l["page"], l.get("back_page"))}
    pages = []
    for p in sorted(work.glob("pages/*.png")):
        stem, _, n = p.stem.rpartition("_p")
        if stem in stems and n.isdigit() and (stem, int(n)) not in components:
            pages.append((stem, int(n)))
    return sorted(pages, key=lambda x: (x[0], x[1]))


def coverage(work, cfg):
    """Text blocks outside every rules region and every `rules_excluded` box, per page."""
    found = {}
    for stem, page in rules_pages(work, cfg):
        same = lambda e: Path(e["file"]).stem == stem and e["page"] == page
        excluded = [e for e in cfg.get("rules_excluded", []) if same(e)]
        if any("box" not in e for e in excluded):
            continue
        boxes = [r["box"] for r in cfg.get("rules_regions", []) if same(r)] + [e["box"] for e in excluded]
        blocks = uncovered_text(Image.open(page_path(work, stem, page)), boxes)
        if blocks:
            found[(stem, page)] = blocks
    return found


def cmd_preview(a):
    """Rules regions drawn on their pages, with text left outside them."""
    work, cfg = Path(a.work), load_config(a)
    uncovered = coverage(work, cfg)
    for stem, page in rules_pages(work, cfg):
        full = Image.open(page_path(work, stem, page))
        im = full.convert("RGB")
        im.thumbnail((PREVIEW_SIDE, PREVIEW_SIDE))
        f = im.width / full.width
        d = ImageDraw.Draw(im)
        same = lambda e: Path(e["file"]).stem == stem and e["page"] == page
        for i, r in enumerate(cfg.get("rules_regions", [])):
            if same(r):
                x0, y0, x1, y1 = region_box(r["box"], full.size)
                d.rectangle([x0 * f, y0 * f, x1 * f, y1 * f], outline="blue", width=3)
                d.text((x0 * f + 5, y0 * f + 5), f"#{i}", fill="blue")
        for e in cfg.get("rules_excluded", []):
            if same(e) and "box" in e:
                x0, y0, x1, y1 = region_box(e["box"], full.size)
                d.rectangle([x0 * f, y0 * f, x1 * f, y1 * f], outline="gray", width=3)
        for n, (box, _) in enumerate(uncovered.get((stem, page), [])):
            x0, y0, x1, y1 = region_box(box, full.size)
            d.rectangle([x0 * f, y0 * f, x1 * f, y1 * f], outline="red", width=3)
            d.text((x0 * f + 5, y0 * f + 5), f"u{n}", fill="red")
        out = work / "preview" / f"regions_{stem}_p{page}.png"
        im.save(out)
        print(out)
    for (stem, page), blocks in uncovered.items():
        print(f"UNCOVERED {stem} page {page}: text outside every region, in red on regions_{stem}_p{page}.png: "
              + "; ".join(f"u{n} {box} ({count} letters)" for n, (box, count) in enumerate(blocks)))
    if uncovered:
        print("Cover each UNCOVERED block with a rules region, or list it in `rules_excluded` with the reason (leave "
              "out `box` to exclude a whole page, such as a cover). `assemble` refuses while any are left.")
    print("This check misses page numbers, very short lines, and light text on dark or coloured bands: check the "
          "previews for headings yourself. No line of text may be cut by a region edge.")
    return uncovered


SHIFT_POOL = ThreadPoolExecutor(os.cpu_count())


def similar(a, b, shift=3, tol=0.001, block=12, block_tol=0.05):
    """Pixel comparison of two RGB arrays, allowing a small misalignment. Identical only if few
    pixels differ overall AND no small block differs much: a single changed symbol (a pip, a sign) is
    a tiny fraction of the whole item but fills a block. Colour, not grey: printed reds and greens
    can have the same brightness."""
    if abs(a.shape[0] - b.shape[0]) > 2 * shift or abs(a.shape[1] - b.shape[1]) > 2 * shift:
        return False, 1.0
    h, w = min(a.shape[0], b.shape[0]) - 2 * shift, min(a.shape[1], b.shape[1]) - 2 * shift
    ref = a[shift:shift + h, shift:shift + w]
    diffs = SHIFT_POOL.map(lambda s: np.abs(ref - b[s[0]:s[0] + h, s[1]:s[1] + w]).max(-1) > 80,
                           [(dy, dx) for dy in range(2 * shift + 1) for dx in range(2 * shift + 1)])
    best = min(diffs, key=lambda d: d.mean())
    hb, wb = h // block * block, w // block * block
    worst_block = best[:hb, :wb].reshape(hb // block, block, wb // block, block).mean((1, 3)).max()
    return best.mean() <= tol and worst_block <= block_tol, float(best.mean())


def differs_small(a, b, shift=1, frac=0.01):
    """Cheap first test on 1/8-size images: True only when the items clearly differ. Identical prints
    differ in no pixel at this size; items that differ only in a small symbol look identical here and
    are left to `similar`."""
    if abs(a.shape[0] - b.shape[0]) > 2 * shift or abs(a.shape[1] - b.shape[1]) > 2 * shift:
        return True
    h, w = min(a.shape[0], b.shape[0]) - 2 * shift, min(a.shape[1], b.shape[1]) - 2 * shift
    if h < 1 or w < 1:
        return False
    ref = a[shift:shift + h, shift:shift + w]
    return min((np.abs(ref - b[dy:dy + h, dx:dx + w]).max(-1) > 80).mean()
               for dy in range(2 * shift + 1) for dx in range(2 * shift + 1)) > frac


def cluster(paths, **tol):
    imgs = {}
    for k, p in paths.items():
        im = Image.open(p).convert("RGB")
        imgs[k] = (np.asarray(im.resize((im.width // 2, im.height // 2))).astype(np.int16),
                   np.asarray(im.resize((16, 16))).astype(np.int16),
                   np.asarray(im.resize((max(1, im.width // 8), max(1, im.height // 8)))).astype(np.int16))
    groups = []
    # numpy releases the GIL, so threads compare against several groups at once; the first matching
    # group in order still wins, as in a sequential search.
    with ThreadPoolExecutor(os.cpu_count()) as pool:
        for k, (arr, sig, small) in imgs.items():
            cands = [g for g in groups if np.abs(sig - imgs[g[0]][1]).mean() < 25
                     and not differs_small(imgs[g[0]][2], small)]
            hits = pool.map(lambda g: similar(imgs[g[0]][0], arr, **tol)[0], cands)
            match = next((g for g, hit in zip(cands, hits) if hit), None)
            if match:
                match.append(k)
            else:
                groups.append([k])
    return groups


def cmd_group(a):
    work, cfg = Path(a.work), load_config(a)
    items = load_json(work / "items.json")
    separate = set(cfg.get("separate", []))
    fronts = {i["key"]: work / "items" / i["key"] / "front.png" for i in items if i["key"] not in separate}
    designs = cluster(fronts) + [[k] for k in sorted(separate)]
    # Backs only drive a consistency check, so near-identical is close enough.
    backs = cluster({i["key"]: work / "items" / i["key"] / "back.png" for i in items
                     if (work / "items" / i["key"] / "back.png").exists()}, tol=0.02, block_tol=0.4)
    out = {"designs": {f"d{n:03d}": g for n, g in enumerate(designs, 1)},
           "backs": {f"b{n:02d}": g for n, g in enumerate(backs, 1)}}
    save_json(work / "groups.json", out)
    entries = [(f"{d} x{len(g)}", Image.open(work / "items" / g[0] / "front.png")) for d, g in out["designs"].items()]
    sheets = [contact_sheet(entries[i:i + 60], work / "contact" / f"designs_{i // 60 + 1}.png") for i in range(0, len(entries), 60)]
    bsheet = contact_sheet([(f"{b} x{len(g)}", Image.open(work / "items" / g[0] / "back.png")) for b, g in out["backs"].items()],
                           work / "contact" / "backs.png") if out["backs"] else None
    print(f"{len(items)} items -> {len(designs)} designs, {len(backs)} back groups")
    if any(re.fullmatch(r"d\d{3}", k) for k in cfg.get("overrides", {})):
        print("Designs are numbered afresh on every `group`: check that each override keyed by a design id (dNNN) "
              "still points at the design it was written for.")
    print("design contact sheets:", *map(str, sheets))
    print("back contact sheet:", bsheet)


# ---------------------------------------------------------------- read / check

def field_schema(f):
    t = f["type"]
    if t == "integer":
        return {"type": ["integer", "null"]}
    if t == "enum":
        return {"enum": f["enum_values"] + [None]}
    if t == "list":
        return {"type": ["array", "null"], "items": {"type": ["string", "integer"]}}
    return {"type": ["string", "null"]}


def reader_schema(cfg):
    kinds = cfg["kinds"]
    return {
        "type": "object", "additionalProperties": False,
        "required": ["observations", "text_direction", "kind", "title", "fields", "mismatch", "text", "misspelled",
                     "unreadable"],
        "properties": {
            "observations": {"type": "string"},
            "text_direction": {"enum": DIRECTIONS},
            "kind": {"enum": [k["id"] for k in kinds] + ["other"]},
            "title": {"type": ["string", "null"]},
            "fields": {
                "type": "object", "additionalProperties": False, "required": [k["id"] for k in kinds],
                "properties": {k["id"]: {
                    "type": ["object", "null"], "additionalProperties": False,
                    "required": [f["name"] for f in k.get("fields", [])],
                    "properties": {f["name"]: field_schema(f) for f in k.get("fields", [])}} for k in kinds}},
            "text": {"type": ["string", "null"]},
            "misspelled": {"type": "array", "items": {"type": "string"}},
            "mismatch": {"type": "string"},
            "unreadable": {"type": "string"},
        },
    }


def reader_prompt(cfg, has_back):
    lines = ["Image 1 is the front of ONE physical game component" + (", image 2 is its back." if has_back else "."),
             "", "Possible kinds of component:"]
    for k in cfg["kinds"]:
        lines.append(f"- kind `{k['id']}` ({k['name']}): {k.get('description', '')}")
        for f in k.get("fields", []):
            ev = f" Allowed values: {', '.join(f['enum_values'])}." if f["type"] == "enum" else ""
            lines.append(f"    - field `{f['name']}` ({f['type']}): {f['description']}{ev}")
    lines += [
        "- kind `other`: it matches none of the above.",
        "",
        "Fill in the JSON:",
        "- observations: first, briefly, for the fields of this kind only: where each value is printed, "
        "and for every counted symbol, each one with its position, counted one by one; tell symbol types "
        "apart (filled or hollow, colour, shape). Don't describe pictures or decoration.",
        "- text_direction: which way the main printed text (title, labels) runs in image 1 as you see it: "
        "'upright', 'bottom to top' (lines run upwards), 'top to bottom' (lines run downwards), "
        "'upside down', or 'no text'.",
        "- kind: which kind this is, judged only from what is printed.",
        "- fields: fill only the object for that kind, using your observations; set every other kind's "
        "object to null. Use null for a value that is not printed or cannot be read.",
        "- mismatch: anything in the description of the kind you chose, or of its fields, that does not match "
        "image 1 as you see it, for example a strip described on the left that is printed along the top, or "
        "symbols that are not where a field says they are; empty string if it all matches.",
        "- title: the printed name on the front (image 1), exactly as printed, letter by letter, including spelling mistakes and "
        "typos (a later step looks for these, so a corrected word is an error); capitals and punctuation "
        "as printed; null if none.",
        "- text: all other printed text on the front, verbatim and letter by letter in the same way, with dashes "
        "(- – —) and quotes (' ’ \" “ ”) as printed, lines joined with ' / '. Leave out the title, "
        "values already recorded in fields, and illegible decorative fine "
        "print. null if none.",
        "- misspelled: every word in the title or text that is printed with a spelling mistake or typo, "
        "copied exactly as printed; [] if none.",
        "- unreadable: anything you could not read, and why; empty string if none.",
    ] + (["Image 2 only helps recognise the kind: take no title or text from the back."] if has_back else [])
    return "\n".join(lines)


def vote(values, key=lambda v: json.dumps(v, sort_keys=True)):
    """Winner if it has at least two votes and strictly more than any other value."""
    groups = defaultdict(list)
    for v in values:
        groups[key(v)].append(v)
    ranked = sorted(groups.values(), key=len, reverse=True)
    if ranked and len(ranked[0]) >= 2 and (len(ranked) == 1 or len(ranked[0]) > len(ranked[1])):
        return True, Counter(map(json.dumps, ranked[0])).most_common(1)[0][0], len(ranked[0])
    return False, None, 0


def clean(out):
    """Undo reader quirks: HTML entities (&amp;) and the word null instead of a JSON null."""
    out = dict(out)
    for k in ("title", "text"):
        if isinstance(out.get(k), str):
            v = html.unescape(out[k]).strip()
            out[k] = None if v.lower() in ("", "null", "none") else v
    return out


def resolve(cfg, reads, kind=None):
    """Per-attribute majority over a design's reads. Returns (values, unsettled, text_settled).
    `kind` comes from an override; its fields are then voted among the reads that filled them in,
    so fields the override doesn't set still need a majority."""
    outs = [clean(r["output"]) for r in reads]
    if kind is None:
        ok, kind, _ = vote([o["kind"] for o in outs])
        if not ok:
            return {"votes": {"kind": [o["kind"] for o in outs]}}, ["kind"], False
        kind = json.loads(kind)
    same = [o for o in outs if o["kind"] == kind]
    if len(same) < 2:
        same = outs
    vals, unsettled, votes = {"kind": kind}, [], {}
    if kind == "other":
        unsettled.append("kind")
    ok, title, _ = vote([o["title"] for o in same], key=lambda v: re.sub(r"\s+", " ", v or "").strip())
    vals["title"] = json.loads(title) if ok else None
    if not ok:
        unsettled.append("title")
        votes["title"] = [o["title"] for o in same]
    fields = {}
    kdef = next((k for k in cfg["kinds"] if k["id"] == kind), {"fields": []})
    for f in kdef.get("fields", []):
        got = [o["fields"][kind].get(f["name"]) for o in same if o["fields"].get(kind) is not None]
        ok, v, _ = vote(got)
        fields[f["name"]] = json.loads(v) if ok else None
        if not ok:
            unsettled.append(f"fields.{f['name']}")
            votes[f"fields.{f['name']}"] = got
    vals["fields"] = fields
    texts = [o["text"] for o in same]
    ok, unresolved = True, []
    if any(texts):
        text, unresolved = merge_reads([t or "" for t in texts])
        vals["text"], ok = text.strip() or None, not unresolved
        if unresolved:
            votes["text"] = unresolved
    else:
        vals["text"] = None
    vals["votes"] = votes
    return vals, unsettled, ok


def image_id(work, key):
    h = hashlib.sha1()
    for name in ("front.png", "back.png"):
        if (work / "items" / key / name).exists():
            h.update((work / "items" / key / name).read_bytes())
    return h.hexdigest()[:12]


def kind_hashes(cfg):
    """What readers are told about each kind. `other` depends on every kind's description."""
    h = {k["id"]: hashlib.sha1(json.dumps([k.get(x) for x in ("name", "description", "fields")]).encode()).hexdigest()[:12]
         for k in cfg["kinds"]}
    h["other"] = hashlib.sha1(json.dumps(h, sort_keys=True).encode()).hexdigest()[:12]
    return h


def read_index(work, cfg):
    """Reads per item, keeping only reads of the item's current crop, made while the kind the reader
    chose was described as it is now: re-cropping, rotating, regrouping or rewriting a kind never
    reuses a read made under other conditions."""
    ids, index, hashes = {}, defaultdict(list), kind_hashes(cfg)
    for p in sorted((work / "reads").glob("*/*.json")):
        r = load_json(p)
        key = r["item"]
        if key not in ids:
            ids[key] = image_id(work, key) if (work / "items" / key).exists() else None
        if r.get("image") == ids[key] and r.get("kind_def", hashes.get(r["output"]["kind"])) == hashes.get(r["output"]["kind"]):
            index[key].append(r)
    return index


def design_reads(index, members):
    return [r for k in members for r in index.get(k, [])]


def orientation(reads):
    """The direction most reads see the text running in, if that is sideways or upside down."""
    c = Counter(r["output"].get("text_direction") for r in reads)
    n, d = max(((n, d) for d, n in c.items() if d in TURN), default=(0, None))
    return d if n * 2 > len(reads) else None


def read_as_text(kinds):
    return f" Read as: {', '.join(sorted(kinds))}." if kinds else ""


ORIENT_PROMPT = ("Image 1 is one printed game component. Which way does its main printed text (title, labels) run "
                 "in the image as you see it: 'upright', 'bottom to top' (lines run upwards), 'top to bottom' (lines "
                 "run downwards), 'upside down', or 'no text'?")
ORIENT_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["text_direction"],
                 "properties": {"text_direction": {"enum": DIRECTIONS}}}


def cmd_orient(a):
    """Two cheap reads per design, front only, asking only which way the text runs; a third where they
    differ. Reads are kept per crop image, so after turning items only the changed crops are read."""
    work = Path(a.work)
    groups = load_json(work / "groups.json")
    reads, spent = defaultdict(list), []
    for p in sorted((work / "orient").glob("*/*.json")):
        r = load_json(p)
        if (work / "items" / r["item"]).exists() and r["image"] == image_id(work, r["item"]):
            reads[r["item"]].append(r)
    design_reads = {d: [r for k in ms for r in reads[k]] for d, ms in groups["designs"].items()}
    nxt = {d: len(list((work / "orient").glob(f"{d}/*.json"))) for d in groups["designs"]}

    def task(design, n):
        def run():
            members = groups["designs"][design]
            key = members[n % len(members)]
            out, cost = ask([Image.open(work / "items" / key / "front.png")], ORIENT_PROMPT, ORIENT_SCHEMA, a.model)
            r = {"item": key, "image": image_id(work, key), "model": a.model, "output": out, "cost_usd": cost}
            save_json(work / "orient" / design / f"{n:02d}.json", r)
            return r
        return run

    def more(design):
        rs = design_reads[design]
        ok = vote([r["output"]["text_direction"] for r in rs])[0]
        if (len(rs) >= 2 and ok) or len(rs) >= 3:
            return []
        nxt[design] += 1
        return [(task(design, nxt[design] - 1), lambda r, d=design: done(d, r))]

    def done(design, r):
        if r is None:
            return []
        design_reads[design].append(r)
        spent.append(r["cost_usd"])
        return more(design)

    run_queue([e for d in groups["designs"] for e in more(d)], a.jobs)
    designs, unsure = {}, []
    for d, rs in design_reads.items():
        ok, v, _ = vote([r["output"]["text_direction"] for r in rs])
        if not ok:
            unsure.append(f"{d} ({', '.join(r['output']['text_direction'] for r in rs)})")
        designs[d] = {"members": groups["designs"][d], "orientation": json.loads(v) if ok else None}
    print(f"spent ${sum(spent):.4f} on orientation reads this run")
    lines = orientation_report(work, designs)
    print(*lines, sep="\n")
    if unsure:
        print("UNSURE: readers disagree on which way the text runs on " + "; ".join(unsure)
              + ". Open one crop of each and turn it with `rotate_items` if it isn't upright.")
    if lines or unsure:
        print("Turn the items, then run `crop && group && orient` again until no ORIENTATION lines are left; only "
              "changed crops are read again. Write `kinds` only after that, from the upright contact sheets and crops: "
              "every position in a description is a position on the upright item.")
    else:
        print("All designs read upright. Write `kinds` from the upright contact sheets and crops.")


def orientation_report(work, designs):
    """Sideways items per page and direction, as r<row>c<col>, or r<row> when the whole row is.
    Items from image files are listed by name."""
    items = {i["key"]: i for i in load_json(work / "items.json")}
    flagged, named, kinds = defaultdict(set), defaultdict(list), defaultdict(set)
    for v in designs.values():
        if v.get("orientation") in TURN:
            read_as = [v["kind"]] if v.get("kind") else v.get("votes", {}).get("kind", [])
            read_as = [k for k in read_as if k]
            for k in v["members"]:
                if "row" in items[k]:
                    where = (items[k]["file"], items[k]["page"], v["orientation"])
                    flagged[where].add((items[k]["row"], items[k]["col"]))
                else:
                    where = v["orientation"]
                    named[where].append(items[k]["label"])
                kinds[where].update(read_as)
    lines = [f"ORIENTATION item files: readers see the text running {d} on {len(names)} items: {' '.join(sorted(names))}. "
             f"Turn them a further {TURN[d]} degrees clockwise (`rotate_items`)." + read_as_text(kinds[d])
             for d, names in sorted(named.items())]
    for (file, page, d), cells in sorted(flagged.items()):
        row_len = Counter(i["row"] for i in items.values() if i["file"] == file and i["page"] == page)
        labels = []
        for row in sorted({r for r, _ in cells}):
            cols = sorted(c for r, c in cells if r == row)
            labels += [f"r{row}"] if len(cols) == row_len[row] else [f"r{row}c{c}" for c in cols]
        lines.append(f"ORIENTATION {file} page {page}: readers see the text running {d} on {len(cells)} items: "
                     f"{' '.join(labels)}. Turn them a further {TURN[d]} degrees clockwise (`rotate` / `rotate_items`)."
                     + read_as_text(kinds[(file, page, d)]))
    return lines


def noted(mismatch):
    return (mismatch or "").strip(" \"'.").lower() not in ("", "none")


def mismatched_kinds(reads):
    """Kinds that most of their reads say are described wrongly, once at least four reads chose them."""
    c = defaultdict(lambda: [0, 0])
    for rs in reads.values():
        for r in rs:
            k = r["output"]["kind"]
            c[k][0] += noted(r["output"].get("mismatch"))
            c[k][1] += 1
    return {k for k, (n, t) in c.items() if k != "other" and t >= 4 and n * 2 > t}


def component_reads(a, work, cfg, spent):
    """Queue entries that read every design until every value has a majority. A design gets one
    read first; if it is read sideways it is not read further, so the bulk of its reading waits
    until it is turned."""
    groups = load_json(work / "groups.json")
    schema = reader_schema(cfg)
    overrides = cfg.get("overrides", {})
    index = read_index(work, cfg)
    reads = {d: design_reads(index, ms) for d, ms in groups["designs"].items() if not a.designs or d in a.designs}
    nxt = {d: len(list((work / "reads" / d).glob("*.json"))) for d in reads}
    busy, failed = Counter(), Counter()

    def task(design, n):
        def run():
            members = groups["designs"][design]
            key = members[n % len(members)]
            d = work / "items" / key
            imgs = [Image.open(d / "front.png")] + ([Image.open(d / "back.png")] if (d / "back.png").exists() else [])
            out, cost = ask(imgs, reader_prompt(cfg, len(imgs) == 2), schema, a.model)
            r = {"item": key, "image": image_id(work, key), "kind_def": kind_hashes(cfg).get(out["kind"]),
                 "model": a.model, "output": out, "cost_usd": cost}
            save_json(work / "reads" / design / f"{n:02d}.json", r)
            return r
        return run

    def done(design, r):
        busy[design] -= 1
        if r is None:
            failed[design] += 1
        else:
            reads[design].append(r)
            spent.append(r["cost_usd"])
        return more(design)

    def more(design):
        rs = reads[design]
        ov = overrides.get(design, {}).get("set", {})
        upright = ov.get("orientation") == "upright"
        if busy[design] or failed[design] >= 2 or len(rs) >= a.max_reads or (orientation(rs) and not upright):
            return []
        if rs and not ov.get("kind") and Counter(r["output"]["kind"] for r in rs).most_common(1)[0][0] in mismatched_kinds(reads):
            return []
        if not rs:
            need = 1
        elif len(rs) < a.reads:
            need = a.reads - len(rs)
        else:
            _, unsettled, text_ok = resolve(cfg, rs, ov.get("kind"))
            need = 1 if unsettled or not text_ok else 0
        out = []
        for _ in range(need):
            busy[design] += 1
            nxt[design] += 1
            out.append((task(design, nxt[design] - 1), lambda r, d=design: done(d, r)))
        return out

    return [e for d in reads for e in more(d)]


def cmd_read(a):
    work, cfg = Path(a.work), load_config(a)
    spent = []
    queue = component_reads(a, work, cfg, spent)
    do_rules = bool(cfg.get("rules_regions")) and not a.designs
    if do_rules:
        queue += rules_reads(a, work, cfg, spent)
    print(f"reading with {a.jobs} parallel readers", flush=True)
    run_queue(queue, a.jobs)
    print(f"spent ${sum(spent):.4f} on reads this run")
    index = read_index(work, cfg)
    stopped = mismatched_kinds({d: design_reads(index, ms) for d, ms in load_json(work / "groups.json")["designs"].items()})
    if stopped:
        print(f"Reading stopped early for {', '.join(sorted(stopped))}: most of their reads say the description "
              "doesn't match the image (see DESCRIPTION below).")
    if do_rules:
        rules_report(a, work, cfg)
    sideways = orientation_report(work, build_resolved(work, cfg)[1])
    if sideways:
        print(*sideways, ORIENTATION_NEXT, sep="\n")
        return
    cmd_check(a)


def apply_override(vals, ov):
    for k, v in ov.items():
        if k.startswith("fields."):
            vals.setdefault("fields", {})[k[7:]] = v
        else:
            vals[k] = v


def build_resolved(work, cfg):
    groups = load_json(work / "groups.json")
    overrides = cfg.get("overrides", {})
    index = read_index(work, cfg)
    designs = {}
    for design, members in groups["designs"].items():
        reads = design_reads(index, members)
        if not reads:
            designs[design] = {"members": members, "reads": 0, "unsettled": ["unread"]}
            continue
        vals, unsettled, text_ok = resolve(cfg, reads, overrides.get(design, {}).get("set", {}).get("kind"))
        unanimous = all(r["output"] == reads[0]["output"] for r in reads) or (
            not unsettled and len({json.dumps(r["output"]["fields"], sort_keys=True) for r in reads}) == 1
            and len({r["output"]["kind"] for r in reads}) == 1)
        vals["orientation"] = orientation(reads)
        ok, majority, _ = vote([r["output"]["kind"] for r in reads])
        vals["read_kind"] = json.loads(majority) if ok else None
        vals["mismatch"] = [(r["output"]["kind"], r["output"].get("mismatch", "")) for r in reads]
        overridden = design in overrides
        if overridden:
            apply_override(vals, overrides[design].get("set", {}))
            unsettled = [u for u in unsettled if u not in overrides[design].get("set", {})]
        proofs = [{"printed": w, "context": ""} for r in reads for w in r["output"].get("misspelled") or []]
        vals["spelling"] = spelling_flags(f"{vals.get('title') or ''}\n{vals.get('text') or ''}", proofs)
        designs[design] = vals | {"members": members, "reads": len(reads), "unsettled": unsettled,
                                  "text_settled": text_ok, "unanimous": unanimous, "overridden": overridden}
    return groups, designs


def expand_rules_items(cfg):
    """Components the rules name that no file shows: one dict per physical item, in the shape of `items`."""
    if "not_in_files" in cfg:
        sys.exit("not_in_files is no longer used: list each missing component under rules_items with its count")
    kinds = {k["id"]: k for k in cfg.get("kinds", [])}
    out, seen = [], Counter()
    for e in cfg.get("rules_items", []):
        kind, src = e["kind"], e["source"]
        if kind not in kinds:
            sys.exit(f"rules_items: kind {kind!r} is not in kinds")
        declared = [f["name"] for f in kinds[kind].get("fields", [])]
        bad = sorted(set(e.get("fields", {})) - set(declared))
        if bad:
            sys.exit(f"rules_items {kind}: fields {bad} are not declared for that kind")
        stem = Path(src["file"]).stem
        for _ in range(int(e["count"])):
            seen[(stem, src["page"], kind)] += 1
            n = seen[(stem, src["page"], kind)]
            out.append({"id": f"{stem}#p{src['page']}_{kind}_{n:02d}", "kind": kind,
                        "source": {"file": src["file"], "page": src["page"]},
                        "title": e.get("title"), "fields": {f: e.get("fields", {}).get(f) for f in declared},
                        "text": e.get("text"), "from_rules": True, "confidence": "high", "notes": ""})
    return out


def cmd_check(a):
    work, cfg = Path(a.work), load_config(a)
    groups, designs = build_resolved(work, cfg)
    items = {i["key"]: i for i in load_json(work / "items.json")}
    item_design = {k: d for d, ms in groups["designs"].items() for k in ms}
    item_back = {k: b for b, ms in groups["backs"].items() for k in ms}
    overrides = cfg.get("overrides", {})

    def item_vals(key):
        v = dict(designs[item_design[key]])
        if key in overrides:
            v["fields"] = dict(v.get("fields", {}))
            apply_override(v, overrides[key].get("set", {}))
        return v

    report = {"conflicts": [], "text_uncertain": [], "spelling": [], "description": [], "checks": [],
              "back_checks": [], "count_checks": [], "orientation": orientation_report(work, designs)}
    for design, v in designs.items():
        img = str(work / "items" / v["members"][0] / "front.png")
        if v["unsettled"]:
            report["conflicts"].append({"design": design, "image": img, "unsettled": v["unsettled"],
                                        "votes": v.get("votes", {}), "members": v["members"]})
        elif not v.get("text_settled", True) and not v.get("overridden"):
            report["text_uncertain"].append({"design": design, "image": img, "spans": v["votes"].get("text", [])})
        for f in v.get("spelling", []):
            report["spelling"].append({"design": design, "image": img} | f)

    against, mismatch = defaultdict(list), defaultdict(list)
    for design, v in designs.items():
        if v.get("overridden") and v.get("read_kind") not in (None, v.get("kind")):
            against[v["kind"]].append(design)
        for k, m in v.get("mismatch", []):
            mismatch[k].append(m)
    for k, said in sorted(mismatch.items(), key=lambda x: str(x[0])):
        noted_ = [m for m in said if noted(m)]
        if k not in (None, "other") and len(noted_) * 2 > len(said):
            report["description"].append({"kind": k, "reads": len(said), "mismatch": len(noted_), "examples": noted_[:3]})
    for k, ds in sorted(against.items()):
        report["checks"].append(
            f"kind {k} is set by override on {len(ds)} designs whose reads mostly chose another kind "
            f"({' '.join(ds[:8])}{' ...' if len(ds) > 8 else ''}): readers don't recognise it from its description. "
            "Rewrite the description for the crop as readers see it and run `read` again, rather than overriding")

    back_kinds = defaultdict(Counter)
    for key in items:
        if key in item_back:
            back_kinds[item_back[key]][item_vals(key).get("kind")] += 1
    allowed = cfg.get("back_kinds", {})
    for b, c in back_kinds.items():
        if b in allowed and set(c) - set(allowed[b]):
            report["back_checks"].append(f"back group {b} allows {allowed[b]} but has {dict(c)}")
        elif b not in allowed and len(c) > 1:
            report["back_checks"].append(f"back group {b} (identical backs) holds several kinds: {dict(c)}")

    cands = [item_vals(k) for k in items] + expand_rules_items(cfg)
    kind_count = Counter(v.get("kind") for v in cands)
    for k in cfg["kinds"]:
        if k.get("count_in_rules") is not None and k["count_in_rules"] != kind_count[k["id"]]:
            report["count_checks"].append(f"kind {k['id']}: rules say {k['count_in_rules']}, found {kind_count[k['id']]} (files plus rules_items)")
    for e in cfg.get("expect", []):
        sel = [v for v in cands if v.get("kind") == e["kind"]
               and all((v["fields"].get(f) if f != "title" else v.get("title")) == val
                       for f, val in e.get("where", {}).items())]
        label = f"expect {e['kind']} {e.get('where', {})}"
        if "count" in e and e["count"] != len(sel):
            report["count_checks"].append(f"{label}: expected {e['count']} items, found {len(sel)}")
        for f, dist in e.get("distribution", {}).items():
            got = Counter(str(v["fields"].get(f)) for v in sel)
            want = {str(k): n for k, n in dist.items()}
            if dict(got) != want:
                report["count_checks"].append(f"{label}: {f} expected {want}, found {dict(got)}")

    save_json(work / "check.json", report)
    n = len(designs)
    settled = sum(1 for v in designs.values() if not v["unsettled"])
    print(f"designs: {n}, settled: {settled}, unanimous: {sum(1 for v in designs.values() if v.get('unanimous'))}, "
          f"overridden: {sum(1 for v in designs.values() if v.get('overridden'))}")
    if back_kinds:
        print(f"items per back group and kind: " + "; ".join(f"{b}: {dict(c)}" for b, c in sorted(back_kinds.items())))
    for c in report["conflicts"]:
        print(f"CONFLICT {c['design']} {c['unsettled']} votes={json.dumps(c['votes'], ensure_ascii=False)} image={c['image']}")
    if report["conflicts"]:
        print(HELP["conflict"])
    for t in report["text_uncertain"]:
        print(f"TEXT UNCERTAIN {t['design']} image={t['image']}")
        for u in t["spans"][:5]:
            print(f"    kept: {u['kept']!r}  alternatives: {u['alternatives']!r}")
    if report["text_uncertain"]:
        print(HELP["text"])
    for f in report["spelling"]:
        print(f"SPELLING {f['design']}: a reader saw {f['printed']!r} printed; the title/text has {f['transcribed']!r} image={f['image']}")
    if report["spelling"]:
        print(HELP["spelling"])
    for d in report["description"]:
        print(f"DESCRIPTION kind {d['kind']}: {d['mismatch']} of {d['reads']} reads say its description doesn't match "
              f"the image, e.g. " + " | ".join(repr(m) for m in d["examples"]))
    if report["description"]:
        print("Readers take values from the wrong place when a description doesn't match, often all in the same "
              "way, so voting can't catch it. Rewrite each flagged description where they say, checking one crop, "
              "and run `read`: it reads that kind again.")
    for line in report["orientation"]:
        print(line)
    if report["orientation"]:
        print(ORIENTATION_NEXT)
    for c in report["checks"]:
        print(f"CHECK {c}")
    for c in report["back_checks"]:
        print(f"CHECK {c}")
    if report["back_checks"]:
        print(HELP["back"])
    for c in report["count_checks"]:
        print(f"CHECK {c}")
    if report["count_checks"]:
        print(HELP["count"])
    print(f"total cost so far: ${total_cost(work):.4f}; details in {work / 'check.json'}")


# ---------------------------------------------------------------- rules

RULES_PROMPT = """This image is one region of a game's rulebook. Transcribe the rules text in it, exactly as
printed, in reading order: headings, paragraphs, list items, tables and captions printed next to pictures.
- Copy every word exactly as printed, letter by letter, including spelling mistakes, typos and odd grammar.
  A later step looks for these, so a corrected word is an error. Never fix, modernise or translate anything.
- Copy every symbol exactly: + - – — × = % / ( ) and the like. Do not drop or add any.
- Write each picture (pictured cards, tokens, boards, sheets, diagrams, icons, logos, QR codes) as just
  [image], and do not transcribe text printed inside it.
- Leave out page numbers, headers and footers, and empty boxes or lines meant for writing in.
- Plain text only: no bold or italics markup. Start heading lines with '# '. Start list items with their
  number ('1. ') or with '- '. Write table rows with ' | ' between cells.
- Text cut off at the region's edge: transcribe what is visible.
Reply with the transcription only: no introduction, no comments."""

PROOF_PROMPT = """Proofread this image of printed text. List every word that is misspelled as printed: spelling
mistakes, typos, wrong letters, missing or doubled letters. Copy each misspelled word exactly as printed,
letter by letter, and give a few words around it as context. Ignore names, abbreviations and symbols.
If there are none, return an empty list."""

PROOF_SCHEMA = {"type": "object", "required": ["misspelled"], "properties": {"misspelled": {"type": "array", "items": {
    "type": "object", "required": ["printed", "context"],
    "properties": {"printed": {"type": "string"}, "context": {"type": "string"}}}}}}


def enlarge(img):
    f = MAX_SIDE / max(img.size)
    return img.resize((round(img.width * f), round(img.height * f)), Image.LANCZOS) if f > 1 else img


def halves(img):
    """Two overlapping halves along the longer side. Readers spot misspellings far more reliably in
    an enlarged half than in the whole region."""
    w, h = img.size
    n = w if w >= h else h
    spans = [(0, int(n * 0.55)), (int(n * 0.45), n)]
    return [img.crop((a, 0, b, h) if w >= h else (0, a, w, b)) for a, b in spans]


def bare(word):
    return re.sub(r"[^\w]", "", word).casefold()


def spelling_flags(text, proofs):
    """Misspellings the proofreaders saw that the transcription has in a corrected form."""
    words = {bare(t): t for t in tokens(text)}
    flags = {}
    for m in proofs:
        printed = bare(m["printed"])
        if not printed or printed in words or printed in flags:
            continue
        close = difflib.get_close_matches(printed, words, n=1, cutoff=0.75)
        if close:
            flags[printed] = {"printed": m["printed"], "transcribed": words[close[0]], "context": m["context"]}
    return list(flags.values())


def tokens(text):
    return re.findall(r"\S+|\n", (text or "").replace("**", "").replace("__", ""))


def detokenize(toks):
    out = ""
    for t in toks:
        out = out.rstrip(" ") + "\n" if t == "\n" else out + t + " "
    return re.sub(r"\n{3,}", "\n\n", "\n".join(l.rstrip() for l in out.split("\n"))).strip() + "\n"


def words_only(toks):
    """Tokens without layout and [image]-style markers, which readers place inconsistently."""
    return tuple(t for t in toks if t not in ("\n", "[", "]") and not re.fullmatch(r"\[[^\]]*\]", t))


def merge_reads(texts):
    """Word-level majority over independent transcriptions. Start from the read closest to the
    others; a differing span is replaced when more reads agree on the replacement than on the
    base. Returns (text, unresolved spans)."""
    ts = [tokens(t) for t in texts]
    ratio = lambda a, b: difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
    b = max(range(len(ts)), key=lambda j: sum(ratio(ts[j], t) for t in ts))
    base = ts[b]
    alts = defaultdict(Counter)
    for j, t in enumerate(ts):
        if j == b:
            continue
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, base, t, autojunk=False).get_opcodes():
            if op != "equal":
                alts[(i1, i2)][tuple(t[j1:j2])] += 1
    out, unresolved = list(base), []
    for (i1, i2), votes in sorted(alts.items(), reverse=True):
        alt, n = votes.most_common(1)[0]
        keep = len(ts) - sum(votes.values())
        ctx = lambda seq: " ".join(x for x in seq if x != "\n")
        # Readers drop text far more often than they invent it, so a passage that only a minority
        # transcribed is flagged rather than voted away.
        dropped = any(len(words_only(v)) >= len(words_only(base[i1:i2])) + 5 for v in votes)
        if n > keep:
            out[i1:i2] = list(alt)
        elif (n == keep or len(votes) > 1 or dropped) and len({words_only(base[i1:i2])} | {words_only(v) for v in votes}) > 1:
            unresolved.append({"kept": ctx(base[max(0, i1 - 4):i2 + 4]),
                               "alternatives": [ctx(base[max(0, i1 - 4):i1] + list(v) + base[i2:i2 + 4]) for v in votes]})
    return detokenize(out), unresolved[::-1]


def ocr_region(r):
    """Tesseract's transcription of a rules region, from the page rendered at 400 dpi and
    thresholded (its best setting in tests). Free, and wrong in different places than the model
    readers: it keeps typos but garbles pictured forms and text between pictures."""
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["pdftoppm", "-r", "400", "-f", str(r["page"]), "-l", str(r["page"]), "-png",
                        "-singlefile", r["file"], f"{tmp}/page"], capture_output=True, check=True)
        page = Image.open(f"{tmp}/page.png").convert("L")
    crop = rotate(page.crop(region_box(r["box"], page.size)), r.get("rotate", 0)).point(lambda v: 255 if v > 160 else 0)
    buf = io.BytesIO()
    crop.save(buf, "PNG")
    return subprocess.run(["tesseract", "-", "-", "-l", "eng", "--psm", "3"], input=buf.getvalue(),
                          capture_output=True, env=os.environ | {"OMP_THREAD_LIMIT": "1"}, check=True).stdout.decode()


def ocr_words(text):
    """Words to compare a transcription with Tesseract's: case and spelling kept; markup, [image]
    markers, list bullets and punctuation around words dropped; quotes straightened."""
    text = re.sub(r"\[[^\]]*\]", " ", text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"'))
    words = (w.strip(".,:;!?()[]{}\"'*_#|>-–—•·") for w in text.split())
    return [w for w in words if re.search(r"\w", w)]


def ocr_confirms(read, ocr):
    return bool(ocr and ocr_words(ocr)) and ocr_words(read) == ocr_words(ocr)


def rules_setup(work, cfg):
    regions = cfg.get("rules_regions", [])
    rdir = work / "rules"
    # Reads are stored under a hash of the region's definition, so editing or reordering regions
    # never reuses a read of a different crop.
    keys = {i: hashlib.sha1(json.dumps(r, sort_keys=True).encode()).hexdigest()[:12] for i, r in enumerate(regions)}
    (rdir / "reads").mkdir(parents=True, exist_ok=True)
    crops = {}
    for i, r in enumerate(regions):
        full = Image.open(page_path(work, Path(r["file"]).stem, r["page"]))
        crop = rotate(full.crop(region_box(r["box"], full.size)), r.get("rotate", 0))
        crop.save(rdir / f"region_{i:02d}.png")
        crops[i] = crop
        if max(crop.size) > MAX_SIDE * 1.5:
            print(f"warning: region {i} is {crop.size[0]}x{crop.size[1]} px and will be shrunk to {MAX_SIDE} px; "
                  "split it if the text gets small", file=sys.stderr)
    return regions, rdir, keys, crops


def region_reads(rdir, key):
    return [load_json(p)["text"] for p in sorted((rdir / "reads").glob(f"{key}.read*.json"))]


def rules_reads(a, work, cfg, spent):
    """Queue entries that transcribe every rules region until every word has a majority, then
    proofread it in enlarged halves. A region whose first read has exactly Tesseract's words is
    done after that read: two independent methods agree."""
    regions, rdir, keys, crops = rules_setup(work, cfg)
    reads = {i: region_reads(rdir, keys[i]) for i in crops}
    nxt = {i: len(list((rdir / "reads").glob(f"{keys[i]}.read*.json"))) for i in crops}
    ocr_path = {i: rdir / "reads" / f"{keys[i]}.ocr.txt" for i in crops}
    ocr = {i: p.read_text() if p.exists() else None for i, p in ocr_path.items()}
    busy, failed, proofed = Counter(), Counter(), set()

    def read_task(i, n):
        def run():
            prompt = RULES_PROMPT + (f"\n\nNote for this region: {regions[i]['note']}" if regions[i].get("note") else "")
            text, cost = ask([enlarge(crops[i])], prompt, None, a.model)
            text = html.unescape(text)
            save_json(rdir / "reads" / f"{keys[i]}.read{n}.json", {"text": text, "cost_usd": cost, "model": a.model})
            spent.append(cost)
            return text
        return run

    def ocr_task(i):
        def run():
            try:
                text = ocr_region(regions[i])
            except (subprocess.CalledProcessError, OSError) as e:
                print(f"OCR of region {i} failed: {e}", file=sys.stderr)
                text = ""
            ocr_path[i].write_text(text)
            return text
        return run

    def proof_task(i, h, n):
        def run():
            out, cost = ask([enlarge(halves(crops[i])[h])], PROOF_PROMPT, PROOF_SCHEMA, a.model)
            save_json(rdir / "reads" / f"{keys[i]}.proof{h}_{n}.json", {**out, "cost_usd": cost, "model": a.model})
            spent.append(cost)
        return run

    def read_done(i, text):
        busy[i] -= 1
        if text is None:
            failed[i] += 1
        else:
            reads[i].append(text)
        return more(i)

    def ocr_done(i, text):
        busy[i] -= 1
        ocr[i] = text
        return more(i)

    def more(i):
        rs = reads[i]
        if busy[i] or failed[i] >= 2:
            return []
        if len(rs) == 1 and ocr_confirms(rs[0], ocr[i]):
            return []
        if len(rs) < a.reads:
            need = a.reads - len(rs)
        elif len(rs) < a.max_reads and len({tuple(tokens(t)) for t in rs}) > 1 and (len(rs) < 3 or merge_reads(rs)[1]):
            need = 1
        else:
            if i in proofed:
                return []
            proofed.add(i)
            return [(proof_task(i, h, n), lambda _: [])
                    for h in range(2) for n in range(a.reads)
                    if not (rdir / "reads" / f"{keys[i]}.proof{h}_{n}.json").exists()]
        out = []
        for _ in range(need):
            busy[i] += 1
            nxt[i] += 1
            out.append((read_task(i, nxt[i] - 1), lambda t, i=i: read_done(i, t)))
        return out

    queue = []
    for i in crops:
        if ocr[i] is None:
            busy[i] += 1
            queue.append((ocr_task(i), lambda t, i=i: ocr_done(i, t)))
        if not reads[i]:
            busy[i] += 1
            nxt[i] += 1
            queue.append((read_task(i, nxt[i] - 1), lambda t, i=i: read_done(i, t)))
        else:
            queue += more(i)
    return queue


def rules_report(a, work, cfg):
    regions, rdir, keys, crops = rules_setup(work, cfg)
    conflicts, confirmed = [], 0
    for i in crops:
        rs = region_reads(rdir, keys[i])
        ocr_file = rdir / "reads" / f"{keys[i]}.ocr.txt"
        confirmed += len(rs) == 1 and ocr_file.exists() and ocr_confirms(rs[0], ocr_file.read_text())
        text, unresolved = merge_reads(rs) if rs else ("", [])
        (rdir / f"region_{i:02d}.txt").write_text(text)
        proofs = [m for p in sorted((rdir / "reads").glob(f"{keys[i]}.proof*.json")) for m in load_json(p)["misspelled"]]
        spelling = spelling_flags(text, proofs)
        ocr_seen = {bare(w) for w in ocr_words(ocr_file.read_text())} if ocr_file.exists() else set()
        for f in spelling:
            f["tesseract_agrees"] = bare(f["printed"]) in ocr_seen
        if not rs:
            unresolved = [{"kept": "", "alternatives": ["(no read succeeded; run `rules` again)"]}]
        if unresolved or spelling:
            conflicts.append({"region": i, "image": str(rdir / f"region_{i:02d}.png"), "reads": len(rs),
                              "unresolved": unresolved, "spelling": spelling})
    save_json(work / "rules_conflicts.json", conflicts)
    save_json(rdir / "regions.json", keys)
    same = sum(1 for i in crops if len({tuple(tokens(t)) for t in region_reads(rdir, keys[i])}) == 1)
    print(f"{len(crops)} regions transcribed; {confirmed} confirmed by Tesseract after one read, "
          f"{same - confirmed} with all reads identical")
    for c in conflicts:
        print(f"REGION {c['region']} ({c['image']}):")
        for u in c["unresolved"][:10]:
            print(f"    NO MAJORITY after {c['reads']} reads. kept: {u['kept']!r}\n        alternatives: {u['alternatives']!r}")
        for f in c["spelling"]:
            print(f"    SPELLING: proofreaders saw {f['printed']!r} ({f['context']!r}); transcription has {f['transcribed']!r}"
                  + ("; Tesseract also reads it as printed" if f["tesseract_agrees"] else ""))
    if any(c["unresolved"] for c in conflicts):
        print(HELP["no_majority"])
    if any(c["spelling"] for c in conflicts):
        print(HELP["rules_spelling"])
    print(f"details in {work / 'rules_conflicts.json'}; total cost so far: ${total_cost(work):.4f}")
    cmd_preview(a)


def cmd_rules(a):
    work, cfg = Path(a.work), load_config(a)
    spent = []
    run_queue(rules_reads(a, work, cfg, spent), a.jobs)
    print(f"spent ${sum(spent):.4f} on rules reads this run")
    rules_report(a, work, cfg)


# ---------------------------------------------------------------- assemble / cost

def cmd_assemble(a):
    work, cfg = Path(a.work), load_config(a)
    out = Path(cfg.get("output", "results"))
    out.mkdir(parents=True, exist_ok=True)

    regions = cfg.get("rules_regions", [])
    keys = {str(i): hashlib.sha1(json.dumps(r, sort_keys=True).encode()).hexdigest()[:12] for i, r in enumerate(regions)}
    if load_json(work / "rules" / "regions.json") != keys:
        sys.exit("rules_regions changed since the last `rules` run; run `rules` again")
    if coverage(work, cfg) and not a.force:
        sys.exit("text outside every rules region; run `preview`, then cover it or list it in `rules_excluded`")
    rules = []
    for i in range(len(regions)):
        p = work / "rules" / f"region_{i:02d}.txt"
        if not p.exists():
            sys.exit(f"rules region {i} not transcribed; run `rules` first")
        rules.append(p.read_text().strip())
    text = "\n\n".join(rules) + "\n"
    for fix in cfg.get("rules_fixes", []):
        if fix["find"] not in text:
            sys.exit(f"rules_fixes: {fix['find']!r} not found")
        text = text.replace(fix["find"], fix["replace"])
    (out / "rules.txt").write_text(text)
    write_review(work, cfg)

    groups, designs = build_resolved(work, cfg)
    declared = {k["id"]: {f"fields.{f['name']}" for f in k.get("fields", [])} for k in cfg["kinds"]}
    blank = [d for d, v in designs.items() if declared.get(v.get("kind")) and declared[v["kind"]] <= set(v["unsettled"])]
    if blank:
        sys.exit(f"designs {blank} have no value for any field of their kind, so readers didn't read them as that kind. "
                 "Rewrite the kind's description for the crop as readers see it and run `read` again; --force doesn't "
                 "cover these. If the image really shows no legible value, set each field to null by override with the reason.")
    open_conflicts = [d for d, v in designs.items() if v["unsettled"] or v.get("orientation") in TURN]
    if open_conflicts and not a.force:
        sys.exit(f"unresolved or sideways designs {open_conflicts}; resolve them (see `check`), or pass --force to mark them low confidence")
    items = load_json(work / "items.json")
    item_design = {k: d for d, ms in groups["designs"].items() for k in ms}
    overrides = cfg.get("overrides", {})
    kinds = {k["id"]: k for k in cfg["kinds"]}
    out_items = []
    for it in items:
        d = item_design[it["key"]]
        v = dict(designs[d])
        v["fields"] = dict(v.get("fields") or {})
        notes = [f"design {d} ({len(v['members'])} identical copies); {v['reads']} independent reads"]
        if it["key"] in overrides:
            apply_override(v, overrides[it["key"]].get("set", {}))
            notes.append(f"overridden: {overrides[it['key']].get('reason', '')}")
        if v.get("overridden"):
            notes.append(f"design overridden: {overrides[d].get('reason', '')}")
        if v.get("orientation") in TURN:
            v["unsettled"] = v["unsettled"] + ["orientation"]
        conf = "low" if v["unsettled"] else "high" if v.get("unanimous") and not v.get("overridden") else "medium"
        if v["unsettled"]:
            notes.append(f"unresolved: {v['unsettled']} votes {json.dumps(v.get('votes', {}), ensure_ascii=False)}")
        if not v.get("text_settled", True):
            notes.append("text: reads differed; closest-to-consensus read kept")
        kind = v.get("kind") if v.get("kind") in kinds else "other"
        if "row" in it:
            src = {"file": it["file"], "page": it["page"], "row": it["row"], "col": it["col"]}
            src |= {k: it[k] for k in ("back_page", "back_row", "back_col") if k in it}
            item_id = f"{Path(it['file']).stem}#p{it['page']}_r{it['row']}_c{it['col']}"
        else:
            src, item_id = {"file": it["file"], "page": it["page"]}, it["label"]
        out_items.append({
            "id": item_id, "kind": kind, "source": src,
            "title": v.get("title"), "fields": {f["name"]: v["fields"].get(f["name"]) for f in kinds.get(kind, {}).get("fields", [])},
            "text": v.get("text"), "from_rules": False, "confidence": conf, "notes": "; ".join(notes)})
    out_items += expand_rules_items(cfg)
    count = Counter(i["kind"] for i in out_items)
    kind_list = [{"id": k["id"], "name": k["name"], "fields": k.get("fields", []), "count_found": count[k["id"]],
                  "count_in_rules": k.get("count_in_rules"), "back": k.get("back"), "notes": k.get("notes", "")}
                 for k in cfg["kinds"]]
    if count["other"]:
        kind_list.append({"id": "other", "name": "Unclassified", "fields": [], "count_found": count["other"],
                          "count_in_rules": None, "back": None, "notes": "Readers could not agree on a kind."})
    doc = {"spec_version": "extraction-1.0", "game": cfg["game"], "sources": cfg["sources"],
           "component_kinds": kind_list, "items": out_items,
           "extraction_notes": cfg.get("extraction_notes", []) + [
               f"Each of {len(designs)} unique designs (pixel-identical fronts grouped) was read by independent "
               f"single-component model calls until every value had a majority; {sum(1 for v in designs.values() if v.get('unanimous'))} "
               f"designs were unanimous, {sum(1 for v in designs.values() if v.get('overridden'))} were resolved by hand.",
               f"Model cost of all reads: ${total_cost(work):.4f}."]}
    save_json(work / "components.json", doc)
    exported = export(doc)
    save_json(out / "components.json", exported)
    errs = validate(doc) + validate(exported, "export.schema.json")
    print(f"wrote {work / 'components.json'}, {out / 'rules.txt'} and {out / 'components.json'}: "
          f"{'VALID' if not errs else 'INVALID'}")
    for e in errs[:30]:
        print("  ", e)
    print("items per kind:", dict(count))


def export(doc):
    """The extraction for the steps after it: no sources, ids, notes or confidence, and items that are
    identical without them merged into one entry with a count. An item counted from the rules joins
    the one variant shown in the files whose kind and fields it matches; the rules' name for it
    doesn't keep it apart."""
    merged = {}

    def add(i, key=None):
        piece = {k: i[k] for k in ("title", "fields", "text", "back") if i.get(k) not in (None, {})}
        key = key or json.dumps([i["kind"], piece], sort_keys=True)
        entry = merged.setdefault(key, {"kind": i["kind"], "count": 0} | piece)
        entry["count"] += 1
        for k in ("title", "text"):
            if i.get(k) and k not in entry:
                entry[k] = i[k]

    for i in doc["items"]:
        if not i["from_rules"]:
            add(i)
    shown = dict(merged)
    for i in doc["items"]:
        if i["from_rules"]:
            same = [k for k, e in shown.items() if e["kind"] == i["kind"] and e.get("fields", {}) == (i["fields"] or {})]
            add(i, same[0] if len(same) == 1 else None)
    kinds = [{k: v for k, v in kind.items() if k in ("id", "name", "fields", "back") and v not in (None, [])}
             for kind in doc["component_kinds"]]
    return {"game": doc["game"], "component_kinds": kinds, "components": list(merged.values())}


def cmd_export(a):
    save_json(a.out, export(load_json(a.file or Path(a.work) / "components.json")))
    print(f"wrote {a.out}")


def write_review(work, cfg):
    """Each rules region beside its transcription, with fixes and flags, for a final read by a person."""
    from html import escape
    flags = {c["region"]: c for c in load_json(work / "rules_conflicts.json", [])}
    fixes = cfg.get("rules_fixes", [])
    parts = []
    for i, r in enumerate(cfg.get("rules_regions", [])):
        text = escape((work / "rules" / f"region_{i:02d}.txt").read_text())
        for fix in fixes:
            text = text.replace(escape(fix["find"]), f"<mark>{escape(fix['replace'])}</mark>")
        notes = [f"no majority: {escape(u['kept'])} / {' / '.join(map(escape, u['alternatives']))}"
                 for u in flags.get(i, {}).get("unresolved", [])]
        notes += [f"proofreaders saw {escape(f['printed'])}, transcribed {escape(f['transcribed'])}"
                  for f in flags.get(i, {}).get("spelling", [])]
        parts.append(f"<h2>Region {i}: {escape(Path(r['file']).name)} page {r['page']}</h2>"
                     + "".join(f"<p class=flag>{n}</p>" for n in notes)
                     + f"<div class=row><img src='rules/region_{i:02d}.png'><pre>{text}</pre></div>")
    (work / "review.html").write_text(
        "<!doctype html><meta charset=utf-8><title>Rules review</title><style>"
        "body{font-family:sans-serif;margin:16px}.row{display:grid;grid-template-columns:1fr 1fr;gap:16px}"
        "img{width:100%;border:1px solid #ccc}pre{white-space:pre-wrap;font-size:15px;margin:0}"
        "mark{background:#ff0}.flag{color:#b00;margin:4px 0}</style>"
        "<p>Each rules region beside its transcription. Fixes from the config are highlighted; flags from the "
        "readers are in red. Read every region against its image.</p>" + "".join(parts))
    print(f"review page: {work / 'review.html'}")


def validate(doc, schema="components.schema.json"):
    from jsonschema import Draft202012Validator
    schema = json.loads((SKILL_DIR / schema).read_text())
    errs = [f"{'/'.join(map(str, e.absolute_path))}: {e.message[:200]}" for e in Draft202012Validator(schema).iter_errors(doc)]
    ids = [i["id"] for i in doc.get("items", [])]
    if len(ids) != len(set(ids)):
        errs.append("duplicate item ids")
    return errs


def total_cost(work):
    paths = (list((work / "reads").glob("*/*.json")) + list((work / "orient").glob("*/*.json"))
             + list((work / "rules" / "reads").glob("*.json")))
    return sum(load_json(p).get("cost_usd", 0) for p in paths)


def cmd_cost(a):
    work = Path(a.work)
    reads = [load_json(p) for p in (work / "reads").glob("*/*.json")]
    orient = [load_json(p) for p in (work / "orient").glob("*/*.json")]
    rules = [load_json(p) for p in (work / "rules" / "reads").glob("*.read*.json")]
    proofs = [load_json(p) for p in (work / "rules" / "reads").glob("*.proof*.json")]
    print(f"orientation reads: {len(orient)} calls, ${sum(r['cost_usd'] for r in orient):.4f}")
    print(f"component reads: {len(reads)} calls, ${sum(r['cost_usd'] for r in reads):.4f}")
    print(f"rules reads: {len(rules)} calls, ${sum(r['cost_usd'] for r in rules):.4f}")
    print(f"proofreading reads: {len(proofs)} calls, ${sum(r['cost_usd'] for r in proofs):.4f}")
    print(f"total: ${total_cost(work):.4f}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--work", default="work")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("render")
    s.add_argument("pdfs", nargs="+")
    s.add_argument("--dpi", type=int, default=300)
    s = sub.add_parser("lines")
    s.add_argument("page", help="page render path or name, e.g. <pdf stem>_p1")
    s.add_argument("--min-frac", type=float, default=0.5)
    sub.add_parser("preview")
    sub.add_parser("crop")
    s = sub.add_parser("export")
    s.add_argument("file", nargs="?")
    s.add_argument("out", nargs="?", default="results/components.json")
    sub.add_parser("group")
    s = sub.add_parser("orient")
    s.add_argument("--model", default="haiku")
    s.add_argument("--jobs", type=int, default=12)
    for name in ("read", "check", "rules", "assemble", "cost"):
        s = sub.add_parser(name)
        s.add_argument("--model", default="haiku")
        s.add_argument("--jobs", type=int, default=12)
        s.add_argument("--reads", type=int, default=2)
        s.add_argument("--max-reads", type=int, default=5)
        s.add_argument("--designs", nargs="*", help="only these designs")
        s.add_argument("--force", action="store_true")
    a = p.parse_args()
    globals()[f"cmd_{a.cmd}"](a)


if __name__ == "__main__":
    main()
