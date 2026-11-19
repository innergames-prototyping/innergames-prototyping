"""Reading the rulebook: every region is transcribed by several readers until their words agree,
then proofread in enlarged halves. Tesseract is a free second opinion where it is installed."""

import asyncio
import hashlib
import html
import io
import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image

from . import regions
from .check import HELP
from .cost import total_cost
from .images import MAX_SIDE, enlarged, halves, rotate
from .models import ExtractionConfig, RulesRegion
from .queue import Read, ReadLimits, ReadTarget, run_reads
from .reader import Reader
from .render import render_page
from .voting import bare, merge_reads, ocr_confirms, ocr_words, space_dots, spelling_flags, tokens
from .workspace import Workspace, load_json, save_json

log = logging.getLogger(__name__)

RULES_PROMPT = """This image is one region of a game's rulebook. Transcribe the rules text in it, exactly as
printed, in reading order: headings, paragraphs, list items, tables and captions printed next to pictures.
- Copy every word exactly as printed, letter by letter, including spelling mistakes, typos and odd grammar.
  A later step looks for these, so a corrected word is an error. Never fix, modernise or translate anything.
- Copy every symbol exactly: + - – — × = % / ( ) and the like. Do not drop or add any.
- Coloured dots or pips set in a line of text, which score or count something, are text: write each
  one where it stands as ● with its colour in brackets, e.g. ●(green) ●(red), one per dot, in printed
  order. Name colours with the closest of: red, orange, yellow, green, blue, purple, pink, brown,
  black, white, grey. List bullets are not such dots: start the list item with '- '.
- Write each picture (pictured cards, tokens, boards, sheets, diagrams, icons, logos, QR codes) as just
  [image], and do not transcribe text printed inside it.
- Leave out page numbers, headers and footers, and empty boxes or lines meant for writing in.
- Plain text only: no bold or italics markup. Start heading lines with '# '. Start list items with their
  number ('1. ') or with '- '. Write table rows with ' | ' between cells.
- Text cut off at the region's edge: transcribe what is visible.
Reply with the transcription only: no introduction, no comments."""  # noqa: E501

PROOF_PROMPT = """Proofread this image of printed text. List every word that is misspelled as printed: spelling
mistakes, typos, wrong letters, missing or doubled letters. Copy each misspelled word exactly as printed,
letter by letter, and give a few words around it as context. Ignore names, abbreviations and symbols.
If there are none, return an empty list."""  # noqa: E501

PROOF_SCHEMA = {
    "type": "object",
    "required": ["misspelled"],
    "properties": {
        "misspelled": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["printed", "context"],
                "properties": {"printed": {"type": "string"}, "context": {"type": "string"}},
            },
        }
    },
}

NO_TESSERACT = "Tesseract is not installed, so no region is confirmed after one read."


# ---------------------------------------------------------------- Tesseract


def tesseract_installed() -> bool:
    return shutil.which("tesseract") is not None


def ocr_region(ws: Workspace, region: RulesRegion) -> str:
    """Tesseract's transcription of a rules region, from the page rendered at 400 dpi and
    thresholded (its best setting in tests). Free, and wrong in different places than the model
    readers: it keeps typos but garbles pictured forms and text between pictures.

    Returns "" when Tesseract is not installed."""
    tesseract = shutil.which("tesseract")
    if tesseract is None:
        return ""
    page = render_page(ws.input_file(region.file), region.page, 400).convert("L")
    crop = rotate(page.crop(regions.region_box(region.box, page.size)), region.rotate)
    crop = crop.point(lambda v: 255 if v > 160 else 0)
    png = io.BytesIO()
    crop.save(png, "PNG")
    done = subprocess.run(
        [tesseract, "-", "-", "-l", "eng", "--psm", "3"],
        input=png.getvalue(),
        capture_output=True,
        env=os.environ | {"OMP_THREAD_LIMIT": "1"},
        check=True,
    )
    return done.stdout.decode()


# ---------------------------------------------------------------- the regions and their files


def region_keys(cfg: ExtractionConfig) -> dict[int, str]:
    """A hash of each region's definition. Reads are stored under it, so editing or reordering
    regions never reuses a read of a different crop."""
    return {
        i: hashlib.sha1(json.dumps(r.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()[
            :12
        ]
        for i, r in enumerate(cfg.rules_regions)
    }


def rules_setup(ws: Workspace, cfg: ExtractionConfig) -> dict[int, Image.Image]:
    """Cuts every region out of its page render and saves it as work/rules/region_NN.png."""
    folder = ws.work / "rules"
    (folder / "reads").mkdir(parents=True, exist_ok=True)
    crops = {}
    for i, region in enumerate(cfg.rules_regions):
        page = Image.open(ws.page_image(Path(region.file).stem, region.page))
        crop = rotate(page.crop(regions.region_box(region.box, page.size)), region.rotate)
        crop.save(folder / f"region_{i:02d}.png")
        crops[i] = crop
        if max(crop.size) > MAX_SIDE * 1.5:
            log.warning(
                "region %d is %dx%d px and will be shrunk to %d px; split it if text gets small",
                i,
                *crop.size,
                MAX_SIDE,
            )
    return crops


def region_reads(folder: Path, key: str) -> list[str]:
    """The transcriptions of one region, in order. `folder` is work/rules."""
    return [load_json(p)["text"] for p in sorted((folder / "reads").glob(f"{key}.read*.json"))]


# ---------------------------------------------------------------- reading a region


class RegionTarget(ReadTarget):
    """Transcribes one region until every word has a majority, then proofreads it in enlarged
    halves. A region whose first read has exactly Tesseract's words is done after that read: two
    independent methods agree."""

    def __init__(
        self,
        ws: Workspace,
        reader: Reader,
        limits: ReadLimits,
        index: int,
        region: RulesRegion,
        key: str,
        crop: Image.Image,
    ):
        super().__init__()
        self.ws, self.reader, self.limits = ws, reader, limits
        self.index, self.region, self.key, self.crop = index, region, key, crop
        self.cost_usd = 0.0
        self._folder = ws.work / "rules" / "reads"
        self.reads = region_reads(ws.work / "rules", key)
        self._next_index = len(list(self._folder.glob(f"{key}.read*.json")))
        self._ocr_path = self._folder / f"{key}.ocr.txt"
        self.ocr: str | None = self._first_ocr()
        self._proofed = False

    def _first_ocr(self) -> str | None:
        """Tesseract's text if we have it; "" when it is not installed; None when still to do."""
        if self._ocr_path.exists():
            return self._ocr_path.read_text()
        return None if tesseract_installed() else ""

    def next_reads(self) -> list[Read]:
        first = []
        if self.ocr is None:
            first.append(self._ocr)
        if not self.reads:
            first.append(self._read_task())
        if first or self.ocr is None:
            return first
        return self._reads_after_the_first()

    def _reads_after_the_first(self) -> list[Read]:
        reads = self.reads
        if len(reads) == 1 and ocr_confirms(reads[0], self.ocr):
            return []
        if len(reads) < self.limits.min_reads:
            return [self._read_task() for _ in range(self.limits.min_reads - len(reads))]
        if len(reads) < self.limits.max_reads and self._reads_disagree():
            return [self._read_task()]
        return self._proofreading()

    def _reads_disagree(self) -> bool:
        """The reads differ in words and, from the third read on, the merge has no clear winner."""
        reads = self.reads
        if len({tuple(tokens(t)) for t in reads}) == 1:
            return False
        return len(reads) < 3 or bool(merge_reads(reads)[1])

    def _proofreading(self) -> list[Read]:
        if self._proofed:
            return []
        self._proofed = True
        return [
            self._proof_task(half, n)
            for half in range(2)
            for n in range(self.limits.min_reads)
            if not (self._folder / f"{self.key}.proof{half}_{n}.json").exists()
        ]

    # -- the calls

    def _read_task(self) -> Read:
        n = self._next_index
        self._next_index += 1
        return lambda: self._read(n)

    def _proof_task(self, half: int, n: int) -> Read:
        return lambda: self._proof(half, n)

    async def _ocr(self) -> None:
        try:
            text = await asyncio.to_thread(ocr_region, self.ws, self.region)
        except Exception:
            # OCR only saves reads; without it the region is read until the readers agree.
            log.exception("OCR of region %d failed", self.index)
            text = ""
        self._ocr_path.write_text(text)
        self.ocr = text

    async def _read(self, n: int) -> None:
        prompt = RULES_PROMPT
        if self.region.note:
            prompt += f"\n\nNote for this region: {self.region.note}"
        answer = await self.reader.ask([enlarged(self.crop)], prompt, None)
        text = space_dots(html.unescape(answer.output))
        record = {"text": text, "cost_usd": answer.cost_usd, "model": self.reader.model}
        save_json(self._folder / f"{self.key}.read{n}.json", record)
        self.reads.append(text)
        self.cost_usd += answer.cost_usd

    async def _proof(self, half: int, n: int) -> None:
        image = enlarged(halves(self.crop)[half])
        answer = await self.reader.ask([image], PROOF_PROMPT, PROOF_SCHEMA)
        record = {**answer.output, "cost_usd": answer.cost_usd, "model": self.reader.model}
        save_json(self._folder / f"{self.key}.proof{half}_{n}.json", record)
        self.cost_usd += answer.cost_usd


def region_targets(
    ws: Workspace, cfg: ExtractionConfig, reader: Reader, limits: ReadLimits
) -> list[RegionTarget]:
    crops = rules_setup(ws, cfg)
    keys = region_keys(cfg)
    return [
        RegionTarget(ws, reader, limits, i, cfg.rules_regions[i], keys[i], crop)
        for i, crop in crops.items()
    ]


# ---------------------------------------------------------------- the report


def _region_conflicts(ws: Workspace, cfg: ExtractionConfig) -> tuple[list[dict], int, int]:
    """Writes work/rules/region_NN.txt, the merged text of each region. Returns the regions that
    need a look, how many were confirmed by Tesseract after one read, and how many were not but
    had identical reads."""
    folder = ws.work / "rules"
    keys = region_keys(cfg)
    conflicts, confirmed, identical = [], 0, 0
    for i, key in keys.items():
        reads = region_reads(folder, key)
        ocr_file = folder / "reads" / f"{key}.ocr.txt"
        ocr = ocr_file.read_text() if ocr_file.exists() else None
        if len(reads) == 1 and ocr_confirms(reads[0], ocr):
            confirmed += 1
        elif len({tuple(tokens(t)) for t in reads}) == 1:
            identical += 1
        text, unresolved = merge_reads(reads) if reads else ("", [])
        (folder / f"region_{i:02d}.txt").write_text(text)
        spelling = _spelling_of_region(folder, key, text, ocr)
        if not reads:
            unresolved = [
                {"kept": "", "alternatives": ["(no read succeeded; call `read_rules` again)"]}
            ]
        if unresolved or spelling:
            image = ws.rel(folder / f"region_{i:02d}.png")
            conflicts.append(
                {
                    "region": i,
                    "image": image,
                    "reads": len(reads),
                    "unresolved": unresolved,
                    "spelling": spelling,
                }
            )
    return conflicts, confirmed, identical


def _spelling_of_region(folder: Path, key: str, text: str, ocr: str | None) -> list[dict]:
    proof_files = sorted((folder / "reads").glob(f"{key}.proof*.json"))
    proofs = [m for p in proof_files for m in load_json(p)["misspelled"]]
    flags = spelling_flags(text, proofs)
    seen_by_ocr = {bare(w) for w in ocr_words(ocr or "")}
    for flag in flags:
        flag["tesseract_agrees"] = bare(flag["printed"]) in seen_by_ocr
    return flags


def _conflict_lines(conflicts: list[dict[str, Any]]) -> list[str]:
    lines = []
    for c in conflicts:
        lines.append(f"REGION {c['region']} ({c['image']}):")
        for u in c["unresolved"][:10]:
            lines.append(
                f"    NO MAJORITY after {c['reads']} reads. kept: {u['kept']!r}\n"
                f"        alternatives: {u['alternatives']!r}"
            )
        for f in c["spelling"]:
            agrees = "; Tesseract also reads it as printed" if f["tesseract_agrees"] else ""
            lines.append(
                f"    SPELLING: proofreaders saw {f['printed']!r} ({f['context']!r}); "
                f"transcription has {f['transcribed']!r}{agrees}"
            )
    return lines


def rules_report(ws: Workspace, cfg: ExtractionConfig) -> str:
    conflicts, confirmed, identical = _region_conflicts(ws, cfg)
    keys = region_keys(cfg)
    save_json(ws.work / "rules_conflicts.json", conflicts)
    save_json(ws.work / "rules" / "regions.json", keys)

    lines = [
        f"{len(keys)} regions transcribed; {confirmed} confirmed by Tesseract after one read, "
        f"{identical} with all reads identical"
    ]
    if not tesseract_installed():
        lines.append(NO_TESSERACT)
    lines += _conflict_lines(conflicts)
    if any(c["unresolved"] for c in conflicts):
        lines.append(HELP["no_majority"])
    if any(c["spelling"] for c in conflicts):
        lines.append(HELP["rules_spelling"])
    lines.append(
        f"details in {ws.rel(ws.work / 'rules_conflicts.json')}; "
        f"total cost so far: ${total_cost(ws):.4f}"
    )
    lines.append(regions.preview_regions(ws))
    return "\n".join(lines)


async def read_rules(ws: Workspace, reader: Reader, limits: ReadLimits) -> str:
    cfg = ws.load_config()
    targets = region_targets(ws, cfg, reader, limits)
    await run_reads(list(targets), limits.parallel)
    spent = sum(t.cost_usd for t in targets)
    return f"spent ${spent:.4f} on rules reads this run\n" + rules_report(ws, cfg)
