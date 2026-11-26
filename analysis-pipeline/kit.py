"""kit.py: one launcher for the kit's tools, on Windows, macOS and Linux.

Run it from anywhere; it finds the kit folder, the runs folder and the newest run itself.

    python3 kit.py before              check the upload set            (tools/before_run.py)
    python3 kit.py after               check the newest finished run   (tools/after_run.py)
    python3 kit.py recompute           play time with measured timings (tools/playtime_recompute.py)
    python3 kit.py import              copy a run into SQLite          (tools/import_sqlite.py)
    python3 kit.py                     menu: pick one of the above

Anything after the command goes to the tool unchanged, for example
    python3 kit.py after 14            Run14_...
    python3 kit.py before lethal       one game folder
    python3 kit.py import 12 --force

On Windows use `py kit.py ...` or the .bat files; on macOS/Linux `python3 kit.py ...` or the
.sh files (`sh AFTER_RUN.sh`). Standard library only, Python 3.8+.
"""
import os
import runpy
import sys

KIT = os.path.dirname(os.path.abspath(__file__))
TOOLS = {"before": "before_run.py", "after": "after_run.py",
         "recompute": "playtime_recompute.py", "import": "import_sqlite.py"}
ALIASES = {"before_run": "before", "after_run": "after", "playtime": "recompute",
           "playtime_recompute": "recompute", "import_sqlite": "import", "sqlite": "import"}
BLURB = {"before": "check the upload set before a run", "after": "check a finished run (newest by default)",
         "recompute": "play time with measured timings", "import": "copy a run into SQLite"}


def menu():
    print("Kit tools:")
    keys = list(TOOLS)
    for i, k in enumerate(keys, 1):
        print(f"  {i}. {k:10s} {BLURB[k]}")
    try:
        pick = input("Number (Enter to quit): ").strip()
    except EOFError:
        return None
    if pick.isdigit() and 1 <= int(pick) <= len(keys):
        return keys[int(pick) - 1]
    return None


def main():
    if sys.version_info < (3, 8):
        sys.exit(f"Python 3.8 or newer is needed; this is {sys.version.split()[0]}.")
    args = sys.argv[1:]
    if args and args[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd = ALIASES.get(args[0], args[0]) if args else menu()
    if cmd is None:
        return 0
    if cmd not in TOOLS:
        print(f"Unknown command '{cmd}'. Commands: {', '.join(TOOLS)}.\n")
        print(__doc__)
        return 2
    script = os.path.join(KIT, "tools", TOOLS[cmd])
    sys.argv = [script] + args[1:]
    sys.path.insert(0, os.path.join(KIT, "tools"))
    try:
        runpy.run_path(script, run_name="__main__")
    except SystemExit as e:            # the tools exit with their own code or message; pass it on
        if isinstance(e.code, str):
            print(e.code, file=sys.stderr)
            return 1
        return e.code if isinstance(e.code, int) else 0
    return 0


if __name__ == "__main__":
    code = main()
    if os.environ.get("KIT_PAUSE"):    # set by the double-click launchers so the window stays open
        try:
            input("\nPress Enter to close.")
        except EOFError:
            pass
    sys.exit(code)
