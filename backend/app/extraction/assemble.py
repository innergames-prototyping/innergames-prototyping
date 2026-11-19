"""Puts the rules text, the components and a review page together from everything settled.

Writes `results/rules.md`, `work/components.json` (every item with its paper trail),
`results/components.json` (what the later steps read) and `work/review.html`.
"""

import json
from collections import Counter
from html import escape
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from . import components, regions, rules
from .cost import total_cost
from .models import (
    Component,
    ComponentRecord,
    ComponentsFile,
    ExportedKind,
    ExtractionConfig,
    Item,
    ItemSource,
    KindSummary,
)
from .orient import TURN
from .workspace import ExtractionError, Workspace, load_json, save_json

# ---------------------------------------------------------------- rules text


def _check_regions_unchanged(ws: Workspace, cfg: ExtractionConfig) -> None:
    saved = load_json(ws.work / "rules" / "regions.json")
    current = {str(i): key for i, key in rules.region_keys(cfg).items()}
    if saved != current:
        raise ExtractionError(
            "rules_regions changed since the last `read_rules` run; call `read_rules` again"
        )


def rules_text(ws: Workspace, cfg: ExtractionConfig, force: bool) -> str:
    """The transcriptions of all regions in order, with `rules_fixes` applied."""
    _check_regions_unchanged(ws, cfg)
    if regions.coverage(ws, cfg) and not force:
        raise ExtractionError(
            "text outside every rules region; call `preview_regions`, then cover it or list it "
            "in `rules_excluded`"
        )
    parts = []
    for i in range(len(cfg.rules_regions)):
        path = ws.work / "rules" / f"region_{i:02d}.txt"
        if not path.exists():
            raise ExtractionError(f"rules region {i} not transcribed; call `read_rules` first")
        parts.append(path.read_text().strip())
    text = "\n\n".join(parts) + "\n"
    for fix in cfg.rules_fixes:
        if fix.find not in text:
            raise ExtractionError(f"rules_fixes: {fix.find!r} not found")
        text = text.replace(fix.find, fix.replace)
    return text


# ---------------------------------------------------------------- items


def _check_designs(cfg: ExtractionConfig, designs: dict[str, dict], force: bool) -> None:
    declared = {k.id: {f"fields.{f.name}" for f in k.fields} for k in cfg.kinds}
    blank = [
        d
        for d, v in designs.items()
        if declared.get(v.get("kind")) and declared[v["kind"]] <= set(v["unsettled"])
    ]
    if blank:
        raise ExtractionError(
            f"designs {blank} have no value for any field of their kind, so readers didn't read "
            "them as that kind. Rewrite the kind's description for the crop as readers see it and "
            "call `read` again; `force` doesn't cover these. If the image really shows no legible "
            "value, set each field to null by override with the reason."
        )
    open_designs = [d for d, v in designs.items() if v["unsettled"] or v.get("orientation") in TURN]
    if open_designs and not force:
        raise ExtractionError(
            f"unresolved or sideways designs {open_designs}; resolve them (see `check`), or "
            "assemble with `force` to mark them low confidence"
        )


def _item_source(it: dict[str, Any]) -> tuple[ItemSource, str]:
    """Where an item came from in the files, and its id."""
    if "row" not in it:
        return ItemSource(file=it["file"], page=it["page"]), it["label"]
    extra = {k: it[k] for k in ("back_page", "back_row", "back_col") if k in it}
    source = ItemSource(file=it["file"], page=it["page"], row=it["row"], col=it["col"], **extra)
    return source, f"{Path(it['file']).stem}#p{it['page']}_r{it['row']}_c{it['col']}"


def _item_values_and_notes(
    cfg: ExtractionConfig, key: str, design: str, v: dict[str, Any]
) -> list[str]:
    """Applies an override for this item key to `v` in place; returns the notes for the item."""
    notes = [
        f"design {design} ({len(v['members'])} identical copies); {v['reads']} independent reads"
    ]
    if key in cfg.overrides:
        components.apply_override(v, cfg.overrides[key].set)
        notes.append(f"overridden: {cfg.overrides[key].reason}")
    if v.get("overridden"):
        notes.append(f"design overridden: {cfg.overrides[design].reason}")
    return notes


def _confidence(v: dict[str, Any]) -> str:
    if v["unsettled"]:
        return "low"
    if v.get("unanimous") and not v.get("overridden"):
        return "high"
    return "medium"


def build_items(
    cfg: ExtractionConfig, items: list[dict], groups: dict, designs: dict[str, dict]
) -> list[Item]:
    item_design = {k: d for d, members in groups["designs"].items() for k in members}
    kinds = {k.id: k for k in cfg.kinds}
    out = []
    for it in items:
        design = item_design[it["key"]]
        v = dict(designs[design])
        v["fields"] = dict(v.get("fields") or {})
        notes = _item_values_and_notes(cfg, it["key"], design, v)
        if v.get("orientation") in TURN:
            v["unsettled"] = v["unsettled"] + ["orientation"]
        if v["unsettled"]:
            votes = json.dumps(v.get("votes", {}), ensure_ascii=False)
            notes.append(f"unresolved: {v['unsettled']} votes {votes}")
        if not v.get("text_settled", True):
            notes.append("text: reads differed; closest-to-consensus read kept")

        kind = v.get("kind") if v.get("kind") in kinds else "other"
        declared = kinds[kind].fields if kind in kinds else []
        source, item_id = _item_source(it)
        out.append(
            Item(
                id=item_id,
                kind=kind,
                source=source,
                title=v.get("title"),
                fields={f.name: v["fields"].get(f.name) for f in declared},
                text=v.get("text"),
                from_rules=False,
                confidence=_confidence(v),
                notes="; ".join(notes),
            )
        )
    return out + components.expand_rules_items(cfg)


# ---------------------------------------------------------------- kinds and notes


def kind_summaries(cfg: ExtractionConfig, items: list[Item]) -> list[KindSummary]:
    count = Counter(i.kind for i in items)
    summaries = [
        KindSummary(
            id=k.id,
            name=k.name,
            fields=k.fields,
            count_found=count[k.id],
            count_in_rules=k.count_in_rules,
            back=k.back,
            notes=k.notes,
        )
        for k in cfg.kinds
    ]
    if count["other"]:
        summaries.append(
            KindSummary(
                id="other",
                name="Unclassified",
                fields=[],
                count_found=count["other"],
                notes="Readers could not agree on a kind.",
            )
        )
    return summaries


def extraction_notes(ws: Workspace, cfg: ExtractionConfig, designs: dict[str, dict]) -> list[str]:
    unanimous = sum(1 for v in designs.values() if v.get("unanimous"))
    by_hand = sum(1 for v in designs.values() if v.get("overridden"))
    return cfg.extraction_notes + [
        f"Each of {len(designs)} unique designs (pixel-identical fronts grouped) was read by "
        "independent single-component model calls until every value had a majority; "
        f"{unanimous} designs were unanimous, {by_hand} were resolved by hand.",
        f"Model cost of all reads: ${total_cost(ws):.4f}.",
    ]


# ---------------------------------------------------------------- export


def export(record: ComponentRecord) -> ComponentsFile:
    """The extraction for the steps after it: no sources, ids, notes or confidence, and items
    that are identical without them merged into one entry with a count. An item counted from the
    rules joins the one variant shown in the files whose kind and fields it matches; the rules'
    name for it doesn't keep it apart."""
    merged: dict[str, dict[str, Any]] = {}

    def add(item: Item, key: str | None = None) -> None:
        piece = {
            name: value
            for name in ("title", "fields", "text", "back")
            if (value := getattr(item, name)) not in (None, {})
        }
        key = key or json.dumps([item.kind, piece], sort_keys=True)
        entry = merged.setdefault(key, {"kind": item.kind, "count": 0} | piece)
        entry["count"] += 1
        for name in ("title", "text"):
            if getattr(item, name) and name not in entry:
                entry[name] = getattr(item, name)

    for item in record.items:
        if not item.from_rules:
            add(item)
    shown = dict(merged)
    for item in record.items:
        if item.from_rules:
            same = [
                key
                for key, entry in shown.items()
                if entry["kind"] == item.kind and entry.get("fields", {}) == (item.fields or {})
            ]
            add(item, same[0] if len(same) == 1 else None)

    kinds = [
        ExportedKind(id=k.id, name=k.name, fields=k.fields or None, back=k.back)
        for k in record.component_kinds
    ]
    return ComponentsFile(
        game=record.game,
        component_kinds=kinds,
        components=[Component(**entry) for entry in merged.values()],
    )


# ---------------------------------------------------------------- review page


def write_review(ws: Workspace, cfg: ExtractionConfig) -> Path:
    """Each rules region beside its transcription, with fixes and flags, for a final read by a
    person."""
    flags = {c["region"]: c for c in load_json(ws.work / "rules_conflicts.json", [])}
    parts = []
    for i, region in enumerate(cfg.rules_regions):
        text = escape((ws.work / "rules" / f"region_{i:02d}.txt").read_text())
        for fix in cfg.rules_fixes:
            text = text.replace(escape(fix.find), f"<mark>{escape(fix.replace)}</mark>")
        flag = flags.get(i, {})
        notes = [
            f"no majority: {escape(u['kept'])} / {' / '.join(map(escape, u['alternatives']))}"
            for u in flag.get("unresolved", [])
        ]
        notes += [
            f"proofreaders saw {escape(f['printed'])}, transcribed {escape(f['transcribed'])}"
            for f in flag.get("spelling", [])
        ]
        parts.append(
            f"<h2>Region {i}: {escape(Path(region.file).name)} page {region.page}</h2>"
            + "".join(f"<p class=flag>{n}</p>" for n in notes)
            + f"<div class=row><img src='rules/region_{i:02d}.png'><pre>{text}</pre></div>"
        )
    path = ws.work / "review.html"
    path.write_text(
        "<!doctype html><meta charset=utf-8><title>Rules review</title><style>"
        "body{font-family:sans-serif;margin:16px}"
        ".row{display:grid;grid-template-columns:1fr 1fr;gap:16px}"
        "img{width:100%;border:1px solid #ccc}"
        "pre{white-space:pre-wrap;font-size:15px;margin:0}"
        "mark{background:#ff0}.flag{color:#b00;margin:4px 0}</style>"
        "<p>Each rules region beside its transcription. Fixes from the config are highlighted; "
        "flags from the readers are in red. Read every region against its image.</p>"
        + "".join(parts)
    )
    return path


# ---------------------------------------------------------------- the step


def assemble(ws: Workspace, force: bool = False) -> str:
    cfg = ws.load_config()
    if cfg.game is None:
        raise ExtractionError("`game` is not set; set it with `update_config` (title, credits)")
    ws.results.mkdir(parents=True, exist_ok=True)

    rules_path = ws.results / "rules.md"
    rules_path.write_text(rules_text(ws, cfg, force))
    write_review(ws, cfg)

    groups, designs = components.build_resolved(ws, cfg)
    _check_designs(cfg, designs, force)
    items = build_items(cfg, load_json(ws.work / "items.json"), groups, designs)

    record_path = ws.work / "components.json"
    data = {
        "spec_version": "extraction-1.0",
        "game": cfg.game.model_dump(mode="json"),
        "sources": [s.model_dump(mode="json") for s in cfg.sources],
        "component_kinds": [k.model_dump(mode="json") for k in kind_summaries(cfg, items)],
        "items": [i.model_dump(mode="json") for i in items],
        "extraction_notes": extraction_notes(ws, cfg, designs),
    }
    # Written before validation, as Luc did, so the agent can open what is wrong.
    save_json(record_path, data)
    try:
        record = ComponentRecord.model_validate(data)
    except ValidationError as e:
        return f"wrote {ws.rel(record_path)}: INVALID; results/components.json not written\n{e}"

    exported = export(record)
    save_json(ws.results / "components.json", exported.model_dump(mode="json", exclude_none=True))

    count = Counter(i.kind for i in record.items)
    return (
        f"wrote {ws.rel(ws.work / 'components.json')}, {ws.rel(rules_path)} and "
        f"{ws.rel(ws.results / 'components.json')}: VALID\n"
        f"review page: {ws.rel(ws.work / 'review.html')}\n"
        f"items per kind: {dict(count)}"
    )
