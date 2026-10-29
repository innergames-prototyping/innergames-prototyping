"""Runs the whole pipeline on a folder of PDFs: the extraction, then the v5 simulation from the
rules.txt and components.json it produces, then check_outputs.py on the simulation's output.

Usage, from backend/ with the virtual environment active: python -m app.pipeline <PDF folder>
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import extraction

ANALYSIS = extraction.REPO / "analysis-pipeline"
UPSTREAM = {"rules.txt": "01_rules.txt", "components.json": "01_components.json"}
# The v5 brief is written for the Claude app, where the files are attached and sent back with a
# delivery tool.
ENVIRONMENT = (
    "You run in Claude Code, not in a chat. The files the brief calls attached are the eight 00 "
    "files and the two 01 files in the working directory; write out/ there too. There is no "
    "delivery tool: a file is delivered once it is in out/. Do the final check of the output "
    "contract's §3.1, skip the sends of §3.2 to §3.4, and report files_failed=none unless a file "
    "is missing. python3 is on the PATH, with the standard library only."
)


def simulation_command() -> list[str]:
    return [
        "claude",
        "-p",
        "Read 00a_START_HERE.md and follow it.",
        "--safe-mode",
        "--strict-mcp-config",
        "--no-chrome",
        "--disable-slash-commands",
        "--model",
        "claude-opus-5-5",
        "--effort",
        "high",
        "--tools",
        "Bash,Read,Write,Edit",
        "--permission-mode",
        "acceptEdits",
        "--allowedTools",
        "Bash",
        "--append-system-prompt",
        ENVIRONMENT,
        "--output-format",
        "stream-json",
        "--verbose",
    ]


def run_claude(step: str, command: list[str], workdir: Path, env: dict | None = None) -> dict:
    start = time.monotonic()
    with (
        (workdir / "claude.jsonl").open("wb") as log,
        (workdir / "claude.err").open("wb") as err,
    ):
        subprocess.run(command, cwd=workdir, env=env, stdout=log, stderr=err, check=True)
    lines = (workdir / "claude.jsonl").read_text().splitlines()
    result = next(e for e in map(json.loads, reversed(lines)) if e.get("type") == "result")
    # extract.py starts its own reader sessions and records their cost under work/
    reads = workdir.glob("work/**/reads/**/*.json")
    cost = result["total_cost_usd"] + sum(json.loads(r.read_text())["cost_usd"] for r in reads)
    minutes = (time.monotonic() - start) / 60
    print(f"{step}: {minutes:.0f} min, ${cost:.2f}", flush=True)
    return result


def main(pdf_folder: Path) -> int:
    pdfs = {p.name: p.read_bytes() for p in sorted(pdf_folder.glob("*.pdf"))}
    job = extraction.prepare(pdfs)
    print(f"job folder: {job}", flush=True)

    run_claude("extraction", extraction.command(job), job)
    missing = [name for name in UPSTREAM if not (job / "results" / name).is_file()]
    if missing:
        print(f"extraction wrote no {', '.join(missing)}")
        return 1

    simulation = job / "simulation"
    simulation.mkdir()
    for f in sorted((ANALYSIS / "system").glob("00*")):
        shutil.copy(f, simulation)
    for name, upstream in UPSTREAM.items():
        shutil.copy(job / "results" / name, simulation / upstream)
    # An engine imported from out/ leaves a __pycache__ folder there, which the contract forbids,
    # and the session isn't allowed to delete it.
    env = os.environ | {"PYTHONDONTWRITEBYTECODE": "1"}
    result = run_claude("simulation", simulation_command(), simulation, env)

    runlog = [line for line in result.get("result", "").splitlines() if line.startswith("RUNLOG:")]
    check = [sys.executable, ANALYSIS / "operator" / "check_outputs.py", simulation / "out"]
    check += ["--json", simulation / "check.json"]
    if runlog:
        check += ["--runlog", runlog[-1]]
    return subprocess.run(check, check=False).returncode


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
