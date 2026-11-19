"""Which way the text runs on each design: cheap reads that find sideways items before the
bulk reading, and the report that tells the agent which items to turn."""

import hashlib
import json
from collections import Counter, defaultdict
from typing import Any

from PIL import Image

from .queue import Read, ReadLimits, ReadTarget, run_reads
from .reader import Reader
from .voting import vote
from .workspace import ExtractionError, Workspace, load_json, save_json

DIRECTIONS = ["upright", "bottom to top", "top to bottom", "upside down", "no text"]
TURN = {"bottom to top": 90, "top to bottom": 270, "upside down": 180}
"""The clockwise turn that makes an item upright."""

ORIENTATION_NEXT = (
    "Designs read sideways were read only once. Check one crop per ORIENTATION line. If it is "
    "really not upright, fix `rotate` / `rotate_items` and call `crop`, then `group`. Positions "
    "turn with the item (a strip on the left of a sideways card runs along the top of the upright "
    "one), so then open one turned crop of each kind named and rewrite every position in that "
    "kind's description and fields for the turned crop. Then call `read`; reads of unchanged "
    "crops are kept. If a crop is upright, record "
    '`{"set": {"orientation": "upright"}, "reason": "..."}` for its design in `overrides` and '
    "call `read` again."
)

ORIENT_PROMPT = (
    "Image 1 is one printed game component. Which way does its main printed text (title, labels) "
    "run in the image as you see it: 'upright', 'bottom to top' (lines run upwards), "
    "'top to bottom' (lines run downwards), 'upside down', or 'no text'?"
)
ORIENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["text_direction"],
    "properties": {"text_direction": {"enum": DIRECTIONS}},
}

AGREEING_READS = 2
MAX_ORIENT_READS = 3


def image_id(ws: Workspace, key: str) -> str:
    """A short hash of the crop of an item. A read is only valid for the crop it was made from."""
    digest = hashlib.sha1()
    for name in ("front.png", "back.png"):
        path = ws.item_dir(key) / name
        if path.exists():
            digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def orientation(reads: list[dict[str, Any]]) -> str | None:
    """The direction most reads see the text running in, if that is sideways or upside down."""
    counts = Counter(r["output"].get("text_direction") for r in reads)
    sideways = [(n, direction) for direction, n in counts.items() if direction in TURN]
    n, direction = max(sideways, default=(0, None))
    return direction if n * 2 > len(reads) else None


def read_as_text(kinds: set[str]) -> str:
    return f" Read as: {', '.join(sorted(kinds))}." if kinds else ""


# ---------------------------------------------------------------- the reads


def _directions(reads: list[dict[str, Any]]) -> list[str]:
    return [r["output"]["text_direction"] for r in reads]


class OrientTarget(ReadTarget):
    """Two reads of the front of a design, a third where they differ. Reads are kept per crop
    image, so after turning items only the changed crops are read again."""

    def __init__(
        self, ws: Workspace, reader: Reader, design: str, members: list[str], reads: list[dict]
    ):
        super().__init__()
        self.ws, self.reader = ws, reader
        self.design, self.members = design, members
        self.reads = reads
        self.cost_usd = 0.0
        self._folder = ws.work / "orient" / design
        self._next_index = len(list(self._folder.glob("*.json")))

    def next_reads(self) -> list[Read]:
        have = len(self.reads)
        if have < AGREEING_READS:
            wanted = AGREEING_READS - have
        elif have < MAX_ORIENT_READS and not vote(_directions(self.reads))[0]:
            wanted = 1
        else:
            return []
        return [self._read_task() for _ in range(wanted)]

    def _read_task(self) -> Read:
        n = self._next_index
        self._next_index += 1
        return lambda: self._read(n)

    async def _read(self, n: int) -> None:
        key = self.members[n % len(self.members)]
        front = Image.open(self.ws.item_dir(key) / "front.png")
        answer = await self.reader.ask([front], ORIENT_PROMPT, ORIENT_SCHEMA)
        record = {
            "item": key,
            "image": image_id(self.ws, key),
            "model": self.reader.model,
            "output": answer.output,
            "cost_usd": answer.cost_usd,
        }
        save_json(self._folder / f"{n:02d}.json", record)
        self.reads.append(record)
        self.cost_usd += answer.cost_usd


def _current_orient_reads(ws: Workspace) -> dict[str, list[dict[str, Any]]]:
    """The orientation reads per item whose crop has not changed since."""
    reads: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in sorted((ws.work / "orient").glob("*/*.json")):
        record = load_json(path)
        key = record["item"]
        if ws.item_dir(key).exists() and record["image"] == image_id(ws, key):
            reads[key].append(record)
    return reads


async def orient_designs(ws: Workspace, reader: Reader, limits: ReadLimits) -> str:
    """Two cheap reads per design, front only, asking only which way the text runs; a third where
    they differ."""
    groups = load_json(ws.work / "groups.json")
    if groups is None:
        raise ExtractionError("there are no designs yet; call `crop`, then `group`")
    by_item = _current_orient_reads(ws)
    targets = [
        OrientTarget(ws, reader, design, members, [r for k in members for r in by_item[k]])
        for design, members in groups["designs"].items()
    ]
    await run_reads(list(targets), limits.parallel)

    designs, unsure = {}, []
    for target in targets:
        ok, winner, _ = vote(_directions(target.reads))
        if not ok:
            unsure.append(f"{target.design} ({', '.join(_directions(target.reads))})")
        designs[target.design] = {
            "members": target.members,
            "orientation": json.loads(winner) if ok else None,
        }
    spent = sum(t.cost_usd for t in targets)
    return "\n".join(_orient_summary(spent, orientation_report(ws, designs), unsure))


def _orient_summary(spent: float, sideways: list[str], unsure: list[str]) -> list[str]:
    lines = [f"spent ${spent:.4f} on orientation reads this run", *sideways]
    if unsure:
        lines.append(
            "UNSURE: readers disagree on which way the text runs on "
            + "; ".join(unsure)
            + ". Open one crop of each and turn it with `rotate_items` if it isn't upright."
        )
    if sideways or unsure:
        lines.append(
            "Turn the items, then call `crop`, `group` and `orient` again until no ORIENTATION "
            "lines are left; only changed crops are read again. Write `kinds` only after that, "
            "from the upright contact sheets and crops: every position in a description is a "
            "position on the upright item."
        )
    else:
        lines.append(
            "All designs read upright. Write `kinds` from the upright contact sheets and crops."
        )
    return lines


# ---------------------------------------------------------------- the report


def orientation_report(ws: Workspace, designs: dict[str, dict[str, Any]]) -> list[str]:
    """Sideways items per page and direction, as r<row>c<col>, or r<row> when the whole row is.
    Items from image files are listed by name."""
    items = {i["key"]: i for i in load_json(ws.work / "items.json", [])}
    cells: dict[tuple, set[tuple[int, int]]] = defaultdict(set)
    names: dict[str, list[str]] = defaultdict(list)
    kinds: dict[Any, set[str]] = defaultdict(set)
    for design in designs.values():
        direction = design.get("orientation")
        if direction not in TURN:
            continue
        read_as = (
            [design["kind"]] if design.get("kind") else design.get("votes", {}).get("kind", [])
        )
        for key in design["members"]:
            item = items[key]
            if "row" in item:
                where = (item["file"], item["page"], direction)
                cells[where].add((item["row"], item["col"]))
            else:
                where = direction
                names[where].append(item["label"])
            kinds[where].update(k for k in read_as if k)

    lines = [
        _file_line(direction, labels, kinds[direction])
        for direction, labels in sorted(names.items())
    ]
    for (file, page, direction), found in sorted(cells.items()):
        row_lengths = Counter(
            i["row"]
            for i in items.values()
            if "row" in i and i["file"] == file and i["page"] == page
        )
        lines.append(
            _page_line(file, page, direction, found, row_lengths, kinds[(file, page, direction)])
        )
    return lines


def _file_line(direction: str, labels: list[str], kinds: set[str]) -> str:
    return (
        f"ORIENTATION item files: readers see the text running {direction} on {len(labels)} "
        f"items: {' '.join(sorted(labels))}. Turn them a further {TURN[direction]} degrees "
        f"clockwise (`rotate_items`)." + read_as_text(kinds)
    )


def _page_line(
    file: str,
    page: int,
    direction: str,
    found: set[tuple[int, int]],
    row_lengths: Counter,
    kinds: set[str],
) -> str:
    labels: list[str] = []
    for row in sorted({r for r, _ in found}):
        cols = sorted(c for r, c in found if r == row)
        whole_row = len(cols) == row_lengths[row]
        labels += [f"r{row}"] if whole_row else [f"r{row}c{c}" for c in cols]
    return (
        f"ORIENTATION {file} page {page}: readers see the text running {direction} on "
        f"{len(found)} items: {' '.join(labels)}. Turn them a further {TURN[direction]} degrees "
        f"clockwise (`rotate` / `rotate_items`)." + read_as_text(kinds)
    )
