"""import_sqlite.py: copy one run's results into a shared SQLite database for querying.

JSON stays the source of truth (team decision); the database is a read copy you can rebuild.

    python tools/import_sqlite.py              # newest run -> runs/pipeline.sqlite
    python tools/import_sqlite.py 14           # Run14_...
    python tools/import_sqlite.py 14 --events  # also the event logs (large)
    python tools/import_sqlite.py 12 --force   # import a run that did not pass the validator

Run after_run.py first: the import reads <run>/_check/out and the validator result in
<run>/_check/check.json, and refuses a run that did not pass unless --force is given.
Importing the same run again replaces its rows. Standard library only.

Tables (run_id = the run folder's name, in every table):
  runs, files, ledger, vocabulary, duration_rows, playtime, outcome, focus_options, d8_arms,
  games (one row per per-game record), players, stats, events (only with --events)
Example query:
  SELECT run_id, player_count, play_typical_median FROM playtime ORDER BY run_id, player_count;
"""
import argparse
import csv
import datetime
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runfolder as RF                                         # noqa: E402
import timings as T                                            # noqa: E402

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, game TEXT, d1_source TEXT, headline_schema TEXT,
  engine_version_final TEXT, games_executed INTEGER, validator TEXT, validator_passed INTEGER,
  model TEXT, active_minutes REAL, tool_calls INTEGER, reported_usd REAL, skills_flagged TEXT,
  headline_json TEXT, imported_at TEXT);
CREATE TABLE IF NOT EXISTS files (run_id TEXT, name TEXT, bytes INTEGER, sha256 TEXT, records INTEGER);
CREATE TABLE IF NOT EXISTS ledger (run_id TEXT, purpose TEXT, arm_id TEXT, arm_kind TEXT, engine_version TEXT,
  player_count INTEGER, seed_from INTEGER, seed_to INTEGER, games INTEGER, new_or_rerun TEXT,
  per_game_file TEXT, events_file TEXT, logged_games INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS vocabulary (run_id TEXT, category TEXT, name TEXT, description TEXT);
CREATE TABLE IF NOT EXISTS duration_rows (run_id TEXT, id TEXT, category TEXT, per TEXT, in_play INTEGER,
  low_s REAL, typical_s REAL, high_s REAL, value_source TEXT, assumed_low_s REAL, assumed_typical_s REAL,
  assumed_high_s REAL, note TEXT);
CREATE TABLE IF NOT EXISTS playtime (run_id TEXT, player_count INTEGER, engine_version TEXT, n_games INTEGER,
  play_typical_p10 REAL, play_typical_median REAL, play_typical_p90 REAL, play_sampled_median REAL,
  play_low_median REAL, play_high_median REAL, session_typical_median REAL, verdict TEXT);
CREATE TABLE IF NOT EXISTS outcome (run_id TEXT, player_count INTEGER, mode TEXT, json TEXT);
CREATE TABLE IF NOT EXISTS focus_options (run_id TEXT, focus_name TEXT, chosen_by TEXT, outcome_metric TEXT,
  player_count INTEGER, option TEXT, outcome REAL, use_per_player_turn REAL, idle_share REAL, spread REAL);
CREATE TABLE IF NOT EXISTS d8_arms (run_id TEXT, arm_id TEXT, json TEXT);
CREATE TABLE IF NOT EXISTS games (run_id TEXT, file TEXT, rowno INTEGER, game_id TEXT, seed INTEGER,
  engine_version TEXT, purpose TEXT, player_count INTEGER, arm_id TEXT, arm_kind TEXT, focal_seat INTEGER,
  mode TEXT, end_condition TEXT, ended_on_round INTEGER, team_result TEXT, tie INTEGER, winning_score REAL,
  play_low REAL, play_typical REAL, play_high REAL, play_sampled REAL, session_typical REAL,
  total_rounds INTEGER, total_turns INTEGER, total_actions INTEGER, illegal_actions INTEGER,
  bound_violations INTEGER);
CREATE TABLE IF NOT EXISTS players (run_id TEXT, file TEXT, rowno INTEGER, game_id TEXT, seat INTEGER, role TEXT,
  score REAL, turns_total INTEGER, turns_idle INTEGER, turns_zero_move INTEGER, turns_skipped INTEGER,
  turns_no_legal_move INTEGER);
CREATE TABLE IF NOT EXISTS stats (run_id TEXT, file TEXT, rowno INTEGER, game_id TEXT, seat INTEGER,
  label TEXT, status TEXT, value REAL);
CREATE TABLE IF NOT EXISTS events (run_id TEXT, file TEXT, game_id TEXT, seq INTEGER, type TEXT,
  action_id INTEGER, dur_row TEXT, dur_n REAL, json TEXT);
CREATE INDEX IF NOT EXISTS games_ix ON games (run_id, purpose, player_count);
CREATE INDEX IF NOT EXISTS stats_ix ON stats (run_id, label);
"""
TABLES = ["runs", "files", "ledger", "vocabulary", "duration_rows", "playtime", "outcome", "focus_options",
          "d8_arms", "games", "players", "stats", "events"]
PER_GAME = ["per_game_D04.jsonl.zip", "per_game_D05.jsonl.zip", "per_game_D07.jsonl.zip",
            "per_game_D08.jsonl.zip", "per_game_other.jsonl.zip"]
EVENTS = ["events_D04.jsonl.zip", "events_D05.jsonl.zip", "events_D07.jsonl.zip", "events_D08.jsonl.zip"]


def g(d, *keys):
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def main(argv=None):
    for _s in (sys.stdout, sys.stderr):        # Windows code pages: never crash on a character
        try:
            _s.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", nargs="?", help="run number, name or path (default: the newest run folder)")
    ap.add_argument("--db", help="database file (default: pipeline.sqlite in the runs folder)")
    ap.add_argument("--events", action="store_true", help="also import the event logs")
    ap.add_argument("--force", action="store_true", help="import even if the validator did not pass")
    ap.add_argument("--runs", help="the folder holding the run folders (default: ../runs next to the kit folder)")
    a = ap.parse_args(argv)

    run = RF.find_run(a.run, a.runs)
    rid = os.path.basename(run)
    src = RF.check_out(run)
    if not os.path.isdir(src):
        sys.exit(f"{rid}: no _check/out folder. Run after_run.py first.")
    chk = load(os.path.join(run, RF.CHECK_DIR, "check.json")) or {}
    passed = bool(chk.get("passed")) if "passed" in chk else chk.get("result", "").startswith("PASSED")
    vres = chk.get("result") or chk.get("summary") or ("PASSED" if passed else "unknown")
    if not passed and not a.force:
        sys.exit(f"{rid}: the validator did not pass ({vres}). Fix the run, or add --force to import it anyway "
                 "(it is then marked validator_passed = 0).")
    H = load(os.path.join(src, "headline.json")) or {}
    M = load(os.path.join(src, "run_manifest.json")) or {}
    U = {}
    up = os.path.join(run, RF.CHECK_DIR, "usage.csv")
    if os.path.isfile(up):
        with open(up, encoding="utf-8") as fh:
            U = next(csv.DictReader(fh), {}) or {}

    db = a.db or os.path.join(RF.runs_dir(a.runs) if not a.run or not os.path.isdir(str(a.run)) else os.path.dirname(run),
                              "pipeline.sqlite")
    con = sqlite3.connect(db)
    con.executescript(SCHEMA)
    for t in TABLES:
        con.execute(f"DELETE FROM {t} WHERE run_id = ?", (rid,))
    ins = lambda t, row: con.execute(f"INSERT INTO {t} VALUES ({','.join('?' * len(row))})", row)  # noqa: E731

    ins("runs", (rid, H.get("game") or g(M, "run", "game"), g(M, "run", "d1_source"), H.get("schema"),
                 H.get("engine_version_final"), num(g(M, "totals", "games_executed")), str(vres), int(passed),
                 U.get("models_list") or U.get("model"), num(float(U["active_minutes"])) if U.get("active_minutes") else None,
                 int(U["tool_calls"]) if U.get("tool_calls") else None,
                 float(U["reported_usd"]) if U.get("reported_usd") else None, U.get("skills_flagged") or None,
                 json.dumps(H), datetime.datetime.now().isoformat(timespec="seconds")))
    for f in M.get("files") or []:
        ins("files", (rid, f.get("name"), f.get("bytes"), f.get("sha256"), f.get("records")))
    keys = ["purpose", "arm_id", "arm_kind", "engine_version", "player_count", "seed_from", "seed_to", "games",
            "new_or_rerun", "per_game_file", "events_file", "logged_games", "note"]
    for e in M.get("simulation_ledger") or []:
        ins("ledger", (rid, *[e.get(k) for k in keys]))
    for cat, names in (M.get("vocabulary") or {}).items():
        if isinstance(names, dict):
            for n, d in names.items():
                ins("vocabulary", (rid, cat, n, d if isinstance(d, str) else json.dumps(d)))
    table = load(os.path.join(src, "D03_duration_table.json"))
    for r in (table or {}).get("rows") or []:
        a_ = r.get("assumed") or {}
        ins("duration_rows", (rid, r.get("id"), r.get("category"), r.get("per"), int(bool(r.get("in_play"))),
                              r.get("low_s"), r.get("typical_s"), r.get("high_s"), r.get("value_source"),
                              a_.get("low_s"), a_.get("typical_s"), a_.get("high_s"), r.get("note")))
    for p in H.get("playtime") or []:
        pm = p.get("play_min") or {}
        ins("playtime", (rid, p.get("player_count"), p.get("engine_version"), p.get("n_games"),
                         g(pm, "typical", "p10"), g(pm, "typical", "median"), g(pm, "typical", "p90"),
                         g(pm, "sampled", "median"), pm.get("low_median"), pm.get("high_median"),
                         p.get("session_min_typical_median"), p.get("verdict")))
    for o in H.get("outcome") or []:
        ins("outcome", (rid, o.get("player_count"), o.get("mode"), json.dumps(o)))
    for f in H.get("focus_items") or []:
        for bp in f.get("by_player_count") or []:
            for op in bp.get("options") or []:
                ins("focus_options", (rid, f.get("name"), f.get("chosen_by"), f.get("outcome_metric"),
                                      bp.get("player_count"), op.get("option"), num(g(op, "outcome", "value")) if isinstance(op.get("outcome"), dict) else num(op.get("outcome")),
                                      num(op.get("use_per_player_turn")), num(op.get("idle_share")), num(bp.get("spread"))))
    for d in H.get("d8_arms") or []:
        ins("d8_arms", (rid, d.get("arm_id"), json.dumps(d)))

    n_games = n_events = 0
    for fname in PER_GAME:
        path = os.path.join(src, fname)
        if not os.path.isfile(path):
            continue
        for i, r in enumerate(T.iter_jsonl_zip(path)):
            gid, t, o, au, ac = r.get("game_id"), r.get("time") or {}, r.get("outcome") or {}, r.get("audit") or {}, r.get("actions") or {}
            pm = t.get("play_min") or {}
            ins("games", (rid, fname, i, gid, r.get("seed"), r.get("engine_version"), r.get("purpose"), r.get("player_count"),
                          r.get("arm_id"), r.get("arm_kind"), r.get("focal_seat"), o.get("mode"), o.get("end_condition"),
                          o.get("ended_on_round"), o.get("team_result"), None if o.get("tie") is None else int(bool(o.get("tie"))),
                          num(o.get("winning_score")), num(pm.get("low")), num(pm.get("typical")), num(pm.get("high")),
                          num(pm.get("sampled")), num(g(t, "session_min", "typical")), t.get("total_rounds"), t.get("total_turns"),
                          ac.get("total_actions"), au.get("illegal_actions"), au.get("bound_violations")))
            for p in r.get("players") or []:
                tu = p.get("turns") or {}
                ins("players", (rid, fname, i, gid, p.get("seat"), p.get("role"), num(p.get("score")), tu.get("total"),
                                tu.get("idle"), tu.get("zero_move"), tu.get("skipped"), tu.get("no_legal_move")))
                for s in p.get("stats") or []:
                    ins("stats", (rid, fname, i, gid, p.get("seat"), s.get("label"), s.get("status"), num(s.get("value"))))
            for s in r.get("game_stats") or []:
                ins("stats", (rid, fname, i, gid, None, s.get("label"), s.get("status"), num(s.get("value"))))
            n_games += 1
    if a.events:
        for fname in EVENTS:
            path = os.path.join(src, fname)
            if not os.path.isfile(path):
                continue
            for e in T.iter_jsonl_zip(path):
                d = e.get("dur") or {}
                ins("events", (rid, fname, e.get("game"), e.get("seq"), e.get("type"), e.get("action_id"),
                               d.get("row"), d.get("n"), json.dumps(e)))
                n_events += 1
    con.commit()
    con.close()
    print(f"{rid}: imported {n_games:,} game records" + (f" and {n_events:,} events" if a.events else "")
          + f" into {db}" + ("" if passed else "  (validator did not pass; marked validator_passed = 0)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
