"""Runs the extract-game-components skill on a set of PDFs with a Haiku Claude Code session.

Port of the run.sh used for the extraction tests: no user customisations, no MCP servers, only the
tools the extraction needs, and the skill as the whole system prompt.
"""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKILL = REPO / ".claude" / "skills" / "extract-game-components"
# The job folder links the skill at this relative path, as the test runs had it: with the absolute
# path the model starts aliasing it, and the aliased command no longer matches the allowed tool
# rule.
SKILL_LINK = ".claude/skills/extract-game-components"
JOBS = REPO / "backend" / "jobs"
RESULT_FILES = ("rules.txt", "components.json")


@dataclass
class Job:
    id: str
    dir: Path
    pdfs: list[str]
    started: float = field(default_factory=time.time)
    finished: float | None = None
    state: str = "running"
    activity: str = "Starting"
    result: str | None = None
    cost_usd: float | None = None
    task: asyncio.Task | None = None

    def results(self) -> list[str]:
        return [name for name in RESULT_FILES if (self.dir / "results" / name).is_file()]


jobs: dict[str, Job] = {}


def system_prompt(workdir: Path) -> str:
    lines = (SKILL / "SKILL.md").read_text().splitlines()
    body_start = [i for i, line in enumerate(lines) if line == "---"][1] + 1
    return (
        "You extract a tabletop game's rules and components from the PDF files in the working "
        f"directory ({workdir}), following the instructions below. Run the script as "
        f"{SKILL_LINK}/extract.py <command> from the working directory; components.schema.json is "
        f"in {SKILL_LINK}. The machine is NixOS: run other tools through nix-shell -p <package> "
        '--run "<command>". Don\'t delete files.\n\n' + "\n".join(lines[body_start:])
    )


def command(workdir: Path) -> list[str]:
    return [
        "claude",
        "-p",
        "Extract the PDFs in this folder.",
        "--safe-mode",
        "--strict-mcp-config",
        "--no-chrome",
        "--model",
        "haiku",
        "--tools",
        "Bash,Read,Write,Edit",
        "--permission-mode",
        "acceptEdits",
        "--allowedTools",
        f"Bash({SKILL_LINK}/extract.py *)",
        "Bash(nix-shell -p *)",
        "--system-prompt",
        system_prompt(workdir),
        "--output-format",
        "stream-json",
        "--verbose",
    ]


def start(pdfs: dict[str, bytes]) -> Job:
    job_id = uuid.uuid4().hex[:12]
    workdir = JOBS / job_id
    workdir.mkdir(parents=True)
    for name, data in pdfs.items():
        (workdir / name).write_bytes(data)
    (workdir / SKILL_LINK).parent.mkdir(parents=True)
    (workdir / SKILL_LINK).symlink_to(SKILL)
    job = Job(job_id, workdir, sorted(pdfs))
    job.task = asyncio.create_task(run(job))
    jobs[job_id] = job
    return job


def describe(tool: dict) -> str | None:
    args = tool.get("input", {})
    if tool.get("name") == "Bash":
        return args.get("description") or args.get("command")
    if "file_path" in args:
        return f"{tool['name']} {Path(args['file_path']).name}"
    return None


async def run(job: Job) -> None:
    try:
        returncode = await run_claude(job)
    except (OSError, ValueError) as e:
        job.state, job.activity = "failed", f"Failed: {e!r}"
    else:
        ok = returncode == 0 and len(job.results()) == len(RESULT_FILES)
        job.state = "done" if ok else "failed"
        job.activity = "Finished" if ok else f"Failed (exit code {returncode})"
    job.finished = time.time()


async def run_claude(job: Job) -> int:
    with (
        (job.dir / "claude.jsonl").open("wb") as log,
        (job.dir / "claude.err").open("wb") as err,
    ):
        # Read results come back as base64 images, so a single line of output can be megabytes long.
        proc = await asyncio.create_subprocess_exec(
            *command(job.dir),
            cwd=job.dir,
            limit=2**26,
            stdout=asyncio.subprocess.PIPE,
            stderr=err,
        )
        assert proc.stdout is not None
        async for line in proc.stdout:
            log.write(line)
            event = json.loads(line)
            if event.get("type") == "assistant":
                for block in event["message"]["content"]:
                    if block.get("type") == "tool_use" and (text := describe(block)):
                        job.activity = text
            elif event.get("type") == "result":
                job.result = event.get("result")
                job.cost_usd = event.get("total_cost_usd")
        return await proc.wait()
