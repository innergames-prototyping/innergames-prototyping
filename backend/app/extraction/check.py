"""The checks after the reads: what is still open before the agent can assemble.

`build_report` finds the problems, `format_report` turns them into the text the agent sees, and
`run_check` does both and saves `work/check.json`.
"""

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any

from . import components
from .cost import total_cost
from .models import Expect, ExtractionConfig
from .orient import ORIENTATION_NEXT, orientation_report
from .workspace import Workspace, load_json, save_json

ONLY_THE_IMAGE = (
    "Decide only from the image: never guess, and never set a value to agree with the rules or a "
    "count check. If the image doesn't settle it, leave it."
)

HELP = {
    "conflict": (
        "CONFLICT is a value without a majority. Record what the image shows in `overrides`: "
        '`"d042": {"set": {"fields.gold": 3}, "reason": "counted 3 filled circles at full size"}`. '
        "Keys are `kind`, `title`, `text`, `fields.<name>`; use an item key (`work/items/<key>`) "
        "instead of a design id when only one copy differs. Override `kind` only for a design or "
        "two that readers misjudge, and then also set its fields that stay in CONFLICT. "
        + ONLY_THE_IMAGE
        + " `assemble` with `force` marks what is left `low` confidence."
    ),
    "text": (
        "TEXT UNCERTAIN is text readers disagree on, often illegible decorative print. Set the "
        "text from the image with a `text` override, or drop the illegible part, with the reason."
    ),
    "spelling": (
        "SPELLING is a misspelled word a reader saw that the voted title or text has corrected. "
        "It is usually a real typo: if the image shows it, override `title` or `text` as printed."
    ),
    "description": (
        "Readers take values from the wrong place when a description doesn't match, often all in "
        "the same way, so voting can't catch it. Rewrite each flagged description where they say, "
        "checking one crop, and call `read`: it reads that kind again."
    ),
    "back": (
        "Identical backs usually mean one kind. If the mix is real, record it in `back_kinds` "
        '(`{"b02": ["kind_a", "kind_b"]}`).'
    ),
    "count": (
        "On a count mismatch, the total is the files' items plus `rules_items`. Re-check the "
        "designs involved at full size and fix only what the image shows. If the files really "
        "differ from the rules, leave it and say so in `extraction_notes`. A mismatch caused by "
        "`rules_items` is fixed there, not by overrides."
    ),
    "no_majority": (
        "NO MAJORITY includes passages only some readers transcribed: readers drop text far more "
        "often than they invent it, so check the image before accepting the shorter version. Fix "
        'rules text with `rules_fixes` (`{"find": "...", "replace": "..."}`, applied to the '
        "assembled text), with `find` long enough to match only the intended place."
    ),
    "rules_spelling": (
        "SPELLING here is a misspelled word proofreaders saw that the transcription has "
        "corrected: usually a real typo, almost always when Tesseract also reads it as printed. "
        "Open the region image and restore it with `rules_fixes` if the image shows it; never "
        "dismiss one without looking."
    ),
}


@dataclass
class CheckReport:
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    text_uncertain: list[dict[str, Any]] = field(default_factory=list)
    spelling: list[dict[str, Any]] = field(default_factory=list)
    description: list[dict[str, Any]] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)
    back_checks: list[str] = field(default_factory=list)
    count_checks: list[str] = field(default_factory=list)
    orientation: list[str] = field(default_factory=list)
    # for the summary line of the text, not saved
    design_count: int = 0
    settled: int = 0
    unanimous: int = 0
    overridden: int = 0
    back_groups: dict[str, dict[str, int]] = field(default_factory=dict)


# ---------------------------------------------------------------- building the report


def _design_flags(ws: Workspace, designs: dict[str, dict], report: CheckReport) -> None:
    """Conflicts, uncertain text and spelling flags, per design."""
    for design, v in designs.items():
        image = str(ws.rel(ws.work / "items" / v["members"][0] / "front.png"))
        if v["unsettled"]:
            report.conflicts.append(
                {
                    "design": design,
                    "image": image,
                    "unsettled": v["unsettled"],
                    "votes": v.get("votes", {}),
                    "members": v["members"],
                }
            )
        elif not v.get("text_settled", True) and not v.get("overridden"):
            report.text_uncertain.append(
                {"design": design, "image": image, "spans": v["votes"].get("text", [])}
            )
        for flag in v.get("spelling", []):
            report.spelling.append({"design": design, "image": image} | flag)


def _kind_flags(designs: dict[str, dict], report: CheckReport) -> None:
    """Kinds whose description readers say does not match the image, and kinds set by override
    against what the reads chose."""
    against: dict[str, list[str]] = defaultdict(list)
    mismatches: dict[str | None, list[str]] = defaultdict(list)
    for design, v in designs.items():
        if v.get("overridden") and v.get("read_kind") not in (None, v.get("kind")):
            against[v["kind"]].append(design)
        for kind, mismatch in v.get("mismatch", []):
            mismatches[kind].append(mismatch)

    for kind, said in sorted(mismatches.items(), key=lambda x: str(x[0])):
        noted = [m for m in said if components.noted(m)]
        if kind not in (None, "other") and len(noted) * 2 > len(said):
            report.description.append(
                {"kind": kind, "reads": len(said), "mismatch": len(noted), "examples": noted[:3]}
            )
    for kind, overridden in sorted(against.items()):
        more = " ..." if len(overridden) > 8 else ""
        report.checks.append(
            f"kind {kind} is set by override on {len(overridden)} designs whose reads mostly "
            f"chose another kind ({' '.join(overridden[:8])}{more}): readers don't recognise it "
            "from its description. Rewrite the description for the crop as readers see it and "
            "call `read` again, rather than overriding"
        )


def _item_values(
    key: str, designs: dict[str, dict], item_design: dict[str, str], cfg: ExtractionConfig
) -> dict[str, Any]:
    """The values of one item: its design's, with an override for this item key on top."""
    values = dict(designs[item_design[key]])
    if key in cfg.overrides:
        values["fields"] = dict(values.get("fields", {}))
        components.apply_override(values, cfg.overrides[key].set)
    return values


def _back_checks(
    cfg: ExtractionConfig,
    item_kinds: dict[str, Any],
    item_back: dict[str, str],
    report: CheckReport,
) -> None:
    per_back: dict[str, Counter] = defaultdict(Counter)
    for key, kind in item_kinds.items():
        if key in item_back:
            per_back[item_back[key]][kind] += 1
    report.back_groups = {b: dict(c) for b, c in per_back.items()}
    for back, counter in per_back.items():
        allowed = cfg.back_kinds.get(back)
        if allowed is not None and set(counter) - set(allowed):
            report.back_checks.append(f"back group {back} allows {allowed} but has {dict(counter)}")
        elif allowed is None and len(counter) > 1:
            report.back_checks.append(
                f"back group {back} (identical backs) holds several kinds: {dict(counter)}"
            )


def _expect_checks(expect: Expect, candidates: list[dict[str, Any]], report: CheckReport) -> None:
    def matches(c: dict[str, Any]) -> bool:
        if c["kind"] != expect.kind:
            return False
        for name, wanted in expect.where.items():
            actual = c["title"] if name == "title" else c["fields"].get(name)
            if actual != wanted:
                return False
        return True

    selected = [c for c in candidates if matches(c)]
    label = f"expect {expect.kind} {expect.where}"
    if expect.count is not None and expect.count != len(selected):
        report.count_checks.append(f"{label}: expected {expect.count} items, found {len(selected)}")
    for name, distribution in expect.distribution.items():
        got = Counter(str(c["fields"].get(name)) for c in selected)
        want = {str(k): n for k, n in distribution.items()}
        if dict(got) != want:
            report.count_checks.append(f"{label}: {name} expected {want}, found {dict(got)}")


def _count_checks(
    cfg: ExtractionConfig, candidates: list[dict[str, Any]], report: CheckReport
) -> None:
    kind_count = Counter(c["kind"] for c in candidates)
    for kind in cfg.kinds:
        if kind.count_in_rules is not None and kind.count_in_rules != kind_count[kind.id]:
            report.count_checks.append(
                f"kind {kind.id}: rules say {kind.count_in_rules}, found {kind_count[kind.id]} "
                "(files plus rules_items)"
            )
    for expect in cfg.expect:
        _expect_checks(expect, candidates, report)


def build_report(ws: Workspace, cfg: ExtractionConfig) -> CheckReport:
    groups, designs = components.build_resolved(ws, cfg)
    item_keys = [i["key"] for i in load_json(ws.work / "items.json")]
    item_design = {k: d for d, members in groups["designs"].items() for k in members}
    item_back = {k: b for b, members in groups["backs"].items() for k in members}

    report = CheckReport(orientation=orientation_report(ws, designs))
    report.design_count = len(designs)
    report.settled = sum(1 for v in designs.values() if not v["unsettled"])
    report.unanimous = sum(1 for v in designs.values() if v.get("unanimous"))
    report.overridden = sum(1 for v in designs.values() if v.get("overridden"))

    _design_flags(ws, designs, report)
    _kind_flags(designs, report)

    values = {key: _item_values(key, designs, item_design, cfg) for key in item_keys}
    _back_checks(cfg, {key: v.get("kind") for key, v in values.items()}, item_back, report)

    # What the game has by now: the files' items plus the components only the rules name.
    candidates = [
        {"kind": v.get("kind"), "title": v.get("title"), "fields": v.get("fields") or {}}
        for v in values.values()
    ]
    candidates += [
        {"kind": i.kind, "title": i.title, "fields": i.fields}
        for i in components.expand_rules_items(cfg)
    ]
    _count_checks(cfg, candidates, report)
    return report


# ---------------------------------------------------------------- the text of the report


def format_report(ws: Workspace, report: CheckReport) -> str:
    lines = [
        f"designs: {report.design_count}, settled: {report.settled}, "
        f"unanimous: {report.unanimous}, overridden: {report.overridden}"
    ]
    if report.back_groups:
        per_back = "; ".join(f"{b}: {c}" for b, c in sorted(report.back_groups.items()))
        lines.append(f"items per back group and kind: {per_back}")

    for c in report.conflicts:
        votes = json.dumps(c["votes"], ensure_ascii=False)
        lines.append(f"CONFLICT {c['design']} {c['unsettled']} votes={votes} image={c['image']}")
    if report.conflicts:
        lines.append(HELP["conflict"])

    for t in report.text_uncertain:
        lines.append(f"TEXT UNCERTAIN {t['design']} image={t['image']}")
        for span in t["spans"][:5]:
            lines.append(f"    kept: {span['kept']!r}  alternatives: {span['alternatives']!r}")
    if report.text_uncertain:
        lines.append(HELP["text"])

    for s in report.spelling:
        lines.append(
            f"SPELLING {s['design']}: a reader saw {s['printed']!r} printed; "
            f"the title/text has {s['transcribed']!r} image={s['image']}"
        )
    if report.spelling:
        lines.append(HELP["spelling"])

    for d in report.description:
        examples = " | ".join(repr(m) for m in d["examples"])
        lines.append(
            f"DESCRIPTION kind {d['kind']}: {d['mismatch']} of {d['reads']} reads say its "
            f"description doesn't match the image, e.g. {examples}"
        )
    if report.description:
        lines.append(HELP["description"])

    lines += report.orientation
    if report.orientation:
        lines.append(ORIENTATION_NEXT)

    lines += [f"CHECK {c}" for c in report.checks]
    lines += [f"CHECK {c}" for c in report.back_checks]
    if report.back_checks:
        lines.append(HELP["back"])
    lines += [f"CHECK {c}" for c in report.count_checks]
    if report.count_checks:
        lines.append(HELP["count"])

    lines.append(
        f"total cost so far: ${total_cost(ws):.4f}; details in {ws.rel(ws.work / 'check.json')}"
    )
    return "\n".join(lines)


def run_check(ws: Workspace) -> str:
    report = build_report(ws, ws.load_config())
    saved = asdict(report)
    for summary_key in ("design_count", "settled", "unanimous", "overridden", "back_groups"):
        del saved[summary_key]
    save_json(ws.work / "check.json", saved)
    return format_report(ws, report)
