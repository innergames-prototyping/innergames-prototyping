"""What the model calls of a run cost, summed from the read files on disk."""

from pathlib import Path

from .workspace import Workspace, load_json


def _costs(paths: list[Path]) -> list[float]:
    return [load_json(p).get("cost_usd", 0) for p in sorted(paths)]


def _component_reads(ws: Workspace) -> list[Path]:
    return list((ws.work / "reads").glob("*/*.json"))


def _orientation_reads(ws: Workspace) -> list[Path]:
    return list((ws.work / "orient").glob("*/*.json"))


def _rules_reads(ws: Workspace, pattern: str = "*.json") -> list[Path]:
    return list((ws.work / "rules" / "reads").glob(pattern))


def _proposal_cost(ws: Workspace) -> float:
    """The `propose_model` step stores its cost next to the model it proposed."""
    proposal = load_json(ws.work / "proposal.json", {})
    return proposal.get("cost_usd", 0)


def total_cost(ws: Workspace) -> float:
    paths = _component_reads(ws) + _orientation_reads(ws) + _rules_reads(ws)
    return sum(_costs(paths)) + _proposal_cost(ws)


def cost_report(ws: Workspace) -> str:
    def line(label: str, paths: list[Path]) -> str:
        return f"{label}: {len(paths)} calls, ${sum(_costs(paths)):.4f}"

    return "\n".join(
        [
            line("orientation reads", _orientation_reads(ws)),
            line("component reads", _component_reads(ws)),
            line("rules reads", _rules_reads(ws, "*.read*.json")),
            line("proofreading reads", _rules_reads(ws, "*.proof*.json")),
            f"model proposal: ${_proposal_cost(ws):.4f}",
            f"total: ${total_cost(ws):.4f}",
        ]
    )
