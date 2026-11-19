"""Build a small synthetic run folder that follows output contract v2.3 exactly.
Used only to test check_outputs.py. Percentiles here come from numpy, independently of the checker.
usage: python make_fake_run.py <out_folder> [raw|extraction] [competitive|cooperative]"""
import hashlib, json, os, random, sys, zipfile
import numpy as np

out = sys.argv[1]
path = sys.argv[2] if len(sys.argv) > 2 else "raw"
MODE = sys.argv[3] if len(sys.argv) > 3 else "competitive"
# id: (low, typical, high, category, in_play, per). One move action = a move event (n=1) plus a
# move_step event (n=STEPS) sharing an action_id: 30 / 60 / 120 s per move on the three clocks.
DUR = {"set_up": (300, 480, 720, "setup", False, "event"), "move": (10, 20, 40, "move", True, "event"),
       "move_step": (10, 20, 40, "move", True, "step")}
STEPS = 2
os.makedirs(out, exist_ok=True)
rng = random.Random(7)
ROLES = ["shovel", "torch", "teleporter", "backpack"]
TARGET = {"2": 30, "3": 45, "4": 60}
TOL = 20


def game(purpose, eng, pc, seed, arm=None, kind=None, focal=None, boost=0.0):
    r = random.Random(seed * 31 + len(purpose))
    k_moves = max(1, int(round(7 * pc + r.gauss(0, 1.5))))
    typ = k_moves * 60 / 60
    scores = {s: max(0, int(r.gauss(4, 2))) for s in range(1, pc + 1)}
    if kind == "strategy" and focal:
        scores[focal] += int(boost)
    if kind == "reading":
        for s in scores:
            scores[s] += int(boost)
    top = max(scores.values())
    winners = [s for s, v in scores.items() if v == top]
    team = None
    if MODE == "cooperative":
        team = "win" if (sum(scores.values()) + seed) % 3 else "loss"
        if kind == "strategy" and focal and boost:
            team = "win"
        winners = list(scores) if team == "win" else []
    gid = f"{purpose}/{eng}/{arm}/{seed}" if purpose.startswith("D8") else f"{purpose}/{eng}/{pc}p/{seed}"
    rec = {"schema_version": "0.6", "game_id": gid, "seed": seed, "engine_version": eng,
           "purpose": purpose, "player_count": pc,
           "_k": k_moves,
           "time": {"play_min": {"low": k_moves * 30 / 60, "typical": typ, "high": k_moves * 120 / 60, "sampled": round(typ * 1.1, 4)},
                    "session_min": {"low": typ, "typical": typ + 8, "high": typ * 2 + 8, "sampled": typ + 9},
                    "total_rounds": 12, "total_turns": 12 * pc,
                    "round_min_typical": {"min": 1, "mean": typ / 12, "median": typ / 12, "max": 3},
                    "turn_min_typical": {"min": .1, "mean": typ / 12 / pc, "median": typ / 12 / pc, "max": 1}},
           "actions": {"total_actions": 20 * pc},
           "outcome": {"mode": MODE, "end_condition": "round_limit", "ended_on_round": 12, "team_result": team,
                       "winner_seats": winners,
                       "tie": (len(winners) > 1) if MODE == "competitive" else False, "winning_score": top,
                       "players_with_zero_score": sum(v == 0 for v in scores.values()),
                       "players_reaching_zero_lives": r.randint(0, pc)},
           "players": [{"seat": s, "role": ROLES[s - 1], "score": scores[s]} for s in scores],
           "game_stats": [], "unmatched": [], "audit": {"illegal_actions": 0, "bound_violations": 0}}
    if purpose.startswith("D8"):
        rec.update({"arm_id": arm, "arm_kind": kind, "focal_seat": focal})
    return rec


ledger, per_file = [], {k: [] for k in ["per_game_D04", "per_game_D05", "per_game_D07", "per_game_D08", "per_game_other"]}
events = {k: [] for k in ["events_D04", "events_D05", "events_D07", "events_D08"]}


def batch(purpose, eng, pc, s0, n, pfile, efile, arm=None, kind=None, focal_fn=None, boost=0, logged=None, rerun="new"):
    recs = []
    for i in range(n):
        seed = s0 + i
        focal = focal_fn(seed) if focal_fn else None
        rec = game(purpose, eng, pc, seed, arm, kind, focal, boost)
        k = rec.pop("_k")
        recs.append(rec)
        per_file[pfile].append(rec)
        if efile and (logged is None or i < logged):
            events[efile].append({"game": rec["game_id"], "seq": 0, "type": "set_up", "action_id": None, "dur": {"row": "set_up", "n": 1}})
            for a in range(k):
                events[efile].append({"game": rec["game_id"], "seq": 1 + 2 * a, "type": "move", "action_id": a + 1, "dur": {"row": "move", "n": 1}})
                events[efile].append({"game": rec["game_id"], "seq": 2 + 2 * a, "type": "move_step", "action_id": a + 1, "dur": {"row": "move_step", "n": STEPS}})
            events[efile].append({"game": rec["game_id"], "seq": 1 + 2 * k, "type": "game_end", "action_id": None, "dur": {"row": None, "n": 0}})
    ledger.append({"purpose": purpose, "arm_id": arm, "arm_kind": kind, "engine_version": eng, "player_count": pc,
                   "seed_from": s0, "seed_to": s0 + n - 1, "games": n, "new_or_rerun": rerun,
                   "per_game_file": pfile + ".jsonl.zip", "events_file": efile + ".jsonl.zip" if efile else None,
                   "logged_games": (n if logged is None else min(n, logged)) if efile else 0, "note": None})
    return recs


batch("test", "v0", 4, 1, 20, "per_game_other", None)
d4l = batch("D4_logged", "v1", 4, 400000, 1, "per_game_D04", "events_D04")
d4 = batch("D4_batch", "v1", 4, 400001, 1000, "per_game_D04", "events_D04")
d5 = {pc: batch("D5", "v2", pc, 500001 + 10000 * pc, 1000, "per_game_D05", "events_D05") for pc in (2, 3, 4)}
d7 = batch("D7_rerun", "v2", 4, 400001, 1000, "per_game_D07", "events_D07", rerun="deterministic_rerun")
rot = lambda s: s % 4 + 1
base = batch("D8_baseline", "v2", 4, 600001, 400, "per_game_D08", "events_D08", arm="B0", logged=100)
arms = {"S1": batch("D8_arm", "v2", 4, 600001, 400, "per_game_D08", "events_D08", "S1", "strategy", rot, 2, logged=100),
        "S2": batch("D8_arm", "v2", 4, 600001, 400, "per_game_D08", "events_D08", "S2", "strategy", rot, 0, logged=100),
        "R-I3a": batch("D8_arm", "v2", 4, 600001, 400, "per_game_D08", "events_D08", "R-I3a", "reading", None, 1, logged=100)}


def write_zip(name, recs):
    with zipfile.ZipFile(os.path.join(out, name + ".jsonl.zip"), "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        with zf.open(name + ".jsonl", "w", force_zip64=True) as f:
            for r in recs:
                f.write((json.dumps(r, allow_nan=False) + "\n").encode())


for k, v in per_file.items():
    write_zip(k, v)
for k, v in events.items():
    write_zip(k, v)

P = lambda xs, q: float(np.percentile(xs, q))


def ws(recs, pc):
    t = {s: 0.0 for s in range(1, pc + 1)}
    for r in recs:
        w = r["outcome"]["winner_seats"]
        for s in w:
            t[s] += 1 / len(w)
    return t


playtime, outcome, groups, focus_pc = [], [], [], []
for pc, recs in d5.items():
    typ = [r["time"]["play_min"]["typical"] for r in recs]
    smp = [r["time"]["play_min"]["sampled"] for r in recs]
    tgt = TARGET[str(pc)]; lo, hi = tgt * .8, tgt * 1.2
    q = lambda xs: {"p10": P(xs, 10), "median": P(xs, 50), "p90": P(xs, 90), "mean": float(np.mean(xs))}
    frac = lambda xs, f: sum(f(x) for x in xs) / len(xs)
    med = P(typ, 50)
    playtime.append({"player_count": pc, "engine_version": "v2", "n_games": len(recs),
                     "play_min": {"typical": q(typ), "sampled": q(smp), "low_median": med * .5, "high_median": med * 2},
                     "session_min_typical_median": med + 8, "round_min_typical_mean": float(np.mean(typ)) / 12,
                     "turn_min_typical_mean": float(np.mean(typ)) / 12 / pc, "rounds_played_median": 12.0,
                     "turns_played_median": float(12 * pc),
                     "p_play_exceeds_target": {"typical": frac(typ, lambda x: x > tgt), "sampled": frac(smp, lambda x: x > tgt)},
                     "p_play_within_tolerance": {"typical": frac(typ, lambda x: lo <= x <= hi), "sampled": frac(smp, lambda x: lo <= x <= hi)},
                     "p_play_below_tolerance": {"typical": frac(typ, lambda x: x < lo), "sampled": frac(smp, lambda x: x < lo)},
                     "verdict": "short" if med < lo else ("long" if med > hi else "on_target")})
    sc = [p["score"] for r in recs for p in r["players"]]
    w = ws(recs, pc)
    team = sum(r["outcome"]["team_result"] == "win" for r in recs) / len(recs)
    outcome.append({"player_count": pc, "engine_version": "v2", "n_games": len(recs), "mode": MODE,
                    "team_success_share": {"share": team if MODE == "cooperative" else None, "ci95": [0, 1]},
                    "score_per_player_mean": float(np.mean(sc)),
                    "winning_score_median": P([r["outcome"]["winning_score"] for r in recs], 50),
                    "tie_share": sum(r["outcome"]["tie"] for r in recs) / len(recs),
                    "players_with_zero_score_per_game_mean": float(np.mean([r["outcome"]["players_with_zero_score"] for r in recs])),
                    "players_reaching_zero_lives_per_game_mean": float(np.mean([r["outcome"]["players_reaching_zero_lives"] for r in recs])),
                    "win_share_by_seat": [{"seat": s, "share": w[s] / len(recs), "ci95": [0, 1], "fair": 1 / pc} for s in w] if MODE == "competitive" else [],
                    "win_share_by_role": [{"role": ROLES[s - 1], "share": w[s] / len(recs), "ci95": [0, 1], "fair": 1 / pc} for s in w] if MODE == "competitive" else []})
    opts = [{"option": ROLES[s - 1], "outcome": (w[s] / len(recs)) if MODE == "competitive" else team, "ci95": [0, 1],
             "use_per_player_turn": 0.2, "idle_share": 0.1} for s in w]
    vals = [o["outcome"] for o in opts]
    focus_pc.append({"player_count": pc, "options": opts, "spread": max(vals) - min(vals)})
    groups.append({"player_count": pc, "engine_version": "v2", "purpose": "D5", "n_games": len(recs),
                   "play_min": {"typical": q(typ), "sampled": q(smp)}, "stats": []})

bseed = {r["seed"]: r for r in base}
d8 = []
for aid, recs in arms.items():
    kind = recs[0]["arm_kind"]
    if kind == "strategy":
        d = [r["players"][r["focal_seat"] - 1]["score"] - bseed[r["seed"]]["players"][r["focal_seat"] - 1]["score"] for r in recs]
        def wv(r, s):
            if MODE == "cooperative":
                return float(r["outcome"]["team_result"] == "win")
            w = r["outcome"]["winner_seats"]; return 1 / len(w) if s in w else 0
        wd = [(wv(r, r["focal_seat"]) - wv(bseed[r["seed"]], r["focal_seat"])) * 100 for r in recs]
    else:
        d = [np.mean([p["score"] for p in r["players"]]) - np.mean([p["score"] for p in bseed[r["seed"]]["players"]]) for r in recs]
        wd = None
    m = float(np.mean(d)); se = float(np.std(d, ddof=1) / np.sqrt(len(d)))
    ci = [m - 1.96 * se, m + 1.96 * se]
    d8.append({"arm_id": aid, "arm_kind": kind, "description": "test arm", "reading_id": "I3" if kind == "reading" else None,
               "focal": "rotating_seat" if kind == "strategy" else "all", "n_pairs": len(recs), "engine_version": "v2",
               "score_diff": {"mean": m, "ci95": ci},
               "win_diff_pp": {"mean": float(np.mean(wd)), "ci95": [0, 0]} if wd else {"mean": None, "ci95": None},
               "opponent_score_diff": {"mean": 0, "ci95": [0, 0]}, "playtime_diff_min": {"mean": 0, "ci95": [0, 0]},
               "significant": not (ci[0] <= 0 <= ci[1])})

if path == "extraction":
    run = {"game": "Lethal Dungeon", "d1_source": "extraction", "rulebook_file": "01_rules.txt",
           "upstream_files": ["01_rules.txt", "01_components.json"], "user_input_files": [], "game_material_files": []}
else:
    run = {"game": "Lethal Dungeon", "d1_source": "raw", "rulebook_file": "rulebook.pdf",
           "upstream_files": [], "user_input_files": [], "game_material_files": ["rulebook.pdf", "preview.webp"]}
table_rows = [{"id": rid, "category": cat, "per": per, "in_play": inplay, "low_s": lo, "typical_s": ty, "high_s": hi,
               "value_source": "assumed", "assumed": {"low_s": lo, "typical_s": ty, "high_s": hi}, "note": None}
              for rid, (lo, ty, hi, cat, inplay, per) in DUR.items()]
dtable = {"schema": "duration_table_v1", "timings_file": None, "rows": table_rows,
          "scale_factors": {"low": 1.0, "typical": 1.0, "high": 1.0}}

d4typ = [r["time"]["play_min"]["typical"] for r in d4]
headline = {"schema": "headline_v2", "game": "Lethal Dungeon", "rulebook_file": run["rulebook_file"],
            "player_counts": [2, 3, 4], "targets": {"basis": "play", "tolerance_pct": TOL, "min_by_player_count": TARGET},
            "headline_clock": "typical", "engine_version_final": "v2", "games_executed": sum(e["games"] for e in ledger),
            "duration_table": [{"event_type": r["id"], "category": r["category"], "low_s": r["low_s"], "typical_s": r["typical_s"],
                                "high_s": r["high_s"], "value_source": r["value_source"], "tag": "G"} for r in table_rows],
            "timings": {"timings_file": None, "categories_provided": [], "categories_inferred": [],
                        "categories_assumed": sorted({r["category"] for r in table_rows}),
                        "scale_factors": {"low": 1.0, "typical": 1.0, "high": 1.0}, "assumed_share_of_play_time": 1.0, "sessions": []},
            "playtime": playtime, "outcome": outcome,
            "focus_items": [{"name": "player_card", "category": "cards", "chosen_by": "run", "reason": "every turn uses the card [L]",
                             "outcome_metric": "win_share" if MODE == "competitive" else "team_success", "by_player_count": focus_pc}],
            "d4_single_game": {"seed": 400000, "play_min_typical": d4l[0]["time"]["play_min"]["typical"],
                               "batch_play_min_typical": {"p10": P(d4typ, 10), "median": P(d4typ, 50), "p90": P(d4typ, 90)},
                               "representative": True, "reason": "inside the p10–p90 band"},
            "d7_audit": {"engine_before": "v1", "engine_after": "v2", "gaps_found": 2, "gaps_fixed": 1, "gaps_unfixed": 1,
                         "rerun_play_min_typical_median": {"before": P(d4typ, 50), "after": P([r["time"]["play_min"]["typical"] for r in d7], 50)}},
            "interpretations": [{"id": "I3", "topic": "bonus", "reading": "once", "tag": "L", "tested_arm_ids": ["R-I3a"]}],
            "d8_arms": d8,
            "designer_questions": [{"rank": 1, "question": "Once or per exit?", "measured_difference": "+x", "source_arm_ids": ["R-I3a"]}],
            "untested": []}
summary = {"schema_version": "0.6", "groups": groups, "strategies": [{"id": a["arm_id"]} for a in d8], "unmatched": [], "flags": []}

open(os.path.join(out, "headline.json"), "w").write(json.dumps(headline, indent=1, allow_nan=False))
open(os.path.join(out, "summary.json"), "w").write(json.dumps(summary, indent=1, allow_nan=False))
open(os.path.join(out, "D01_board_layout.json"), "w").write("null")
open(os.path.join(out, "D03_duration_table.json"), "w").write(json.dumps(dtable, indent=1, allow_nan=False))
for f in ["D01_rules_dossier.md", "D03_playtime_model.md", "D04_single_vs_batch.md", "D05_playtime.md",
          "D06_game_statistics.md", "D07_self_audit.md", "D08_exploits_and_rulebook_audit.md", "D09_limitations.md",
          "D10_designer_questions.md", "D11_data_needed.md"]:
    open(os.path.join(out, f), "w").write(f"# {f}\nplaceholder\n")
open(os.path.join(out, "REPORT.md"), "w").write("# Report\n" + "word " * 500 + "\n")
for f in ["D02_engine_v1.py", "D02_engine_v2.py", "D02_run.py"]:
    open(os.path.join(out, f), "w").write("print('engine')\n")

manifest = {"schema_version": "0.8", "run": run,
            "config": {"target_min": TARGET, "target_basis": "play", "tolerance_pct": TOL, "player_counts": [2, 3, 4], "headline_clock": "typical"},
            "engine_versions": [{"id": "v0", "change_note": "dev"}, {"id": "v1", "change_note": "first"}, {"id": "v2", "change_note": "D7 fixes"}],
            "simulation_ledger": ledger,
            "totals": {"games_executed": sum(e["games"] for e in ledger), "games_new": sum(e["games"] for e in ledger if e["new_or_rerun"] == "new")},
            "flags": [],
            "vocabulary": {"roles": {r: "item" for r in ROLES}, "action_types": {"move": "a move", "move_step": "one step of a move"},
                           "phases": {"set_up": "preparing the game"}, "cards": {"player_card": "the card each player holds"},
                           "readings": {"I3": "exit bonus once per game", "R-I3a": "exit bonus on every exit"},
                           "strategies": {"S1": "test strategy one", "S2": "test strategy two"}}}
files = []
for name in sorted(os.listdir(out)):
    p = os.path.join(out, name)
    rec = None
    if name.endswith(".jsonl.zip"):
        with zipfile.ZipFile(p) as zf:
            with zf.open(name[:-4]) as fh:
                rec = sum(1 for line in fh if line.strip())
    files.append({"name": name, "bytes": os.path.getsize(p), "sha256": hashlib.sha256(open(p, "rb").read()).hexdigest(), "records": rec})
manifest["files"] = files
open(os.path.join(out, "run_manifest.json"), "w").write(json.dumps(manifest, indent=1, allow_nan=False))
print("fake run written to", out, "path", path, "games", manifest["totals"]["games_executed"])
