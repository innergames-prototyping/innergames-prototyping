"""The `read` step: reads every design and every rules region, then checks the result."""

from .check import run_check
from .components import (
    build_resolved,
    design_reads,
    design_targets,
    mismatched_kinds,
    read_index,
)
from .orient import ORIENTATION_NEXT, orientation_report
from .queue import ReadLimits, ReadTarget, run_reads
from .reader import Reader
from .rules import region_targets, rules_report
from .workspace import Workspace, load_json


def _stopped_early(ws: Workspace, cfg) -> list[str]:
    """Kinds whose reading stopped because most reads say the description does not fit."""
    groups = load_json(ws.work / "groups.json")
    index = read_index(ws, cfg)
    reads = {d: design_reads(index, members) for d, members in groups["designs"].items()}
    stopped = mismatched_kinds(reads)
    if not stopped:
        return []
    return [
        f"Reading stopped early for {', '.join(sorted(stopped))}: most of their reads say the "
        "description doesn't match the image (see DESCRIPTION below)."
    ]


async def read_all(
    ws: Workspace, reader: Reader, limits: ReadLimits, designs: list[str] | None = None
) -> str:
    """Reads the designs (only `designs`, when given) and, unless that filter is set, the rules
    regions, in one queue. Ends with the rules report and the check, or, when designs are read
    sideways, with what to turn."""
    cfg = ws.load_config()
    targets: list[ReadTarget] = list(design_targets(ws, cfg, reader, limits, designs))
    read_rules_too = bool(cfg.rules_regions) and not designs
    if read_rules_too:
        targets += region_targets(ws, cfg, reader, limits)

    lines = [f"reading with {limits.parallel} parallel readers"]
    await run_reads(targets, limits.parallel)
    spent = sum(t.cost_usd for t in targets)  # type: ignore[attr-defined]
    lines.append(f"spent ${spent:.4f} on reads this run")
    lines += _stopped_early(ws, cfg)
    if read_rules_too:
        lines.append(rules_report(ws, cfg))

    sideways = orientation_report(ws, build_resolved(ws, cfg)[1])
    if sideways:
        return "\n".join([*lines, *sideways, ORIENTATION_NEXT])
    return "\n".join([*lines, run_check(ws)])
