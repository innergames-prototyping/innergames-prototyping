"""One analysis session: prepares its folder, runs the kit brief and validates the output.

<folder>/00*            the kit's eight instruction files, byte-identical
<folder>/01_*           extraction results and optional designer numbers
<folder>/out/           what the session writes
<folder>/events.jsonl   one line per tool call or text block
<folder>/check.json     the result of the kit's validator
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query,
)

from ..claude import ISOLATED_ENV, MAX_MESSAGE_BYTES

KIT = Path(__file__).resolve().parents[3] / "analysis-pipeline"
PROMPT = "Read 00a_START_HERE.md and follow it."
ENVIRONMENT = (
    "You run in Claude Code, not in a chat. The files the brief calls attached are the files in "
    "the working directory: the eight 00 files, any 01 files (01_rules.txt, 01_components.json, "
    "01_timings.json, 01_focus.json) and any game material. Read them from there. Write out/ in "
    "the working directory. There is no delivery tool: a file is delivered once it is in out/. "
    "Do the final check of the output contract's §3.1, skip §3.2 and §3.3, and in the RUNLOG "
    "report files_failed=none unless a file is missing and files_written as §3.4 says. python3 "
    "is on the PATH, with the standard library only."
)
UPSTREAM = {"rules.md": "01_rules.txt", "components.json": "01_components.json"}
SCHEMAS = {"01_timings.json": "timings_v1", "01_focus.json": "focus_v1"}

EventSink = Callable[[str, str], None]


class AnalysisError(Exception):
    """The analysis cannot start or its session failed."""


@dataclass(frozen=True)
class AnalysisResult:
    session_id: str
    reply: str
    cost_usd: float
    is_error: bool
    runlog: str | None
    validator_exit: int | None


def verify_kit(kit: Path = KIT) -> list[Path]:
    """The instruction files, after checking them against the kit's hash list."""
    expected = json.loads((kit / "tools" / "kit_hashes.json").read_text())["system"]
    files = sorted((kit / "system").glob("00*"))
    if {f.name for f in files} != set(expected):
        raise AnalysisError("the kit's system folder does not match kit_hashes.json")
    for file in files:
        if hashlib.sha256(file.read_bytes()).hexdigest() != expected[file.name]["sha256"]:
            raise AnalysisError(f"{file.name} does not match its hash in kit_hashes.json")
    return files


def check_designer_numbers(timings: dict[str, Any] | None, focus: dict[str, Any] | None) -> None:
    for name, data in {"01_timings.json": timings, "01_focus.json": focus}.items():
        if data is not None and data.get("schema") != SCHEMAS[name]:
            raise AnalysisError(f"{name} needs schema {SCHEMAS[name]}")


def prepare(
    folder: Path,
    rules: Path,
    components: Path,
    timings: dict[str, Any] | None = None,
    focus: dict[str, Any] | None = None,
) -> None:
    """Fills `folder` with the kit files, the two extraction results and the designer numbers."""
    check_designer_numbers(timings, focus)
    designer = {"01_timings.json": timings, "01_focus.json": focus}
    kit_files = verify_kit()
    folder.mkdir(parents=True, exist_ok=False)
    for file in kit_files:
        shutil.copy(file, folder)
    shutil.copy(rules, folder / "01_rules.txt")
    shutil.copy(components, folder / "01_components.json")
    for name, data in designer.items():
        if data is not None:
            (folder / name).write_text(json.dumps(data, ensure_ascii=False, indent=1))


async def analyse_results(
    results: Path,
    folder: Path,
    model: str,
    timings: dict[str, Any] | None,
    focus: dict[str, Any] | None,
    on_event: EventSink,
) -> AnalysisResult:
    """Runs the analysis on an extraction's `results/` folder."""
    missing = [name for name in UPSTREAM if not (results / name).is_file()]
    if missing:
        raise AnalysisError(f"the extraction has no {', '.join(missing)}")
    prepare(folder, results / "rules.md", results / "components.json", timings, focus)
    return await run_session(folder, model, on_event)


def session_options(folder: Path, model: str, resume: str | None = None) -> ClaudeAgentOptions:
    """Isolated like every app session, but with the file and shell tools the kit needs."""
    return ClaudeAgentOptions(
        system_prompt={"type": "preset", "preset": "claude_code", "append": ENVIRONMENT},
        model=model,
        effort="high",
        cwd=folder,
        setting_sources=[],
        strict_mcp_config=True,
        tools=["Bash", "Read", "Write", "Edit"],
        allowed_tools=["Bash", "Read", "Write", "Edit"],
        permission_mode="acceptEdits",
        env={**ISOLATED_ENV, "PYTHONDONTWRITEBYTECODE": "1"},
        extra_args={"safe-mode": None, "no-chrome": None, "disable-slash-commands": None},
        max_buffer_size=MAX_MESSAGE_BYTES,
        resume=resume,
    )


async def run_session(
    folder: Path, model: str, on_event: EventSink | None = None
) -> AnalysisResult:
    """Runs the brief to its end in `folder`, then runs the kit's validator on `out/`."""
    log = folder / "events.jsonl"

    def emit(kind: str, text: str) -> None:
        line = {"at": datetime.now(UTC).isoformat(), "kind": kind, "text": text}
        with log.open("a") as file:
            file.write(json.dumps(line, ensure_ascii=False) + "\n")
        if on_event:
            on_event(kind, text)

    reply, result = "", None
    async for message in query(prompt=PROMPT, options=session_options(folder, model)):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ToolUseBlock):
                    emit("tool", f"{block.name} {json.dumps(block.input)[:300]}")
                elif isinstance(block, TextBlock) and block.text.strip():
                    reply = block.text.strip()
                    emit("text", reply)
        elif isinstance(message, ResultMessage):
            result = message
    if result is None:
        raise AnalysisError("the session ended without a result")
    final = result.result or reply
    runlog = find_runlog(final)
    exit_code = validate(folder, runlog) if (folder / "out").is_dir() else None
    return AnalysisResult(
        session_id=result.session_id,
        reply=final,
        cost_usd=result.total_cost_usd or 0.0,
        is_error=result.is_error,
        runlog=runlog,
        validator_exit=exit_code,
    )


def find_runlog(reply: str) -> str | None:
    lines = [line.strip() for line in reply.splitlines() if line.strip().startswith("RUNLOG:")]
    return lines[-1] if lines else None


def validate(folder: Path, runlog: str | None) -> int:
    """Exit code of the kit's validator: 0 passed, 1 failed, 2 could not finish."""
    command = [
        sys.executable,
        str(KIT / "tools" / "check_outputs.py"),
        str(folder / "out"),
        "--json",
        str(folder / "check.json"),
    ]
    if runlog:
        command += ["--runlog", runlog]
    env = os.environ | {"PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(command, env=env, capture_output=True, check=False).returncode
