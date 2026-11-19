"""playtime_recompute.py: play time of a finished run under measured human timings. No AI involved.

    python tools/playtime_recompute.py                 # newest run; finds 01_timings.json itself
    python tools/playtime_recompute.py 14              # Run14_...
    python tools/playtime_recompute.py 14 --timings my_timings.json

Where it looks for the timings (first hit wins): --timings, the run folder, then
<kit>/games/<game>/01_timings.json for the run's game. Without any timings file it still runs and
lists which categories carry most of the play time: the ones to time first.

It applies contract section 7.3 to the run's own D03_duration_table.json and events_D05:
  provided  categories in the timings file replace the run's values,
  inferred  the other in-play categories are scaled by provided / assumed time,
  assumed   no in-play timing given: the run's own estimate stays.
Observed sessions are compared, not applied.

Needs a run made under contract v2.3 or later (every event carries 'dur').
Writes <run>/_check/playtime_recompute/: PLAYTIME_RECOMPUTE.md, playtime_recomputed.json,
D03_duration_table_recomputed.json. The run's own files are not changed.
"""
import argparse
import glob
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runfolder as RF                                         # noqa: E402
import timings as T                                            # noqa: E402


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def find_timings(arg, run, game):
    if arg:
        return os.path.abspath(arg)
    p = os.path.join(run, "01_timings.json")
    if os.path.isfile(p):
        return p
    cands = glob.glob(os.path.join(RF.KIT, "games", "*", "01_timings.json"))
    for c in cands:
        try:
            g = (load(c).get("game") or "").strip().lower()
        except (OSError, ValueError):
            continue
        if game and g and (g in game.lower() or game.lower() in g):
            return c
    return None


def timings_problems(tm):
    out = []
    for cat, v in (tm.get("categories") or {}).items():
        if cat not in T.CATEGORIES:
            out.append(f"'{cat}' is not a category; ignored (categories: contract 7.1)")
            continue
        if not isinstance(v, dict):
            continue
        lo, hi, ty = v.get("min_s"), v.get("max_s"), v.get("typical_s")
        if (lo is None) != (hi is None):
            out.append(f"{cat}: only one of min_s/max_s filled; ignored (both are needed)")
        elif lo is not None and not (isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and 0 <= lo <= hi):
            out.append(f"{cat}: need 0 <= min_s <= max_s, got {lo}, {hi}")
        elif ty is not None and lo is not None and not lo <= ty <= hi:
            out.append(f"{cat}: typical_s {ty} outside min..max")
    return out


def pctl(xs):
    return {"p10": round(T.percentile(xs, 0.1), 2), "median": round(statistics.median(xs), 2),
            "p90": round(T.percentile(xs, 0.9), 2), "mean": round(statistics.fmean(xs), 2)} if xs else None


def verdict(med, target, tol):
    if target is None or med is None:
        return None
    t = (tol or 0) / 100 * target
    return "short" if med < target - t else "long" if med > target + t else "on_target"


def main(argv=None):
    for _s in (sys.stdout, sys.stderr):        # Windows code pages: never crash on a character
        try:
            _s.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", nargs="?", help="run number, name or path (default: the newest run folder)")
    ap.add_argument("--timings", help="a 01_timings.json to use instead of the one found automatically")
    ap.add_argument("--runs", help="the folder holding the run folders (default: ../runs next to the kit folder)")
    a = ap.parse_args(argv)

    run = RF.find_run(a.run, a.runs)
    src = RF.check_out(run) if os.path.isdir(RF.check_out(run)) else run
    need = ["D03_duration_table.json", "events_D05.jsonl.zip", "per_game_D05.jsonl.zip", "headline.json"]
    lacking = [f for f in need if not os.path.isfile(os.path.join(src, f))]
    if lacking:
        sys.exit(f"{os.path.basename(run)}: {', '.join(lacking)} not found in {src}. "
                 "Run after_run.py first; runs before contract v2.3 (v5.1) have no duration table to recompute.")
    table = load(os.path.join(src, "D03_duration_table.json"))
    probs = T.table_problems(table)
    if probs:
        sys.exit(f"D03_duration_table.json is not usable: {probs[:4]}")
    H = load(os.path.join(src, "headline.json"))
    tpath = find_timings(a.timings, run, H.get("game"))
    tm = load(tpath) if tpath else {}
    tprobs = timings_problems(tm) if tm else []

    events = os.path.join(src, "events_D05.jsonl.zip")
    new, rep = T.apply_timings(table, tm, events)
    old_rows, new_rows = T.rows_by_id(table), T.rows_by_id(new)
    out_rows = {rid for rid, r in new_rows.items() if not r.get("in_play", True)}

    pc_of = {}
    for g in T.iter_jsonl_zip(os.path.join(src, "per_game_D05.jsonl.zip")):
        pc_of[g["game_id"]] = g.get("player_count")
    per_pc = {}
    no_dur = 0
    for gid, evs in T.events_by_game(events, set(pc_of)):
        no_dur += sum(1 for e in evs if "dur" not in e)
        before, _ = T.game_clocks(evs, old_rows)
        after, _ = T.game_clocks(evs, new_rows)
        outside = sum((e.get("dur") or {}).get("n", 1) * new_rows[e["dur"]["row"]]["typical_s"]
                      for e in evs if (e.get("dur") or {}).get("row") in out_rows) / 60
        d = per_pc.setdefault(pc_of[gid], {"before": [], "after": {c: [] for c in T.CLOCKS}, "outside": []})
        d["before"].append(before["typical"])
        for c in T.CLOCKS:
            d["after"][c].append(after[c])
        d["outside"].append(outside)
    if no_dur:
        sys.exit(f"{no_dur:,} D5 events carry no 'dur': this run predates contract v2.3 and cannot be recomputed.")

    targets = H.get("targets") or {}
    tol = targets.get("tolerance_pct")
    basis = targets.get("basis") or "play"
    results = []
    for pc in sorted(per_pc):
        d = per_pc[pc]
        target = (targets.get("min_by_player_count") or {}).get(str(pc))
        med_after = statistics.median(d["after"]["typical"])
        med_session = statistics.median([x + y for x, y in zip(d["after"]["typical"], d["outside"])])
        med_basis = med_session if basis == "session" else med_after
        results.append({
            "player_count": pc, "n_games": len(d["before"]),
            "play_min_run_typical_median": round(statistics.median(d["before"]), 2),
            "play_min_recomputed": {c: pctl(d["after"][c]) for c in T.CLOCKS},
            "session_min_recomputed_typical_median": round(med_session, 2),
            "target_min": target, "target_basis": basis,
            "verdict_run": verdict(statistics.median(d["before"]) + (statistics.median(d["outside"]) if basis == "session" else 0), target, tol),
            "verdict_recomputed": verdict(med_basis, target, tol)})
    sessions = []
    for s in tm.get("sessions") or []:
        if not isinstance(s, dict) or not isinstance(s.get("play_min"), (int, float)):
            continue
        r = next((x for x in results if x["player_count"] == s.get("player_count")), None)
        sim = r["play_min_recomputed"]["typical"]["median"] if r else None
        sessions.append({**{k: s.get(k) for k in ("player_count", "play_min", "setup_min", "first_play", "note")},
                         "simulated_median": sim, "ratio_observed_to_simulated": round(s["play_min"] / sim, 2) if sim else None})

    outd = os.path.join(run, RF.CHECK_DIR, "playtime_recompute")
    os.makedirs(outd, exist_ok=True)
    with open(os.path.join(outd, "D03_duration_table_recomputed.json"), "w", encoding="utf-8") as fh:
        json.dump(new, fh, indent=2)
    summary = {"run": os.path.basename(run), "game": H.get("game"), "timings_file": tpath,
               "timings_problems": tprobs, "sources": {k: rep[k] for k in ("provided", "inferred", "assumed")},
               "scale_basis": rep["scale_basis"], "scale_factors": rep["scale_factors"],
               "share_of_play_time_typical": rep["share_of_play_time_assumed_typical"],
               "occurrences_D5": rep["occurrences"], "by_player_count": results, "sessions": sessions}
    with open(os.path.join(outd, "playtime_recomputed.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    # ---- report in D11 order (contract 7.4)
    share = rep["share_of_play_time_assumed_typical"]
    L = [f"# Play time recomputed: {os.path.basename(run)}", "",
         f"Game: {H.get('game')}. Timings file: {tpath or 'none found'}. "
         f"Computed from the run's own duration table and its {sum(r['n_games'] for r in results):,} D5 games; no AI involved.", ""]
    if tprobs:
        L += ["**Problems in the timings file:**"] + [f"- {x}" for x in tprobs] + [""]
    L += ["## Result", "", f"Target basis: {basis}; tolerance {tol}%.", "",
          "| Players | Run (typical median) | Recomputed low / typical / high median | p10–p90 typical | Target | Verdict run → recomputed |",
          "|---|---|---|---|---|---|"]
    for r in results:
        pr = r["play_min_recomputed"]
        L.append(f"| {r['player_count']} | {r['play_min_run_typical_median']} | {pr['low']['median']} / {pr['typical']['median']} / "
                 f"{pr['high']['median']} | {pr['typical']['p10']}–{pr['typical']['p90']} | {r['target_min']} | "
                 f"{r['verdict_run']} → {r['verdict_recomputed']} |")
    L += ["", "Minutes of play (first turn to final scoring)" + (", targets compared on session time (play + setup/teardown rows)." if basis == "session" else "."), ""]
    L += ["## 1. What was used", ""]
    if rep["provided"]:
        for cat in rep["provided"]:
            v = tm["categories"][cat]
            L.append(f"- `{cat}`: min {v.get('min_s')} s, typical {v.get('typical_s') if v.get('typical_s') is not None else 'midpoint'}, "
                     f"max {v.get('max_s')} s" + (f", {v.get('observations')} observations" if v.get("observations") else "")
                     + (f" ({v.get('note')})" if v.get("note") else ""))
    else:
        L.append("- No measured category timings were supplied.")
    if sessions:
        L += ["", "| Observed session | Players | Play min | Simulated median | Observed ÷ simulated |", "|---|---|---|---|---|"]
        for i, s in enumerate(sessions, 1):
            L.append(f"| {i}{' (first play)' if s.get('first_play') else ''} | {s['player_count']} | {s['play_min']} | "
                     f"{s['simulated_median']} | {s['ratio_observed_to_simulated']} |")
        L.append("Sessions are compared, not applied to the clocks (contract 7.3 step 3).")
    else:
        L.append("- No observed sessions were supplied.")
    L += ["", "## 2. What was assumed or inferred", "",
          f"Scale factors (low / typical / high): {rep['scale_factors']['low']} / {rep['scale_factors']['typical']} / "
          f"{rep['scale_factors']['high']}" + (f", based on {', '.join(rep['scale_basis'])}." if rep["scale_basis"] else " (no in-play timing given)."),
          "", "| Category | Source | Share of D5 play time (typical) | Typical s per row (recomputed) |", "|---|---|---|---|"]
    by_cat = {}
    for r in new["rows"]:
        by_cat.setdefault(r["category"], []).append(r)
    for cat in sorted(by_cat, key=lambda c: -share.get(c, 0)):
        rows = by_cat[cat]
        srcs = sorted({r["value_source"] for r in rows})
        vals = ", ".join(f"{r['id']} {r['typical_s']}" for r in rows[:4]) + (" …" if len(rows) > 4 else "")
        L.append(f"| `{cat}` | {'/'.join(srcs)} | {share.get(cat, 0) * 100:.1f}%{'' if rows[0].get('in_play', True) else ' (outside play)'} | {vals} |")
    todo = [c for c in sorted(share, key=lambda c: -share[c]) if c not in rep["provided"]]
    L += ["", "## 3. Where it is recorded", "",
          "- Row level: `D03_duration_table_recomputed.json` (this folder); the run's own table is unchanged.",
          "- Summary: `playtime_recomputed.json` (this folder).", "- This file.", "",
          "## 4. What else can be supplied", ""]
    if todo:
        L.append("Time these categories next, largest share of play time first: "
                 + ", ".join(f"`{c}` ({share[c] * 100:.0f}%)" for c in todo[:5]) + ".")
    have = {s["player_count"] for s in sessions}
    miss = [r["player_count"] for r in results if r["player_count"] not in have]
    if miss:
        L.append(f"Observed sessions for {', '.join(map(str, miss))} players (play minutes, setup minutes, first play or not).")
    L.append("Form: `templates/01_timings.template.json` in the kit folder. Fill any subset; put it in the run folder "
             "or in `games/<game>/01_timings.json`, then run this script again.")
    with open(os.path.join(outd, "PLAYTIME_RECOMPUTE.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"\nWritten: {outd}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
