"""Reading the components: what readers are asked, how their answers are voted into one value
per design, and the target that reads a design until every value has a majority."""

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from PIL import Image

from .models import ExtractionConfig, Item, ItemSource, Kind, KindField
from .orient import DIRECTIONS, image_id, orientation
from .queue import Read, ReadLimits, ReadTarget
from .reader import Reader
from .voting import clean, merge_reads, spelling_flags, vote
from .workspace import ExtractionError, Workspace, load_json, save_json

# ---------------------------------------------------------------- what readers are asked


def field_schema(field: KindField) -> dict[str, Any]:
    match field.type:
        case "integer":
            return {"type": ["integer", "null"]}
        case "enum":
            return {"enum": [*(field.enum_values or []), None]}
        case "list":
            return {"type": ["array", "null"], "items": {"type": ["string", "integer"]}}
        case _:
            return {"type": ["string", "null"]}


def _kind_schema(kind: Kind) -> dict[str, Any]:
    return {
        "type": ["object", "null"],
        "additionalProperties": False,
        "required": [f.name for f in kind.fields],
        "properties": {f.name: field_schema(f) for f in kind.fields},
    }


def reader_schema(cfg: ExtractionConfig) -> dict[str, Any]:
    kind_ids = [k.id for k in cfg.kinds]
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "observations",
            "text_direction",
            "kind",
            "title",
            "fields",
            "mismatch",
            "text",
            "misspelled",
            "unreadable",
        ],
        "properties": {
            "observations": {"type": "string"},
            "text_direction": {"enum": DIRECTIONS},
            "kind": {"enum": [*kind_ids, "other"]},
            "title": {"type": ["string", "null"]},
            "fields": {
                "type": "object",
                "additionalProperties": False,
                "required": kind_ids,
                "properties": {k.id: _kind_schema(k) for k in cfg.kinds},
            },
            "text": {"type": ["string", "null"]},
            "misspelled": {"type": "array", "items": {"type": "string"}},
            "mismatch": {"type": "string"},
            "unreadable": {"type": "string"},
        },
    }


def _kind_lines(kind: Kind) -> list[str]:
    lines = [f"- kind `{kind.id}` ({kind.name}): {kind.description}"]
    for f in kind.fields:
        allowed = f" Allowed values: {', '.join(f.enum_values)}." if f.type == "enum" else ""
        lines.append(f"    - field `{f.name}` ({f.type}): {f.description}{allowed}")
    return lines


def reader_prompt(cfg: ExtractionConfig, has_back: bool) -> str:
    lines = [
        "Image 1 is the front of ONE physical game component"
        + (", image 2 is its back." if has_back else "."),
        "",
        "Possible kinds of component:",
    ]
    for kind in cfg.kinds:
        lines += _kind_lines(kind)
    lines += [
        "- kind `other`: it matches none of the above.",
        "",
        "Fill in the JSON:",
        "- observations: first, briefly, for the fields of this kind only: where each value is "
        "printed, and for every counted symbol, each one with its position, counted one by one; "
        "tell symbol types apart (filled or hollow, colour, shape). Don't describe pictures or "
        "decoration.",
        "- text_direction: which way the main printed text (title, labels) runs in image 1 as you "
        "see it: 'upright', 'bottom to top' (lines run upwards), 'top to bottom' (lines run "
        "downwards), 'upside down', or 'no text'.",
        "- kind: which kind this is, judged only from what is printed.",
        "- fields: fill only the object for that kind, using your observations; set every other "
        "kind's object to null. Use null for a value that is not printed or cannot be read.",
        "- mismatch: anything in the description of the kind you chose, or of its fields, that "
        "does not match image 1 as you see it, for example a strip described on the left that is "
        "printed along the top, or symbols that are not where a field says they are; empty string "
        "if it all matches.",
        "- title: the printed name on the front (image 1), exactly as printed, letter by letter, "
        "including spelling mistakes and typos (a later step looks for these, so a corrected word "
        "is an error); capitals and punctuation as printed; null if none.",
        "- text: all other printed text on the front, verbatim and letter by letter in the same "
        "way, with dashes (- – —) and quotes (' ’ \" “ ”) as printed, lines joined with ' / '. "
        "Leave out the title, values already recorded in fields, and illegible decorative fine "
        "print. null if none.",
        "- misspelled: every word in the title or text that is printed with a spelling mistake or "
        "typo, copied exactly as printed; [] if none.",
        "- unreadable: anything you could not read, and why; empty string if none.",
    ]
    if has_back:
        lines.append("Image 2 only helps recognise the kind: take no title or text from the back.")
    return "\n".join(lines)


# ---------------------------------------------------------------- voting a design's reads


def _normalised_title(title: str | None) -> str:
    return re.sub(r"\s+", " ", title or "").strip()


def _vote_kind(outs: list[dict]) -> str | None:
    """The kind most reads chose, or None when there is no majority."""
    ok, winner, _ = vote([o["kind"] for o in outs])
    return json.loads(winner) if ok else None


def _vote_text(texts: list[str | None]) -> tuple[str | None, list[dict]]:
    """The merged text of the reads, and the passages they could not settle."""
    if not any(texts):
        return None, []
    merged, unresolved = merge_reads([t or "" for t in texts])
    return merged.strip() or None, unresolved


def resolve(
    cfg: ExtractionConfig, reads: list[dict[str, Any]], kind: str | None = None
) -> tuple[dict[str, Any], list[str], bool]:
    """Per-attribute majority over a design's reads. Returns (values, unsettled, text_settled).

    `kind` comes from an override; its fields are then voted among the reads that filled them
    in, so fields the override doesn't set still need a majority."""
    outs = [clean(r["output"]) for r in reads]
    if kind is None:
        kind = _vote_kind(outs)
        if kind is None:
            return {"votes": {"kind": [o["kind"] for o in outs]}}, ["kind"], False
    same = [o for o in outs if o["kind"] == kind]
    if len(same) < 2:
        same = outs
    values: dict[str, Any] = {"kind": kind}
    unsettled: list[str] = []
    votes: dict[str, Any] = {}
    if kind == "other":
        unsettled.append("kind")

    ok, title, _ = vote([o["title"] for o in same], key=_normalised_title)
    values["title"] = json.loads(title) if ok else None
    if not ok:
        unsettled.append("title")
        votes["title"] = [o["title"] for o in same]

    kind_def = next((k for k in cfg.kinds if k.id == kind), None)
    fields: dict[str, Any] = {}
    for f in kind_def.fields if kind_def else []:
        got = [o["fields"][kind].get(f.name) for o in same if o["fields"].get(kind) is not None]
        ok, value, _ = vote(got)
        fields[f.name] = json.loads(value) if ok else None
        if not ok:
            unsettled.append(f"fields.{f.name}")
            votes[f"fields.{f.name}"] = got
    values["fields"] = fields

    values["text"], unresolved = _vote_text([o["text"] for o in same])
    if unresolved:
        votes["text"] = unresolved
    values["votes"] = votes
    return values, unsettled, not unresolved


# ---------------------------------------------------------------- read files


def _hash(data: Any) -> str:
    return hashlib.sha1(json.dumps(data, sort_keys=True).encode()).hexdigest()[:12]


def kind_hashes(cfg: ExtractionConfig) -> dict[str, str]:
    """What readers are told about each kind. `other` depends on every kind's description."""
    hashes = {}
    for kind in cfg.kinds:
        told = kind.model_dump(mode="json", include={"name", "description", "fields"})
        hashes[kind.id] = _hash(told)
    hashes["other"] = _hash(hashes)
    return hashes


def read_index(ws: Workspace, cfg: ExtractionConfig) -> dict[str, list[dict[str, Any]]]:
    """Reads per item, keeping only reads of the item's current crop, made while the kind the
    reader chose was described as it is now: re-cropping, rotating, regrouping or rewriting a
    kind never reuses a read made under other conditions."""
    crops: dict[str, str | None] = {}
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    hashes = kind_hashes(cfg)
    for path in sorted((ws.work / "reads").glob("*/*.json")):
        record = load_json(path)
        key = record["item"]
        if key not in crops:
            crops[key] = image_id(ws, key) if ws.item_dir(key).exists() else None
        current_hash = hashes.get(record["output"]["kind"])
        same_crop = record.get("image") == crops[key]
        same_kind_def = record.get("kind_def", current_hash) == current_hash
        if same_crop and same_kind_def:
            index[key].append(record)
    return index


def design_reads(index: dict[str, list[dict]], members: list[str]) -> list[dict]:
    return [r for key in members for r in index.get(key, [])]


def noted(mismatch: str | None) -> bool:
    """Whether a reader said the description does not match."""
    return (mismatch or "").strip(" \"'.").lower() not in ("", "none")


def mismatched_kinds(reads: dict[str, list[dict[str, Any]]]) -> set[str]:
    """Kinds that most of their reads say are described wrongly, once at least four reads chose
    them. `reads` is the reads per design."""
    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for design_reads_ in reads.values():
        for r in design_reads_:
            kind = r["output"]["kind"]
            counts[kind][0] += noted(r["output"].get("mismatch"))
            counts[kind][1] += 1
    return {k for k, (n, total) in counts.items() if k != "other" and total >= 4 and n * 2 > total}


# ---------------------------------------------------------------- reading a design


def _override_values(cfg: ExtractionConfig, design: str) -> dict[str, Any]:
    override = cfg.overrides.get(design)
    return override.set if override else {}


class DesignTarget(ReadTarget):
    """Reads a design until every value has a majority. A design gets one read first; if it is
    read sideways it is not read further, so the bulk of its reading waits until it is turned."""

    def __init__(
        self,
        ws: Workspace,
        cfg: ExtractionConfig,
        reader: Reader,
        limits: ReadLimits,
        design: str,
        members: list[str],
        all_reads: dict[str, list[dict[str, Any]]],
    ):
        super().__init__()
        self.ws, self.cfg, self.reader, self.limits = ws, cfg, reader, limits
        self.design, self.members = design, members
        # The reads of every design being read: a kind is judged wrong across all of them.
        self.all_reads = all_reads
        self.cost_usd = 0.0
        self._schema = reader_schema(cfg)
        self._kind_hashes = kind_hashes(cfg)
        self._folder = ws.work / "reads" / design
        self._next_index = len(list(self._folder.glob("*.json")))

    @property
    def reads(self) -> list[dict[str, Any]]:
        return self.all_reads[self.design]

    def next_reads(self) -> list[Read]:
        return [self._read_task() for _ in range(self._reads_needed())]

    def _reads_needed(self) -> int:
        reads = self.reads
        override = _override_values(self.cfg, self.design)
        read_upright = override.get("orientation") == "upright"
        if len(reads) >= self.limits.max_reads or (orientation(reads) and not read_upright):
            return 0
        if reads and not override.get("kind") and self._kind_is_mismatched():
            return 0
        if not reads:
            return 1
        if len(reads) < self.limits.min_reads:
            return self.limits.min_reads - len(reads)
        _, unsettled, text_settled = resolve(self.cfg, reads, override.get("kind"))
        return 1 if unsettled or not text_settled else 0

    def _kind_is_mismatched(self) -> bool:
        most_chosen = Counter(r["output"]["kind"] for r in self.reads).most_common(1)[0][0]
        return most_chosen in mismatched_kinds(self.all_reads)

    def _read_task(self) -> Read:
        n = self._next_index
        self._next_index += 1
        return lambda: self._read(n)

    async def _read(self, n: int) -> None:
        key = self.members[n % len(self.members)]
        folder = self.ws.item_dir(key)
        images = [Image.open(folder / "front.png")]
        if (folder / "back.png").exists():
            images.append(Image.open(folder / "back.png"))
        prompt = reader_prompt(self.cfg, has_back=len(images) == 2)
        answer = await self.reader.ask(images, prompt, self._schema)
        record = {
            "item": key,
            "image": image_id(self.ws, key),
            "kind_def": self._kind_hashes.get(answer.output["kind"]),
            "model": self.reader.model,
            "output": answer.output,
            "cost_usd": answer.cost_usd,
        }
        save_json(self._folder / f"{n:02d}.json", record)
        self.reads.append(record)
        self.cost_usd += answer.cost_usd


def design_targets(
    ws: Workspace,
    cfg: ExtractionConfig,
    reader: Reader,
    limits: ReadLimits,
    designs: list[str] | None = None,
) -> list[DesignTarget]:
    """One target per design (only those in `designs`, when given)."""
    groups = load_json(ws.work / "groups.json")
    if groups is None:
        raise ExtractionError("there are no designs yet; call `crop`, then `group`")
    index = read_index(ws, cfg)
    wanted = {d: ms for d, ms in groups["designs"].items() if not designs or d in designs}
    all_reads = {d: design_reads(index, ms) for d, ms in wanted.items()}
    return [
        DesignTarget(ws, cfg, reader, limits, design, members, all_reads)
        for design, members in wanted.items()
    ]


# ---------------------------------------------------------------- the resolved designs


def apply_override(values: dict[str, Any], set_values: dict[str, Any]) -> None:
    """Put the agent's values over the voted ones (`fields.<name>` sets one field)."""
    for key, value in set_values.items():
        if key.startswith("fields."):
            values.setdefault("fields", {})[key.removeprefix("fields.")] = value
        else:
            values[key] = value


def _unanimous(reads: list[dict[str, Any]], unsettled: list[str]) -> bool:
    """All reads gave the same answer, or at least the same kind and fields with all settled."""
    if all(r["output"] == reads[0]["output"] for r in reads):
        return True
    same_fields = len({json.dumps(r["output"]["fields"], sort_keys=True) for r in reads}) == 1
    same_kind = len({r["output"]["kind"] for r in reads}) == 1
    return not unsettled and same_fields and same_kind


def build_resolved(ws: Workspace, cfg: ExtractionConfig) -> tuple[dict, dict[str, dict]]:
    """The groups, and for each design its voted values with how sure they are."""
    groups = load_json(ws.work / "groups.json")
    if groups is None:
        raise ExtractionError("there are no designs yet; call `crop`, then `group`")
    index = read_index(ws, cfg)
    designs: dict[str, dict] = {}
    for design, members in groups["designs"].items():
        reads = design_reads(index, members)
        if not reads:
            designs[design] = {"members": members, "reads": 0, "unsettled": ["unread"]}
            continue
        designs[design] = _resolve_design(cfg, design, members, reads)
    return groups, designs


def _resolve_design(
    cfg: ExtractionConfig, design: str, members: list[str], reads: list[dict[str, Any]]
) -> dict[str, Any]:
    override = _override_values(cfg, design)
    values, unsettled, text_settled = resolve(cfg, reads, override.get("kind"))
    unanimous = _unanimous(reads, unsettled)
    values["orientation"] = orientation(reads)
    ok, majority, _ = vote([r["output"]["kind"] for r in reads])
    values["read_kind"] = json.loads(majority) if ok else None
    values["mismatch"] = [(r["output"]["kind"], r["output"].get("mismatch", "")) for r in reads]
    overridden = design in cfg.overrides
    if overridden:
        apply_override(values, override)
        unsettled = [u for u in unsettled if u not in override]
    proofs = [
        {"printed": w, "context": ""} for r in reads for w in r["output"].get("misspelled") or []
    ]
    values["spelling"] = spelling_flags(
        f"{values.get('title') or ''}\n{values.get('text') or ''}", proofs
    )
    return values | {
        "members": members,
        "reads": len(reads),
        "unsettled": unsettled,
        "text_settled": text_settled,
        "unanimous": unanimous,
        "overridden": overridden,
    }


# ---------------------------------------------------------------- components named in the rules


def expand_rules_items(cfg: ExtractionConfig) -> list[Item]:
    """Components the rules name that no file shows: one item per physical piece.

    The config validation has already refused unknown kinds and undeclared fields."""
    kinds = {k.id: k for k in cfg.kinds}
    seen: Counter[tuple[str, int, str]] = Counter()
    items = []
    for entry in cfg.rules_items:
        stem, page = Path(entry.source.file).stem, entry.source.page
        declared = [f.name for f in kinds[entry.kind].fields]
        for _ in range(entry.count):
            seen[(stem, page, entry.kind)] += 1
            n = seen[(stem, page, entry.kind)]
            items.append(
                Item(
                    id=f"{stem}#p{page}_{entry.kind}_{n:02d}",
                    kind=entry.kind,
                    source=ItemSource(file=entry.source.file, page=page),
                    title=entry.title,
                    fields={f: entry.fields.get(f) for f in declared},
                    text=entry.text,
                    from_rules=True,
                    confidence="high",
                )
            )
    return items
