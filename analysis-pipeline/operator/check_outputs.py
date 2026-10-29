#!/usr/bin/env python3
"""check_outputs.py: check one run's output folder against output contract v2.2 (00b_output_contract.md).

Project Pipeline / InnerGames, 2026-10-24; v1.3 2026-10-26 (brief v5). Standard library only (Python 3.8+). Read-only:
it never changes, moves or creates anything in the folder it checks.

    py check_outputs.py "E:\\...\\runs\\Run11_Single\\out"
    py check_outputs.py FOLDER --runlog "RUNLOG: phases=... games_simulated=... files_written=[...]"
    py check_outputs.py FOLDER --json E:\\reports\\Run11_check.json
    py check_outputs.py FOLDER --skip-events          (faster: skips the event-log checks)

Exit code: 0 = no failures (warnings allowed), 1 = at least one failure, 2 = could not run.
The full explanation is in check_outputs_explained.md.
"""
import argparse
import collections
import hashlib
import json
import math
import os
import re
import statistics
import sys
import zipfile

VERSION = "1.3 (contract v2.2, brief v5)"

# ---------------------------------------------------------------- contract constants
FIXED_FILES = [
    "REPORT.md", "headline.json", "summary.json", "run_manifest.json",
    "D01_rules_dossier.md", "D01_board_layout.json", "D02_run.py",
    "D03_playtime_model.md", "D04_single_vs_batch.md", "D05_playtime.md",
    "D06_game_statistics.md", "D07_self_audit.md", "D08_exploits_and_rulebook_audit.md",
    "D09_limitations.md", "D10_designer_questions.md",
    "per_game_D04.jsonl.zip", "per_game_D05.jsonl.zip", "per_game_D07.jsonl.zip",
    "per_game_D08.jsonl.zip", "per_game_other.jsonl.zip",
    "events_D04.jsonl.zip", "events_D05.jsonl.zip", "events_D07.jsonl.zip",
    "events_D08.jsonl.zip",
]
ENGINE_FILE_RE = re.compile(r"^D02_engine_v([1-9][0-9]*)\.py$")
MARKDOWN = [f for f in FIXED_FILES if f.endswith(".md")]
PER_GAME_FILES = {  # file -> purposes allowed inside it
    "per_game_D04.jsonl.zip": {"D4_logged", "D4_batch"},
    "per_game_D05.jsonl.zip": {"D5"},
    "per_game_D07.jsonl.zip": {"D7_rerun"},
    "per_game_D08.jsonl.zip": {"D8_baseline", "D8_arm"},
    "per_game_other.jsonl.zip": {"test", "debug"},
}
EVENT_FILES = {
    "events_D04.jsonl.zip": {"D4_logged", "D4_batch"},
    "events_D05.jsonl.zip": {"D5"},
    "events_D07.jsonl.zip": {"D7_rerun"},
    "events_D08.jsonl.zip": {"D8_baseline", "D8_arm"},
}
ORDER = (["REPORT.md", "headline.json", "summary.json", "run_manifest.json",
          "D01_rules_dossier.md", "D01_board_layout.json"]
         + ["<engines>", "D02_run.py"] + FIXED_FILES[7:])
PURPOSES = {"D4_logged", "D4_batch", "D5", "D7_rerun", "D8_baseline", "D8_arm", "test", "debug"}
ARM_KINDS = {"strategy", "reading"}
ARM_ID_RE = re.compile(r"^(B0|S[1-9][0-9]*|R-I[1-9][0-9]*[a-z]?)$")
ENGINE_RE = re.compile(r"^v(0|[1-9][0-9]*)$")
NEW_OR_RERUN = {"new", "deterministic_rerun"}
END_CONDITIONS = {"round_limit", "deck_exhausted", "goal_reached", "all_players_out",
                  "elimination", "safety_cap", "other"}
LEDGER_KEYS = ["purpose", "arm_id", "arm_kind", "engine_version", "player_count", "seed_from",
               "seed_to", "games", "new_or_rerun", "per_game_file", "events_file",
               "logged_games", "note"]
VOCAB_CATEGORIES = {"roles", "abilities", "resources", "sources", "causes", "decks", "cards",
                    "zones", "entity_classes", "npcs", "hazards", "goals", "phases",
                    "action_types", "event_types", "readings", "strategies"}
SNAKE_RE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")
# contract §4.2 rule 5: ids keep their case in these two categories
ID_KEYS = {"readings": re.compile(r"^(I[1-9][0-9]*|R-I[1-9][0-9]*[a-z]?)$"),
           "strategies": re.compile(r"^S[1-9][0-9]*$")}
UPSTREAM_FILES = ["01_components.json", "01_rules.txt"]
ARCHIVE_EXT = (".tar", ".tar.gz", ".tgz", ".gz", ".xz", ".7z", ".rar", ".bz2", ".zst")
BROWSER_DUP_RE = re.compile(r"^(?P<stem>.+?) ?\((?P<n>\d+)\)(?P<ext>(\.[A-Za-z0-9]+)+)$")
HEADLINE_KEYS = ["schema", "game", "rulebook_file", "player_counts", "targets", "headline_clock",
                 "engine_version_final", "games_executed", "duration_table", "playtime", "outcome",
                 "d4_single_game", "d7_audit", "interpretations", "d8_arms", "designer_questions",
                 "untested"]
EXPECTED = {"D4_logged": 1, "D4_batch": 1000, "D5": 1000, "D7_rerun": 1000, "D8_baseline": 400,
            "D8_arm": 400}
EVENTS_D08_PER_ARM = 100
TOL_MIN, TOL_SHARE, TOL_POINTS = 0.011, 0.0025, 0.011


# ---------------------------------------------------------------- reporting
class Report:
    def __init__(self):
        self.items = []  # (section, id, level, message, fix)

    def add(self, section, cid, level, msg, fix=None):
        self.items.append((section, cid, level, msg, fix))

    def ok(self, section, cid, msg):
        self.add(section, cid, "PASS", msg)

    def fail(self, section, cid, msg, fix=None):
        self.add(section, cid, "FAIL", msg, fix)

    def warn(self, section, cid, msg, fix=None):
        self.add(section, cid, "WARN", msg, fix)

    def skip(self, section, cid, msg):
        self.add(section, cid, "SKIP", msg)

    def counts(self):
        return collections.Counter(i[2] for i in self.items)


def strict_json_load(text):
    def bad_constant(name):
        raise ValueError(f"non-standard JSON constant {name}")
    return json.loads(text, parse_constant=bad_constant)


def percentile(xs, p):
    """Linear interpolation between order statistics (numpy's default)."""
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * p
    lo = math.floor(k)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def close(a, b, tol):
    if a is None or b is None:
        return a is None and b is None
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


def dig(obj, *path):
    for p in path:
        if isinstance(obj, dict):
            obj = obj.get(p)
        elif isinstance(obj, list) and isinstance(p, int) and -len(obj) <= p < len(obj):
            obj = obj[p]
        else:
            return None
    return obj


# ---------------------------------------------------------------- 1. files
def check_files(folder, R):
    S = "1 Files"
    entries = sorted(os.listdir(folder))
    subdirs = [e for e in entries if os.path.isdir(os.path.join(folder, e))]
    files = [e for e in entries if os.path.isfile(os.path.join(folder, e))]
    if subdirs:
        R.fail(S, "F1", f"subfolders found: {subdirs}",
               "The contract wants one flat folder. Move the files up and delete the subfolders.")
    else:
        R.ok(S, "F1", "folder is flat (no subfolders)")

    present = set(files)
    missing = [f for f in FIXED_FILES if f not in present]
    engines = sorted((int(m.group(1)), f) for f in files if (m := ENGINE_FILE_RE.match(f)))
    if missing:
        R.fail(S, "F2", f"{len(missing)} required file(s) missing: {missing}",
               "Check the run's file cards for these names; a missing file means the run didn't deliver it.")
    else:
        R.ok(S, "F2", f"all {len(FIXED_FILES)} fixed-name files present")
    if engines:
        R.ok(S, "F2e", f"engine files present: {[f for _, f in engines]}")
    else:
        R.fail(S, "F2e", "no D02_engine_v<n>.py file found",
               "At least D02_engine_v1.py is required.")

    known = set(FIXED_FILES) | {f for _, f in engines}
    extras = [f for f in files if f not in known]
    for f in extras:
        hint = "Not part of the contract. Remove it from the folder, or report it as a deviation."
        m = BROWSER_DUP_RE.match(f)
        low = {k.lower(): k for k in known | set(FIXED_FILES)}
        if m and (m.group("stem") + m.group("ext")) in known | set(FIXED_FILES):
            hint = (f"Looks like a browser download copy of '{m.group('stem') + m.group('ext')}'. "
                    "Rename it (delete the ' (n)' part) if the original is missing; otherwise delete the copy.")
        elif f.lower() in low:
            hint = f"Wrong upper/lower case: should be '{low[f.lower()]}'."
        elif f.lower().endswith(".zip"):
            hint = "Unexpected zip. Only the nine .jsonl.zip data files are allowed; bundles are not."
        elif f.lower().endswith(ARCHIVE_EXT):
            hint = "Archive type not allowed by the contract (only single-file .jsonl.zip)."
        R.fail(S, "F3", f"extra file: '{f}'", hint)
    if not extras:
        R.ok(S, "F3", "no extra files")
    return files, engines


# ---------------------------------------------------------------- 2. JSON / text files
def load_json_file(folder, name, R, S, cid):
    path = os.path.join(folder, name)
    if not os.path.isfile(path):
        R.skip(S, cid, f"{name}: missing, not parsed")
        return None, False
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
        text = raw.decode("utf-8")
        data = strict_json_load(text)
    except UnicodeDecodeError as e:
        R.fail(S, cid, f"{name}: not UTF-8 ({e})")
        return None, False
    except ValueError as e:
        R.fail(S, cid, f"{name}: not valid JSON ({e})",
               "NaN and Infinity are not JSON; the contract requires null.")
        return None, False
    R.ok(S, cid, f"{name}: valid strict JSON")
    return data, True


def check_text_files(folder, files, R):
    S = "2 Text files"
    nread = 0
    for name in MARKDOWN + ["D02_run.py"] + [f for f in files if ENGINE_FILE_RE.match(f)]:
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            continue
        nread += 1
        with open(path, "rb") as fh:
            raw = fh.read()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as e:
            R.fail(S, "T1", f"{name}: not UTF-8 ({e})")
            continue
        if not text.strip():
            R.fail(S, "T2", f"{name}: empty",
                   "The contract wants at least one line saying why a file has nothing to hold.")
        if b"\r\n" in raw:
            R.warn(S, "T3", f"{name}: Windows line endings (CRLF); contract asks for LF")
    rp = os.path.join(folder, "REPORT.md")
    if os.path.isfile(rp):
        with open(rp, encoding="utf-8", errors="replace") as fh:
            words = len(fh.read().split())
        if words < 1200:
            R.ok(S, "T4", f"REPORT.md has {words} words (limit: under 1,200)")
        else:
            R.fail(S, "T4", f"REPORT.md has {words} words (limit: under 1,200)")
    if nread == 0:
        R.skip(S, "T1", "no fixed-name Markdown or Python files present to read")
    elif not any(i[0] == S and i[2] == "FAIL" for i in R.items):
        R.ok(S, "T1", f"{nread} Markdown/Python file(s) present and read: UTF-8, not empty")


# ---------------------------------------------------------------- 3. zips
def read_zip_lines(folder, name, R, S, on_record, progress_label):
    """Open a single-member zip, check its structure, stream every line to on_record.
    Returns the record count, or None if the zip could not be read."""
    path = os.path.join(folder, name)
    if not os.path.isfile(path):
        R.skip(S, "Z0", f"{name}: missing, not read")
        return None
    try:
        zf = zipfile.ZipFile(path)
    except zipfile.BadZipFile as e:
        R.fail(S, "Z1", f"{name}: not a readable zip ({e})")
        return None
    with zf:
        infos = zf.infolist()
        want = name[:-len(".zip")]
        names = [i.filename for i in infos]
        if len(infos) != 1 or names[0] != want:
            R.fail(S, "Z2", f"{name}: must hold exactly one member '{want}' at the root; holds {names[:6]}"
                   + (" …" if len(names) > 6 else ""),
                   "Re-zip with only the .jsonl file, no folders.")
            if want not in names:
                return None
        info = zf.getinfo(want)
        if info.compress_type not in (zipfile.ZIP_DEFLATED, zipfile.ZIP_STORED):
            R.warn(S, "Z3", f"{name}: compression method {info.compress_type} is not DEFLATE; some tools can't open it")
        n = bad = 0
        first_bad = None
        try:
            with zf.open(want) as fh:
                for raw in fh:
                    if not raw.strip():
                        continue
                    n += 1
                    try:
                        rec = strict_json_load(raw.decode("utf-8"))
                    except (ValueError, UnicodeDecodeError) as e:
                        bad += 1
                        if first_bad is None:
                            first_bad = (n, str(e)[:120])
                        continue
                    on_record(rec)
                    if n % 200000 == 0:
                        print(f"  … {progress_label}: {n:,} lines read", file=sys.stderr)
        except (zipfile.BadZipFile, OSError, EOFError) as e:
            R.fail(S, "Z4", f"{name}: zip is damaged or truncated after {n:,} lines ({e})",
                   "Usually an incomplete download. Download the file again.")
            return None
        if bad:
            R.fail(S, "Z5", f"{name}: {bad:,} of {n:,} lines are not valid JSON (first at line {first_bad[0]}: {first_bad[1]})")
        else:
            R.ok(S, "Z5", f"{name}: one member, {n:,} valid JSON lines")
        return n


# ---------------------------------------------------------------- 4. manifest
def check_manifest(man, R, files, engines):
    S = "4 Manifest"
    if not isinstance(man, dict):
        R.fail(S, "M0", "run_manifest.json is not a JSON object; manifest checks skipped")
        return None
    run = man.get("run") or {}
    leaked = [k for k in ("run_id", "condition") if k in run or k in man]
    if leaked:
        R.warn(S, "M1", f"manifest contains {leaked}; the template should not ask for these (it can leak study design)")
    else:
        R.ok(S, "M1", "no run_id/condition fields")

    up = run.get("upstream_files")
    if not isinstance(up, list) or sorted(up) != UPSTREAM_FILES:
        R.fail(S, "M1c", f"run.upstream_files is {up!r}; want {UPSTREAM_FILES}",
               "The brief asks the run to record the names of the two 01 files.")
    else:
        R.ok(S, "M1c", f"run.upstream_files = {up}")

    ledger = man.get("simulation_ledger")
    if not isinstance(ledger, list) or not ledger:
        R.fail(S, "M2", "simulation_ledger missing or empty")
        return None
    key_problems, enum_problems = [], []
    for i, e in enumerate(ledger):
        if not isinstance(e, dict):
            key_problems.append(f"entry {i}: not an object")
            continue
        if list(e.keys()) != LEDGER_KEYS:
            extra = [k for k in e if k not in LEDGER_KEYS]
            miss = [k for k in LEDGER_KEYS if k not in e]
            if extra or miss:
                key_problems.append(f"entry {i}: extra {extra} missing {miss}")
        p = e.get("purpose")
        if p not in PURPOSES:
            enum_problems.append(f"entry {i}: purpose '{p}'")
        if not (isinstance(e.get("engine_version"), str) and ENGINE_RE.match(e["engine_version"])):
            enum_problems.append(f"entry {i}: engine_version '{e.get('engine_version')}'")
        if e.get("new_or_rerun") not in NEW_OR_RERUN:
            enum_problems.append(f"entry {i}: new_or_rerun '{e.get('new_or_rerun')}'")
        if p in ("D8_arm", "D8_baseline"):
            aid, ak = e.get("arm_id"), e.get("arm_kind")
            if not (isinstance(aid, str) and ARM_ID_RE.match(aid)):
                enum_problems.append(f"entry {i}: arm_id '{aid}'")
            if p == "D8_baseline" and aid != "B0":
                enum_problems.append(f"entry {i}: baseline arm_id must be B0, got '{aid}'")
            if p == "D8_arm" and ak not in ARM_KINDS:
                enum_problems.append(f"entry {i}: arm_kind '{ak}'")
            if p == "D8_arm" and isinstance(aid, str):
                if (ak == "strategy") != aid.startswith("S"):
                    enum_problems.append(f"entry {i}: arm_id '{aid}' does not fit arm_kind '{ak}'")
        if not isinstance(e.get("games"), int) or e.get("games", -1) < 0:
            enum_problems.append(f"entry {i}: games '{e.get('games')}' is not a whole number")
        pgf = e.get("per_game_file")
        if pgf not in PER_GAME_FILES:
            enum_problems.append(f"entry {i}: per_game_file '{pgf}' is not one of the five per_game files")
        elif p in PURPOSES and p not in PER_GAME_FILES[pgf]:
            enum_problems.append(f"entry {i}: purpose {p} doesn't belong in {pgf}")
        ef = e.get("events_file")
        if ef is not None and ef not in EVENT_FILES:
            enum_problems.append(f"entry {i}: events_file '{ef}' is not one of the four events files")
    if key_problems:
        R.fail(S, "M2", f"{len(key_problems)} ledger entries break the fixed key list: {key_problems[:5]}",
               f"Each entry has exactly these keys, in this order: {LEDGER_KEYS}")
    else:
        R.ok(S, "M2", f"{len(ledger)} ledger entries, all with exactly the fixed keys")
    if enum_problems:
        R.fail(S, "M3", f"{len(enum_problems)} value(s) outside the fixed vocabulary: {enum_problems[:8]}")
    else:
        R.ok(S, "M3", "all ledger values use the fixed strings")

    totals = man.get("totals") or {}
    s_all = sum(e.get("games", 0) for e in ledger if isinstance(e, dict) and isinstance(e.get("games"), int))
    s_new = sum(e.get("games", 0) for e in ledger if isinstance(e, dict) and e.get("new_or_rerun") == "new"
                and isinstance(e.get("games"), int))
    if totals.get("games_executed") == s_all and totals.get("games_new") == s_new:
        R.ok(S, "M4", f"totals match the ledger: games_executed {s_all:,}, games_new {s_new:,}")
    else:
        R.fail(S, "M4", f"totals {totals} vs ledger sums executed={s_all:,} new={s_new:,}")

    # engine versions vs engine files
    ev = man.get("engine_versions") or []
    ids = [x.get("id") for x in ev if isinstance(x, dict)]
    bad_ids = [i for i in ids if not (isinstance(i, str) and ENGINE_RE.match(i))]
    if bad_ids:
        R.fail(S, "M5", f"engine_versions ids outside v0, v1, v2…: {bad_ids}")
    want_files = sorted(f"D02_engine_{i}.py" for i in ids if isinstance(i, str) and ENGINE_RE.match(i) and i != "v0")
    have_files = sorted(f for _, f in engines)
    if want_files == have_files:
        R.ok(S, "M5", f"engine files match manifest versions ({', '.join(i for i in ids if i != 'v0')})")
    else:
        R.fail(S, "M5", f"manifest lists {want_files}, folder has {have_files}")
    used = {e.get("engine_version") for e in ledger if isinstance(e, dict)}
    unknown = sorted(v for v in used if v not in ids)
    if unknown:
        R.fail(S, "M5b", f"ledger uses engine versions not declared in engine_versions: {unknown}")

    # vocabulary
    vocab = man.get("vocabulary") or {}
    if not isinstance(vocab, dict):
        R.fail(S, "M6", "vocabulary is not an object")
    else:
        badcat = [c for c in vocab if c not in VOCAB_CATEGORIES]
        badname, seen = [], collections.defaultdict(list)
        for c, d in vocab.items():
            if isinstance(d, dict):
                for nm in d:
                    if not SNAKE_RE.match(nm) and not (c in ID_KEYS and ID_KEYS[c].match(nm)):
                        badname.append(f"{c}:{nm}")
                    seen[nm].append(c)
        if badcat:
            R.fail(S, "M6", f"vocabulary categories not in the fixed list: {badcat}")
        else:
            R.ok(S, "M6", f"vocabulary uses only fixed categories ({len(vocab)} of {len(VOCAB_CATEGORIES)})")
        if badname:
            R.fail(S, "M7", f"{len(badname)} names are not lowercase snake_case: {badname[:8]}")
        else:
            R.ok(S, "M7", "all vocabulary names are snake_case (ids in readings/strategies keep their case)")
        dup = {n: c for n, c in seen.items() if len(c) > 1}
        if dup:
            R.warn(S, "M8", f"{len(dup)} names declared in more than one category (check they mean the same thing): "
                   f"{dict(list(dup.items())[:5])}")
    return ledger


def check_manifest_files(folder, man, R, files, engines, jsonl_counts):
    S = "4 Manifest"
    lst = man.get("files") if isinstance(man, dict) else None
    if not isinstance(lst, list):
        R.fail(S, "M9", "manifest has no 'files' list", "Contract §6: add the files list after everything else is final.")
        return
    expected = [f for f in FIXED_FILES if f != "run_manifest.json"] + [f for _, f in engines]
    listed = [x.get("name") for x in lst if isinstance(x, dict)]
    miss = sorted(set(expected) - set(listed))
    extra = sorted(set(listed) - set(expected))
    if miss or extra:
        R.fail(S, "M9", f"files list differs from the contract: missing {miss}, extra {extra}")
    else:
        R.ok(S, "M9", f"files list names all {len(expected)} files")
    mism = []
    for x in lst:
        if not isinstance(x, dict) or x.get("name") not in files:
            continue
        path = os.path.join(folder, x["name"])
        size = os.path.getsize(path)
        if x.get("bytes") != size:
            mism.append(f"{x['name']}: bytes {x.get('bytes')} vs {size}")
            continue
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        if (x.get("sha256") or "").lower() != h.hexdigest():
            mism.append(f"{x['name']}: sha256 differs")
        if x["name"].endswith(".jsonl.zip") and x["name"] in jsonl_counts:
            if x.get("records") != jsonl_counts[x["name"]]:
                mism.append(f"{x['name']}: records {x.get('records')} vs {jsonl_counts[x['name']]} lines")
        elif not x["name"].endswith(".jsonl.zip") and x.get("records") is not None:
            mism.append(f"{x['name']}: records should be null")
    if mism:
        R.fail(S, "M10", f"{len(mism)} file(s) don't match their size/hash/record count: {mism[:6]}",
               "A changed hash means the file changed after the manifest was written, or the download is damaged.")
    else:
        R.ok(S, "M10", "every listed file matches its size, sha256 and record count")


# ---------------------------------------------------------------- 5. per-game data
def collect_per_game(folder, R, ledger):
    S = "5 Per-game data"
    games = {}          # game_id -> compact tuple
    by_file = collections.defaultdict(list)
    counts = {}
    problems = collections.defaultdict(list)
    gid_re = re.compile(r"^(?P<purpose>[A-Za-z0-9_]+)/(?P<eng>v\d+)/(?P<mid>[^/]+)/(?P<seed>-?\d+)$")

    for fname, allowed in PER_GAME_FILES.items():
        def on_record(r, fname=fname, allowed=allowed):
            gid = r.get("game_id")
            purpose = r.get("purpose")
            if purpose not in allowed:
                problems["purpose in wrong file"].append(f"{fname}: {gid} has purpose {purpose}")
            m = gid_re.match(gid or "")
            if not m:
                problems["game_id format"].append(f"{fname}: '{gid}'")
            else:
                mid = m.group("mid")
                exp_mid = r.get("arm_id") if purpose in ("D8_arm", "D8_baseline") else f"{r.get('player_count')}p"
                if (m.group("purpose") != purpose or m.group("eng") != r.get("engine_version")
                        or mid != exp_mid or int(m.group("seed")) != r.get("seed")):
                    problems["game_id doesn't match the record's own fields"].append(f"{fname}: '{gid}'")
            if gid in games:
                problems["duplicate game_id"].append(gid)
            if not (isinstance(r.get("engine_version"), str) and ENGINE_RE.match(r["engine_version"])):
                problems["engine_version"].append(f"{gid}: {r.get('engine_version')}")
            ec = dig(r, "outcome", "end_condition")
            if ec not in END_CONDITIONS:
                problems["end_condition"].append(f"{gid}: {ec}")
            if purpose in ("D8_arm", "D8_baseline"):
                for k in ("arm_id", "arm_kind", "focal_seat"):
                    if k not in r:
                        problems["D8 record missing arm_id/arm_kind/focal_seat"].append(gid)
                        break
            players = r.get("players") or []
            winners = dig(r, "outcome", "winner_seats") or []
            games[gid] = {
                "file": fname, "purpose": purpose, "eng": r.get("engine_version"),
                "pc": r.get("player_count"), "seed": r.get("seed"), "arm": r.get("arm_id"),
                "kind": r.get("arm_kind"), "focal": r.get("focal_seat"),
                "typ": dig(r, "time", "play_min", "typical"), "smp": dig(r, "time", "play_min", "sampled"),
                "low": dig(r, "time", "play_min", "low"), "high": dig(r, "time", "play_min", "high"),
                "sess": dig(r, "time", "session_min", "typical"),
                "rmean": dig(r, "time", "round_min_typical", "mean"),
                "tmean": dig(r, "time", "turn_min_typical", "mean"),
                "rounds": dig(r, "time", "total_rounds"), "turns": dig(r, "time", "total_turns"),
                "winners": winners, "tie": dig(r, "outcome", "tie"),
                "wscore": dig(r, "outcome", "winning_score"),
                "zs": dig(r, "outcome", "players_with_zero_score"),
                "zl": dig(r, "outcome", "players_reaching_zero_lives"),
                "scores": {p.get("seat"): p.get("score") for p in players if isinstance(p, dict)},
                "roles": {p.get("seat"): p.get("role") for p in players if isinstance(p, dict)},
            }
            by_file[fname].append(gid)
        counts[fname] = read_zip_lines(folder, fname, R, S, on_record, fname)

    for what, lst in problems.items():
        R.fail(S, "P1", f"{what}: {len(lst):,} record(s), e.g. {lst[:3]}")
    if not problems and any(v is not None for v in counts.values()):
        R.ok(S, "P1", f"{len(games):,} per-game records: ids unique and well-formed, fixed strings used, purposes in the right files")

    # ledger reconciliation
    if ledger:
        led = collections.Counter()
        ranges = collections.defaultdict(list)
        for e in ledger:
            if not isinstance(e, dict) or not isinstance(e.get("games"), int):
                continue
            key = (e.get("per_game_file"), e.get("purpose"), e.get("engine_version"),
                   e.get("player_count"), e.get("arm_id") if e.get("purpose", "").startswith("D8") else None)
            led[key] += e["games"]
            ranges[key].append((e.get("seed_from"), e.get("seed_to")))
        got = collections.Counter()
        out_of_range = []
        for gid, g in games.items():
            key = (g["file"], g["purpose"], g["eng"], g["pc"], g["arm"] if (g["purpose"] or "").startswith("D8") else None)
            got[key] += 1
            rs = ranges.get(key)
            if rs and not any(isinstance(a, int) and isinstance(b, int) and a <= (g["seed"] or -10**18) <= b for a, b in rs):
                out_of_range.append(gid)
        diffs = []
        for key in sorted(set(led) | set(got), key=str):
            if led.get(key, 0) != got.get(key, 0):
                diffs.append(f"{key[1]} {key[2]} {key[3]}p {key[4] or ''} in {key[0]}: ledger {led.get(key, 0):,} vs records {got.get(key, 0):,}")
        if diffs:
            R.fail(S, "P2", f"{len(diffs)} ledger batch(es) don't match the records in the files: {diffs[:6]}",
                   "Every game in the ledger must be in the per-game file it names, and vice versa.")
        else:
            R.ok(S, "P2", f"every ledger batch matches its per-game records ({sum(got.values()):,} games)")
        if not games:
            R.skip(S, "P3", "no per-game records read, so seed ranges not checked")
        elif out_of_range:
            R.fail(S, "P3", f"{len(out_of_range):,} records have seeds outside their ledger range, e.g. {out_of_range[:3]}")
        else:
            R.ok(S, "P3", "every record's seed lies in its ledger batch's seed range")
    else:
        R.skip(S, "P2", "no usable ledger, so per-game records not reconciled with it")
    return games, counts


def check_sample_sizes(games, man, R):
    S = "6 Sample sizes"
    pcs = dig(man, "config", "player_counts") or []
    cnt = collections.Counter()
    for g in games.values():
        cnt[(g["purpose"], g["pc"], g["arm"])] += 1
    msgs = []
    if cnt[("D4_logged", 4, None)] != 1:
        msgs.append(f"D4_logged at 4p: {cnt[('D4_logged', 4, None)]} (want 1)")
    if cnt[("D4_batch", 4, None)] != 1000:
        msgs.append(f"D4_batch at 4p: {cnt[('D4_batch', 4, None)]} (want 1,000)")
    for pc in pcs:
        if cnt[("D5", pc, None)] != 1000:
            msgs.append(f"D5 at {pc}p: {cnt[('D5', pc, None)]} (want 1,000)")
    d7 = cnt[("D7_rerun", 4, None)]
    if d7 not in (1000, 1001):
        msgs.append(f"D7_rerun at 4p: {d7} (want 1,000)")
    elif d7 == 1001:
        R.warn(S, "S1", "D7_rerun has 1,001 games (the logged game was re-run too); brief asks for 1,000")
    base = sorted(g["seed"] for g in games.values() if g["purpose"] == "D8_baseline")
    if len(base) != 400:
        msgs.append(f"D8 baseline: {len(base)} (want 400)")
    arms = collections.defaultdict(list)
    for g in games.values():
        if g["purpose"] == "D8_arm":
            arms[g["arm"]].append(g["seed"])
    for a, seeds in sorted(arms.items()):
        if len(seeds) != 400:
            msgs.append(f"D8 arm {a}: {len(seeds)} (want 400)")
        elif sorted(seeds) != base:
            msgs.append(f"D8 arm {a}: seeds are not the baseline's seeds (pairing broken)")
    if msgs:
        R.fail(S, "S1", f"{len(msgs)} sample-size problem(s): {msgs[:8]}")
    else:
        R.ok(S, "S1", f"sample sizes as briefed; {len(arms)} D8 arms × 400 on the baseline's seeds")
    return arms


# ---------------------------------------------------------------- 7. events
def check_events(folder, games, R, skip):
    S = "7 Event logs"
    counts = {}
    if skip:
        R.skip(S, "E0", "event-log checks skipped (--skip-events); their record counts are not verified either")
        return counts
    for fname, purposes in EVENT_FILES.items():
        seen = collections.Counter()
        missing_field = [0]

        def on_record(r, seen=seen, missing_field=missing_field):
            g = r.get("game")
            if g is None or "type" not in r:
                missing_field[0] += 1
            seen[g] += 1
        counts[fname] = read_zip_lines(folder, fname, R, S, on_record, fname)
        if counts[fname] is None:
            continue
        if missing_field[0]:
            R.fail(S, "E1", f"{fname}: {missing_field[0]:,} events lack 'game' or 'type'")
        orphans = [g for g in seen if g not in games]
        if orphans:
            R.fail(S, "E2", f"{fname}: events for {len(orphans):,} game ids with no per-game record, e.g. {orphans[:3]}")
        if fname != "events_D08.jsonl.zip":
            want = [gid for gid, g in games.items() if g["purpose"] in purposes]
            lack = [gid for gid in want if gid not in seen]
        else:
            groups = collections.defaultdict(list)
            for gid, g in games.items():
                if g["purpose"] in purposes:
                    groups[g["arm"]].append((g["seed"], gid))
            want, lack = [], []
            for arm, lst in groups.items():
                first = [gid for _, gid in sorted(lst)[:EVENTS_D08_PER_ARM]]
                want += first
                lack += [gid for gid in first if gid not in seen]
        if lack:
            R.fail(S, "E3", f"{fname}: {len(lack):,} of {len(want):,} required games have no events, e.g. {lack[:3]}")
        else:
            R.ok(S, "E3", f"{fname}: events present for all {len(want):,} required games")
    return counts


# ---------------------------------------------------------------- 8. headline
def win_shares(glist, pc):
    tot = collections.Counter()
    for g in glist:
        w = g["winners"] or []
        for s in w:
            tot[s] += 1 / len(w)
    n = len(glist)
    return {s: tot[s] / n for s in range(1, pc + 1)} if n else {}


def recompute_d5(games, pc, target, tol_pct):
    gl = [g for g in games.values() if g["purpose"] == "D5" and g["pc"] == pc]
    if not gl:
        return None
    typ = [g["typ"] for g in gl if isinstance(g["typ"], (int, float))]
    smp = [g["smp"] for g in gl if isinstance(g["smp"], (int, float))]
    out = {"n_games": len(gl),
           "typical": {"p10": percentile(typ, .1), "median": percentile(typ, .5), "p90": percentile(typ, .9),
                       "mean": statistics.mean(typ) if typ else None},
           "sampled": {"p10": percentile(smp, .1), "median": percentile(smp, .5), "p90": percentile(smp, .9),
                       "mean": statistics.mean(smp) if smp else None}}
    out["rounds"] = percentile([g["rounds"] for g in gl if g["rounds"] is not None], .5)
    out["turns"] = percentile([g["turns"] for g in gl if g["turns"] is not None], .5)
    if target is not None and tol_pct is not None:
        lo, hi = target * (1 - tol_pct / 100), target * (1 + tol_pct / 100)
        for clk, xs in (("typical", typ), ("sampled", smp)):
            if xs:
                out.setdefault("exceeds", {})[clk] = sum(x > target for x in xs) / len(xs)
                out.setdefault("within", {})[clk] = sum(lo <= x <= hi for x in xs) / len(xs)
                out.setdefault("below", {})[clk] = sum(x < lo for x in xs) / len(xs)
        med = out["typical"]["median"]
        out["verdict"] = "short" if med < lo else ("long" if med > hi else "on_target")
    scores = [s for g in gl for s in g["scores"].values() if isinstance(s, (int, float))]
    out["score_pp"] = statistics.mean(scores) if scores else None
    out["wscore"] = percentile([g["wscore"] for g in gl if g["wscore"] is not None], .5)
    out["tie"] = sum(1 for g in gl if g["tie"]) / len(gl)
    out["zs"] = statistics.mean(g["zs"] for g in gl if g["zs"] is not None) if any(g["zs"] is not None for g in gl) else None
    out["zl"] = statistics.mean(g["zl"] for g in gl if g["zl"] is not None) if any(g["zl"] is not None for g in gl) else None
    out["seat"] = win_shares(gl, pc)
    return out


def check_headline(H, man, summ, games, arms, R):
    S = "8 headline.json"
    if not isinstance(H, dict):
        R.fail(S, "H0", "headline.json missing or not an object; headline checks skipped")
        return
    keys = list(H.keys())
    miss = [k for k in HEADLINE_KEYS if k not in H]
    extra = [k for k in keys if k not in HEADLINE_KEYS]
    if miss or extra:
        R.fail(S, "H1", f"top-level keys differ from the template: missing {miss}, extra {extra}")
    elif keys != HEADLINE_KEYS:
        R.warn(S, "H1", "all keys present but not in the template's order")
    else:
        R.ok(S, "H1", "top-level keys exactly as in the template")
    if H.get("schema") != "headline_v1":
        R.fail(S, "H1b", f"schema is '{H.get('schema')}', want 'headline_v1'")

    cfg = (man or {}).get("config") or {}
    pcs = cfg.get("player_counts") or []
    tmins = cfg.get("target_min") or {}
    tol = cfg.get("tolerance_pct")
    if H.get("player_counts") != pcs:
        R.fail(S, "H2", f"player_counts {H.get('player_counts')} vs manifest {pcs}")
    hm = dig(H, "targets", "min_by_player_count") or {}
    if {str(k): v for k, v in hm.items()} != {str(k): v for k, v in tmins.items()} or dig(H, "targets", "tolerance_pct") != tol:
        R.fail(S, "H2", f"targets {H.get('targets')} differ from manifest config (target_min {tmins}, tolerance {tol})")
    elif H.get("player_counts") == pcs:
        R.ok(S, "H2", "player counts and targets match the manifest")
    if man and H.get("games_executed") != dig(man, "totals", "games_executed"):
        R.fail(S, "H3", f"games_executed {H.get('games_executed')} vs manifest {dig(man, 'totals', 'games_executed')}")
    ids = [x.get("id") for x in (man or {}).get("engine_versions") or [] if isinstance(x, dict)]
    nums = [int(i[1:]) for i in ids if isinstance(i, str) and ENGINE_RE.match(i)]
    if nums and H.get("engine_version_final") != f"v{max(nums)}":
        R.fail(S, "H3", f"engine_version_final {H.get('engine_version_final')} but highest declared version is v{max(nums)}")

    # playtime + outcome recomputed from D5 games
    pt = {e.get("player_count"): e for e in H.get("playtime") or [] if isinstance(e, dict)}
    oc = {e.get("player_count"): e for e in H.get("outcome") or [] if isinstance(e, dict)}
    sgroups = {(g.get("purpose"), g.get("player_count")): g for g in (summ or {}).get("groups") or [] if isinstance(g, dict)}
    bad, checked = [], 0
    for pc in pcs:
        tgt = tmins.get(str(pc), tmins.get(pc))
        rc = recompute_d5(games, pc, tgt, tol)
        P, O = pt.get(pc), oc.get(pc)
        if P is None or O is None:
            bad.append(f"{pc}p: no playtime/outcome entry")
            continue
        if rc is None:
            bad.append(f"{pc}p: no D5 games to recompute from")
            continue
        checked += 1
        def cmp(label, have, want, tol_):
            if not close(have, want, tol_):
                bad.append(f"{pc}p {label}: headline {have} vs recomputed {None if want is None else round(want, 4)}")
        if P.get("n_games") != rc["n_games"]:
            bad.append(f"{pc}p n_games: {P.get('n_games')} vs {rc['n_games']}")
        for clk in ("typical", "sampled"):
            for q in ("p10", "median", "p90", "mean"):
                cmp(f"play_min.{clk}.{q}", dig(P, "play_min", clk, q), rc[clk][q], TOL_MIN)
        cmp("rounds_played_median", P.get("rounds_played_median"), rc["rounds"], TOL_MIN)
        cmp("turns_played_median", P.get("turns_played_median"), rc["turns"], TOL_MIN)
        for f, k in (("p_play_exceeds_target", "exceeds"), ("p_play_within_tolerance", "within"), ("p_play_below_tolerance", "below")):
            for clk in ("typical", "sampled"):
                cmp(f"{f}.{clk}", dig(P, f, clk), dig(rc, k, clk), TOL_SHARE)
        if P.get("verdict") != rc.get("verdict"):
            bad.append(f"{pc}p verdict: '{P.get('verdict')}' vs '{rc.get('verdict')}'")
        cmp("score_per_player_mean", O.get("score_per_player_mean"), rc["score_pp"], TOL_POINTS)
        cmp("winning_score_median", O.get("winning_score_median"), rc["wscore"], TOL_POINTS)
        cmp("tie_share", O.get("tie_share"), rc["tie"], TOL_SHARE)
        cmp("players_with_zero_score_per_game_mean", O.get("players_with_zero_score_per_game_mean"), rc["zs"], TOL_POINTS)
        cmp("players_reaching_zero_lives_per_game_mean", O.get("players_reaching_zero_lives_per_game_mean"), rc["zl"], TOL_POINTS)
        hs = {e.get("seat"): e.get("share") for e in O.get("win_share_by_seat") or [] if isinstance(e, dict)}
        for seat, sh in rc["seat"].items():
            cmp(f"win_share seat {seat}", hs.get(seat), sh, TOL_SHARE)
        roles = {e.get("role") for e in O.get("win_share_by_role") or [] if isinstance(e, dict)}
        vroles = set((dig(man, "vocabulary", "roles") or {}).keys())
        if vroles and roles - vroles:
            bad.append(f"{pc}p roles not in manifest vocabulary: {sorted(roles - vroles)}")
        # summary agreement
        G = sgroups.get(("D5", pc))
        if G is None:
            bad.append(f"{pc}p: summary.json has no D5 group")
        else:
            for q in ("p10", "median", "p90"):
                if not close(dig(G, "play_min", "typical", q), dig(P, "play_min", "typical", q), TOL_MIN):
                    bad.append(f"{pc}p summary play_min.typical.{q} {dig(G, 'play_min', 'typical', q)} vs headline {dig(P, 'play_min', 'typical', q)}")
    if bad:
        R.fail(S, "H4", f"{len(bad)} playtime/outcome value(s) disagree: {bad[:10]}",
               "Either headline.json was computed from different games or with a different method (contract §5).")
    elif checked:
        R.ok(S, "H4", f"playtime and outcome for {checked} player count(s) match a recompute from per_game_D05 and match summary.json")

    # D4 single game and batch
    d4 = H.get("d4_single_game") or {}
    logged = [g for g in games.values() if g["purpose"] == "D4_logged"]
    batch = [g["typ"] for g in games.values() if g["purpose"] == "D4_batch" and isinstance(g["typ"], (int, float))]
    b4 = []
    if logged:
        if d4.get("seed") != logged[0]["seed"]:
            b4.append(f"seed {d4.get('seed')} vs logged game {logged[0]['seed']}")
        if not close(d4.get("play_min_typical"), logged[0]["typ"], TOL_MIN):
            b4.append(f"play_min_typical {d4.get('play_min_typical')} vs {logged[0]['typ']}")
    if batch:
        for q, p in (("p10", .1), ("median", .5), ("p90", .9)):
            if not close(dig(d4, "batch_play_min_typical", q), percentile(batch, p), TOL_MIN):
                b4.append(f"batch {q} {dig(d4, 'batch_play_min_typical', q)} vs {round(percentile(batch, p), 4)}")
    if not isinstance(d4.get("representative"), bool):
        b4.append("representative is not true/false")
    if b4:
        R.fail(S, "H5", f"d4_single_game: {b4}")
    elif logged and batch:
        R.ok(S, "H5", "d4_single_game matches the D4 records")

    # D7
    d7 = H.get("d7_audit") or {}
    rer = [g["typ"] for g in games.values() if g["purpose"] == "D7_rerun" and isinstance(g["typ"], (int, float))]
    b7 = []
    if rer and not close(dig(d7, "rerun_play_min_typical_median", "after"), percentile(rer, .5), TOL_MIN):
        b7.append(f"after {dig(d7, 'rerun_play_min_typical_median', 'after')} vs {round(percentile(rer, .5), 4)}")
    if batch and not close(dig(d7, "rerun_play_min_typical_median", "before"), percentile(batch, .5), TOL_MIN):
        b7.append(f"before {dig(d7, 'rerun_play_min_typical_median', 'before')} vs D4 batch {round(percentile(batch, .5), 4)}")
    gf, gx, gu = d7.get("gaps_found"), d7.get("gaps_fixed"), d7.get("gaps_unfixed")
    if all(isinstance(x, int) for x in (gf, gx, gu)) and gf != gx + gu:
        b7.append(f"gaps_found {gf} ≠ gaps_fixed {gx} + gaps_unfixed {gu}")
    if b7:
        R.fail(S, "H6", f"d7_audit: {b7}")
    elif rer:
        R.ok(S, "H6", "d7_audit medians match the D4 and D7 records")

    # D8 arms
    harms = {a.get("arm_id"): a for a in H.get("d8_arms") or [] if isinstance(a, dict)}
    b8 = []
    if set(harms) != set(arms):
        b8.append(f"arm ids: headline {sorted(harms)} vs per-game {sorted(arms)}")
    sids = {s.get("id") for s in (summ or {}).get("strategies") or [] if isinstance(s, dict)}
    if summ is not None and sids != set(harms):
        b8.append(f"summary.json strategies {sorted(sids)} vs headline {sorted(harms)}")
    base = {g["seed"]: g for g in games.values() if g["purpose"] == "D8_baseline"}
    recomputed = 0
    for aid, a in harms.items():
        kind = a.get("arm_kind")
        if kind not in ARM_KINDS:
            b8.append(f"{aid}: arm_kind '{kind}'")
        if not (isinstance(aid, str) and ARM_ID_RE.match(aid)) or aid == "B0":
            b8.append(f"{aid}: not a valid arm_id")
        ci = dig(a, "score_diff", "ci95")
        if isinstance(ci, list) and len(ci) == 2 and all(isinstance(x, (int, float)) for x in ci):
            sig = not (ci[0] <= 0 <= ci[1])
            if a.get("significant") is not sig:
                b8.append(f"{aid}: significant={a.get('significant')} but ci95 {ci}")
        else:
            b8.append(f"{aid}: score_diff.ci95 missing")
        ag = [g for g in games.values() if g["purpose"] == "D8_arm" and g["arm"] == aid]
        if a.get("n_pairs") != len(ag):
            b8.append(f"{aid}: n_pairs {a.get('n_pairs')} vs {len(ag)} games")
        diffs, wdiffs = [], []
        for g in ag:
            b = base.get(g["seed"])
            if not b:
                continue
            if kind == "strategy" and g["focal"] is not None:
                fs = g["focal"]
                if isinstance(g["scores"].get(fs), (int, float)) and isinstance(b["scores"].get(fs), (int, float)):
                    diffs.append(g["scores"][fs] - b["scores"][fs])
                    wa = (1 / len(g["winners"])) if fs in (g["winners"] or []) else 0
                    wb = (1 / len(b["winners"])) if fs in (b["winners"] or []) else 0
                    wdiffs.append((wa - wb) * 100)
            elif kind == "reading":
                sa = [s for s in g["scores"].values() if isinstance(s, (int, float))]
                sb = [s for s in b["scores"].values() if isinstance(s, (int, float))]
                if sa and sb:
                    diffs.append(statistics.mean(sa) - statistics.mean(sb))
        if diffs:
            recomputed += 1
            if not close(dig(a, "score_diff", "mean"), statistics.mean(diffs), TOL_POINTS):
                b8.append(f"{aid}: score_diff.mean {dig(a, 'score_diff', 'mean')} vs recomputed {round(statistics.mean(diffs), 4)}")
            if kind == "strategy" and wdiffs and not close(dig(a, "win_diff_pp", "mean"), statistics.mean(wdiffs), 0.11):
                b8.append(f"{aid}: win_diff_pp.mean {dig(a, 'win_diff_pp', 'mean')} vs recomputed {round(statistics.mean(wdiffs), 3)}")
        if kind == "reading" and dig(a, "win_diff_pp", "mean") is not None:
            b8.append(f"{aid}: win_diff_pp should be null for a reading arm")
    if b8:
        R.fail(S, "H7", f"{len(b8)} D8 problem(s): {b8[:10]}")
    else:
        R.ok(S, "H7", f"{len(harms)} D8 arms match the per-game files; {recomputed} score differences recomputed from paired seeds")

    # interpretations, questions, duration table
    bi = []
    iids = [i.get("id") for i in H.get("interpretations") or [] if isinstance(i, dict)]
    if any(not (isinstance(i, str) and re.match(r"^I[1-9][0-9]*$", i)) for i in iids):
        bi.append("interpretation ids must be I1, I2, …")
    if len(set(iids)) != len(iids):
        bi.append("duplicate interpretation ids")
    for i in H.get("interpretations") or []:
        if isinstance(i, dict):
            if i.get("tag") not in ("C", "L", "G"):
                bi.append(f"{i.get('id')}: tag '{i.get('tag')}'")
            for t in i.get("tested_arm_ids") or []:
                if t not in harms:
                    bi.append(f"{i.get('id')}: tested_arm_ids lists unknown arm '{t}'")
    q = H.get("designer_questions") or []
    if len(q) > 5:
        bi.append(f"{len(q)} designer questions (max 5)")
    if [x.get("rank") for x in q if isinstance(x, dict)] != list(range(1, len(q) + 1)):
        bi.append("designer question ranks are not 1, 2, 3 … in order")
    for x in q:
        for t in (x.get("source_arm_ids") or []) if isinstance(x, dict) else []:
            if t not in harms:
                bi.append(f"question {x.get('rank')}: unknown source arm '{t}'")
    for d in H.get("duration_table") or []:
        if isinstance(d, dict):
            vals = [d.get("low_s"), d.get("typical_s"), d.get("high_s")]
            if not all(isinstance(v, (int, float)) for v in vals) or not (vals[0] <= vals[1] <= vals[2]):
                bi.append(f"duration '{d.get('event_type')}': need low ≤ typical ≤ high, got {vals}")
            et = set((dig(man, "vocabulary", "event_types") or {}).keys()) | set((dig(man, "vocabulary", "action_types") or {}).keys())
            if et and d.get("event_type") not in et:
                bi.append(f"duration '{d.get('event_type')}' not declared in vocabulary event_types/action_types")
    if not H.get("duration_table"):
        bi.append("duration_table is empty")
    if bi:
        R.fail(S, "H8", f"{len(bi)} problem(s) in interpretations/questions/duration table: {bi[:8]}")
    else:
        R.ok(S, "H8", f"{len(iids)} interpretations, {len(q)} designer questions, {len(H.get('duration_table') or [])} duration rows: consistent")


# ---------------------------------------------------------------- 9. RUNLOG
def check_runlog(text, man, engines, R):
    S = "9 RUNLOG"
    if not text:
        R.skip(S, "L0", "no --runlog given; RUNLOG line not compared")
        return
    m = re.search(r"games_simulated=(\d+)", text)
    if not m:
        R.fail(S, "L1", "RUNLOG has no games_simulated=<n>")
    elif man and int(m.group(1)) != dig(man, "totals", "games_executed"):
        R.fail(S, "L1", f"games_simulated {m.group(1)} vs manifest totals {dig(man, 'totals', 'games_executed')}")
    else:
        R.ok(S, "L1", f"games_simulated = manifest total ({m.group(1)})")
    m = (re.search(r"files_failed=\[?(.*?)\]?\s+files_written=", text)
         or re.search(r"files_failed=\[?([^\]\s]*)\]?", text))
    if not m:
        R.fail(S, "L3", "RUNLOG has no files_failed=<none|list>")
    elif m.group(1).strip().lower() in ("none", ""):
        R.ok(S, "L3", "files_failed=none")
    else:
        R.fail(S, "L3", f"the run reports files it could not deliver after three attempts: {m.group(1)}",
               "Ask for these files in the run's chat before RUN-END (operator step), or record them as missing.")
    m = re.search(r"files_written=\[?([^\]]*)\]?\s*$", text.strip())
    if not m:
        R.fail(S, "L2", "RUNLOG has no files_written=[...]")
        return
    listed = [x.strip() for x in m.group(1).split(",") if x.strip()]
    want = []
    for f in ORDER:
        want += [e for _, e in engines] if f == "<engines>" else [f]
    if listed == want:
        R.ok(S, "L2", "files_written lists exactly the contract files in order")
    elif sorted(listed) == sorted(want):
        R.warn(S, "L2", "files_written has the right files in a different order")
    else:
        R.fail(S, "L2", f"files_written differs: missing {sorted(set(want) - set(listed))}, extra {sorted(set(listed) - set(want))}")


# ---------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description="Check a run's output folder against output contract v2.2 (00b_output_contract.md).")
    ap.add_argument("folder", help="the run's output folder (the one holding REPORT.md)")
    ap.add_argument("--runlog", help="the RUNLOG line from the run's last message, in quotes")
    ap.add_argument("--json", help="also write the results to this JSON file (must be outside the folder)")
    ap.add_argument("--skip-events", action="store_true", help="skip the event-log checks (faster)")
    a = ap.parse_args(argv)

    folder = os.path.abspath(a.folder)
    if not os.path.isdir(folder):
        print(f"ERROR: '{folder}' is not a folder.", file=sys.stderr)
        return 2
    if a.json and os.path.dirname(os.path.abspath(a.json)) == folder:
        print("ERROR: --json must point outside the checked folder (a new file there would fail check F3).", file=sys.stderr)
        return 2

    R = Report()
    print(f"check_outputs.py {VERSION}\nChecking: {folder}\n", file=sys.stderr)
    files, engines = check_files(folder, R)
    S = "3 JSON files"
    man, _ = load_json_file(folder, "run_manifest.json", R, S, "J1")
    H, _ = load_json_file(folder, "headline.json", R, S, "J2")
    summ, _ = load_json_file(folder, "summary.json", R, S, "J3")
    load_json_file(folder, "D01_board_layout.json", R, S, "J4")
    check_text_files(folder, files, R)
    ledger = check_manifest(man, R, files, engines) if man is not None else None
    games, pg_counts = collect_per_game(folder, R, ledger)
    if games:
        arms = check_sample_sizes(games, man or {}, R)
    else:
        arms = {}
        R.skip("6 Sample sizes", "S0", "no per-game records read, so sample sizes not checked")
    ev_counts = check_events(folder, games, R, a.skip_events)
    if man is not None:
        check_manifest_files(folder, man, R, files, engines, {**pg_counts, **{k: v for k, v in ev_counts.items() if v is not None}})
    check_headline(H, man, summ, games, arms, R)
    check_runlog(a.runlog, man, engines, R)

    # print
    cur = None
    for sec, cid, lvl, msg, fix in sorted(R.items, key=lambda i: int(i[0].split()[0])):
        if sec != cur:
            print(f"\n== {sec}")
            cur = sec
        print(f"  [{lvl}] {cid}  {msg}")
        if fix and lvl in ("FAIL", "WARN"):
            print(f"         fix: {fix}")
    c = R.counts()
    verdict = "FAILED" if c["FAIL"] else "PASSED"
    print(f"\nRESULT: {verdict}  ({c['PASS']} pass, {c['FAIL']} fail, {c['WARN']} warn, {c['SKIP']} skipped)")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump({"tool": VERSION, "folder": folder, "result": verdict, "counts": dict(c),
                       "items": [dict(zip(("section", "id", "level", "message", "fix"), i)) for i in R.items]},
                      fh, indent=1, ensure_ascii=False)
        print(f"Results also written to {a.json}")
    return 1 if c["FAIL"] else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(2)
    except Exception as e:  # never fail silently
        import traceback
        traceback.print_exc()
        print(f"\nERROR: the checker itself crashed ({type(e).__name__}: {e}). "
              "Nothing above this line is a complete result.", file=sys.stderr)
        sys.exit(2)
