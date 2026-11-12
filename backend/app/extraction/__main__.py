"""Command line to test the extraction without the server.

uv run python -m app.extraction run <files...> [--run-dir DIR]
uv run python -m app.extraction tool <name> --run-dir DIR ['<json args>']
uv run python -m app.extraction propose --run-dir DIR
"""

import argparse
import asyncio
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

from ..settings import Settings, load_settings
from .agent import run_agent
from .proposal import propose_model
from .queue import ReadLimits
from .reader import ClaudeReader
from .tools import TOOL_NAMES, call_tool
from .workspace import ExtractionError, Workspace


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        asyncio.run(args.handler(args, load_settings()))
    except ExtractionError as e:
        raise SystemExit(f"error: {e}") from e


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.extraction", description=__doc__)
    commands = parser.add_subparsers(required=True)

    run = commands.add_parser("run", help="the whole flow: agent session, then propose_model")
    run.add_argument("files", nargs="+", type=Path)
    run.add_argument("--run-dir", type=Path, help="default: a new folder under the runs folder")
    run.set_defaults(handler=run_all)

    tool = commands.add_parser("tool", help="run one tool by hand and print its output")
    tool.add_argument("name", choices=TOOL_NAMES)
    tool.add_argument("--run-dir", type=Path, required=True)
    tool.add_argument("args", nargs="?", default="{}", help="JSON object with the arguments")
    tool.set_defaults(handler=run_tool)

    propose = commands.add_parser("propose", help="propose the game model from the results")
    propose.add_argument("--run-dir", type=Path, required=True)
    propose.set_defaults(handler=run_propose)
    return parser


def _workspace(run_dir: Path) -> Workspace:
    return Workspace(run_dir).create()


def _reader(settings: Settings, ws: Workspace) -> ClaudeReader:
    return ClaudeReader(settings.reader_model, cwd=ws.root)


async def run_all(args: argparse.Namespace, settings: Settings) -> None:
    run_dir = args.run_dir or settings.runs_dir / f"{datetime.now(UTC):%Y%m%d-%H%M%S}"
    ws = _workspace(run_dir)
    for file in args.files:
        shutil.copy(file, ws.input / file.name)
    print(f"run folder: {ws.root}")

    reader = _reader(settings, ws)
    limits = ReadLimits(parallel=settings.parallel_reads)
    result = await run_agent(ws, settings, reader, limits, _print_event)
    print(f"\n{result.reply}\n\nagent cost: ${result.cost_usd:.4f}")
    if result.is_error:
        raise SystemExit("the agent session failed")
    if (ws.results / "components.json").exists():
        await propose_and_print(ws, reader)


def _print_event(kind: str, text: str) -> None:
    print(f"[{kind}] {text}", flush=True)


async def run_tool(args: argparse.Namespace, settings: Settings) -> None:
    ws = _workspace(args.run_dir)
    tool_args = json.loads(args.args)
    limits = ReadLimits(parallel=settings.parallel_reads)
    print(await call_tool(ws, _reader(settings, ws), limits, args.name, tool_args))


async def run_propose(args: argparse.Namespace, settings: Settings) -> None:
    ws = _workspace(args.run_dir)
    await propose_and_print(ws, _reader(settings, ws))


async def propose_and_print(ws: Workspace, reader: ClaudeReader) -> None:
    model = await propose_model(ws, reader)
    print(
        f"game model saved: {len(model.action_kinds)} action kinds, "
        f"{len(model.variables)} variables ({ws.rel(ws.results / 'game_model_v1.json')})"
    )


if __name__ == "__main__":
    main()
