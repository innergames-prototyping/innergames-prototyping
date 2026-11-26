"""Runs one analysis from the command line.

uv run python -m app.analysis FOLDER --rules 01_rules.txt --components 01_components.json
"""

import argparse
import asyncio
import json
from pathlib import Path

from .session import prepare, run_session


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    parser.add_argument("--rules", type=Path, required=True)
    parser.add_argument("--components", type=Path, required=True)
    parser.add_argument("--timings", type=Path)
    parser.add_argument("--focus", type=Path)
    parser.add_argument("--model", default="claude-opus-5-5")
    args = parser.parse_args()
    timings = json.loads(args.timings.read_text()) if args.timings else None
    focus = json.loads(args.focus.read_text()) if args.focus else None
    prepare(args.folder, args.rules, args.components, timings, focus)
    result = asyncio.run(
        run_session(args.folder.resolve(), args.model, lambda k, t: print(k, t[:160], flush=True))
    )
    print(result.runlog, f"cost_usd={result.cost_usd:.2f}", f"validator={result.validator_exit}")
    return 0 if result.validator_exit == 0 and not result.is_error else 1


if __name__ == "__main__":
    raise SystemExit(main())
