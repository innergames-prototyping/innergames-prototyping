"""before_run.py: check the upload set before a run is started. Changes nothing.

    python tools/before_run.py                    # every game folder in the kit's games folder
    python tools/before_run.py lethal_dungeon     # one game (name or part of it)

Checks:
  - system/ holds exactly the 8 instruction files, byte-identical to tools/kit_hashes.json;
  - the game folder follows intake rules 2.3: no archives, no Office files, no spaces or reserved
    characters in names, no 00 names, only known 01 names, nothing of ours (RUN-END, RESEND, notes);
  - which path the run will take (extraction if 01_rules.txt is there, otherwise raw).
Prints the upload list with sizes and hashes, ready for the run log. Exit 0 = ready.
"""
import argparse
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)
SYSTEM = os.path.join(KIT, "system")
GAMES = os.path.join(KIT, "games")
USER_INPUTS = {"01_rules.txt", "01_components.json", "01_timings.json", "01_focus.json"}
OK_EXT = {".pdf", ".txt", ".md", ".csv", ".json", ".jpg", ".jpeg", ".png", ".gif", ".webp"}
ARCHIVE = {".zip", ".rar", ".7z", ".tar", ".gz", ".tgz"}
OFFICE = {".docx", ".doc", ".odt", ".pptx", ".ppt", ".xlsx", ".xls", ".ods", ".rtf", ".pages", ".key", ".numbers"}
OURS = re.compile(r"(RUN[-_]?END|RESEND|CONTINUE|AB_|instrument|ruling|answer|catalogue|notes?\b|REPORT|headline|run_manifest|summary\.json|per_game|events_D)", re.I)
BAD_CHARS = re.compile(r'[<>:"|?*\\/ ]')
MAX_BYTES = 500 * 1024 * 1024


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def check_system(problems):
    want = json.load(open(os.path.join(HERE, "kit_hashes.json"), encoding="utf-8"))["system"]
    have = sorted(n for n in os.listdir(SYSTEM) if not n.startswith("."))
    for n in sorted(set(want) - set(have)):
        problems.append(f"system/: {n} is missing")
    for n in sorted(set(have) - set(want)):
        problems.append(f"system/: {n} does not belong there (only the 8 instruction files)")
    rows = []
    for n in sorted(set(have) & set(want)):
        p = os.path.join(SYSTEM, n)
        h = sha(p)
        if h != want[n]["sha256"]:
            problems.append(f"system/: {n} differs from the kit (sha256 {h[:12]}, want {want[n]['sha256'][:12]})")
        rows.append((n, os.path.getsize(p), h[:12]))
    return rows


def check_game(folder, problems):
    names = sorted(n for n in os.listdir(folder) if not n.startswith("."))
    rows = []
    if not names:
        problems.append("the game folder is empty")
    for n in names:
        p = os.path.join(folder, n)
        ext = os.path.splitext(n)[1].lower()
        if os.path.isdir(p):
            problems.append(f"{n}/: a subfolder; put its files in the game folder itself, flat (2.3 rule 1)")
            continue
        if ext in ARCHIVE:
            problems.append(f"{n}: an archive; unpack it into the game folder and remove the archive (2.3 rule 1)")
        elif ext in OFFICE:
            problems.append(f"{n}: an Office file; convert it to PDF (2.3 rule 1)")
        elif ext not in OK_EXT:
            problems.append(f"{n}: file type {ext or '(none)'} is not on the intake list (2.3 rule 1)")
        if BAD_CHARS.search(n):
            problems.append(f"{n}: spaces or reserved characters in the name; use _ (2.3 rule 2)")
        if n.startswith("00"):
            problems.append(f"{n}: 00 names are ours; prefix the client's file with client_ (2.3 rule 2)")
        if n.startswith("01") and n not in USER_INPUTS:
            problems.append(f"{n}: unknown 01 name; allowed: {', '.join(sorted(USER_INPUTS))} (2.3 rule 2)")
        if n not in USER_INPUTS and OURS.search(n):
            problems.append(f"{n}: looks like one of our files (operator text, notes or earlier output); keep it out (2.3 rule 4)")
        if os.path.getsize(p) > MAX_BYTES:
            problems.append(f"{n}: over 500 MB (2.3 rule 3)")
        if os.path.getsize(p) == 0:
            problems.append(f"{n}: empty file")
        if n.endswith(".json"):
            try:
                json.load(open(p, encoding="utf-8"))
            except ValueError as e:
                problems.append(f"{n}: not valid JSON ({e})")
        rows.append((n, os.path.getsize(p), sha(p)[:12]))
    if "01_components.json" in names and "01_rules.txt" not in names:
        problems.append("01_components.json without 01_rules.txt: the extraction path needs both")
    for n in ("01_timings.json", "01_focus.json"):
        if n in names:
            d = json.load(open(os.path.join(folder, n), encoding="utf-8"))
            want = {"01_timings.json": "timings_v1", "01_focus.json": "focus_v1"}[n]
            if d.get("schema") != want:
                problems.append(f"{n}: schema should be '{want}' (copy it from templates/)")
    path = "extraction" if "01_rules.txt" in names else "raw"
    return rows, path, [n for n in names if n in {"01_timings.json", "01_focus.json"}]


def main(argv=None):
    for _s in (sys.stdout, sys.stderr):        # Windows code pages: never crash on a character
        try:
            _s.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("game", nargs="?", help="game folder name or part of it (default: all)")
    a = ap.parse_args(argv)
    sys_problems = []
    sys_rows = check_system(sys_problems)
    games = sorted(d for d in os.listdir(GAMES) if os.path.isdir(os.path.join(GAMES, d)))
    if a.game:
        games = [d for d in games if a.game.lower() in d.lower()] or sys.exit(f"no game folder matches '{a.game}'")
    kit = json.load(open(os.path.join(HERE, "kit_hashes.json"), encoding="utf-8")).get("kit", "?")
    print(f"Kit {kit}: {KIT}\n")
    print("system/ (upload all 8):")
    for n, b, h in sys_rows:
        print(f"  {n:34s} {b:>9,} B  {h}")
    for p in sys_problems:
        print(f"  PROBLEM  {p}")
    ready = not sys_problems
    for gname in games:
        problems = []
        rows, path, extras = check_game(os.path.join(GAMES, gname), problems)
        print(f"\ngames/{gname}/  ->  {path} path" + (f", optional inputs: {', '.join(extras)}" if extras else ", no optional inputs"))
        for n, b, h in rows:
            print(f"  {n:34s} {b:>9,} B  {h}")
        for p in problems:
            print(f"  PROBLEM  {p}")
        total = len(sys_rows) + len(rows)
        print(f"  Upload: 8 from system/ + {len(rows)} from games/{gname}/ = {total} files. "
              + ("READY" if not problems and not sys_problems else "NOT READY"))
        ready &= not problems
    print("\nNever upload anything from operator/, templates/, tools/ or tests/.")
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
