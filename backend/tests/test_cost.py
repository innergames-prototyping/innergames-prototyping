from app.extraction.cost import cost_report, total_cost
from app.extraction.workspace import Workspace, save_json


def write_costs(ws: Workspace) -> None:
    save_json(ws.work / "reads" / "d001" / "00.json", {"cost_usd": 0.01})
    save_json(ws.work / "reads" / "d001" / "01.json", {"cost_usd": 0.02})
    save_json(ws.work / "orient" / "d001" / "00.json", {"cost_usd": 0.04})
    save_json(ws.work / "rules" / "reads" / "aa.read1.json", {"cost_usd": 0.08})
    save_json(ws.work / "rules" / "reads" / "aa.proof1.json", {"cost_usd": 0.16})
    save_json(ws.work / "proposal.json", {"cost_usd": 0.32})


def test_total_cost_sums_every_kind_of_file(ws: Workspace):
    write_costs(ws)
    assert abs(total_cost(ws) - 0.63) < 1e-9


def test_total_cost_of_an_empty_run_is_zero(ws: Workspace):
    assert total_cost(ws) == 0


def test_cost_report_has_a_line_per_kind(ws: Workspace):
    write_costs(ws)
    lines = cost_report(ws).splitlines()
    assert lines == [
        "orientation reads: 1 calls, $0.0400",
        "component reads: 2 calls, $0.0300",
        "rules reads: 1 calls, $0.0800",
        "proofreading reads: 1 calls, $0.1600",
        "model proposal: $0.3200",
        "total: $0.6300",
    ]
