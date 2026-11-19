"""Break a copy of the compliant fake run in one way at a time and check the validator catches it.
v1.3 (contract v2.2): adds d1_source, the id exemption in readings/strategies, and RUNLOG files_failed.
v1.4 (contract v2.3): duration table and event durations, D11, outcome modes, focus items, test-id repeats,
per-engine D8 baselines, operator files and archives as game material.
usage: python mutation_tests.py <good_competitive_out> <check_outputs.py> <good_cooperative_out>"""
import json, os, shutil, subprocess, sys, tempfile, zipfile

good, checker, good_coop = sys.argv[1], sys.argv[2], sys.argv[3]
ORDER = ["REPORT.md", "headline.json", "summary.json", "run_manifest.json", "D01_rules_dossier.md",
         "D01_board_layout.json", "D02_engine_v1.py", "D02_engine_v2.py", "D02_run.py", "D03_playtime_model.md",
         "D03_duration_table.json", "D04_single_vs_batch.md", "D05_playtime.md", "D06_game_statistics.md",
         "D07_self_audit.md", "D08_exploits_and_rulebook_audit.md", "D09_limitations.md", "D10_designer_questions.md",
         "D11_data_needed.md",
         "per_game_D04.jsonl.zip", "per_game_D05.jsonl.zip", "per_game_D07.jsonl.zip", "per_game_D08.jsonl.zip",
         "per_game_other.jsonl.zip", "events_D04.jsonl.zip", "events_D05.jsonl.zip", "events_D07.jsonl.zip",
         "events_D08.jsonl.zip"]


def runlog(games, failed="none"):
    return (f"RUNLOG: phases=10 interpretations=1 games_simulated={games} files_failed={failed} "
            f"files_written={','.join(ORDER)}")


def run(folder, *extra):
    p = subprocess.run([sys.executable, "-I", checker, folder, "--json", os.path.join(os.path.dirname(folder), "r.json"), *extra],
                       capture_output=True, text=True)
    rep = json.load(open(os.path.join(os.path.dirname(folder), "r.json")))
    return p.returncode, {(i["id"], i["level"]) for i in rep["items"]}, rep


def edit_json(path, fn):
    d = json.load(open(path)); fn(d); open(path, "w").write(json.dumps(d))


def rezip(path, member, lines):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(member, "".join(lines))


def read_lines(path):
    with zipfile.ZipFile(path) as zf:
        return zf.read(zf.namelist()[0]).decode().splitlines(keepends=True)


games = json.load(open(os.path.join(good, "run_manifest.json")))["totals"]["games_executed"]
MAN = lambda o: os.path.join(o, "run_manifest.json")
cases = []
def case(name, expect, *extra, base=None):
    """expect = check id that must FAIL, or None = the change is allowed and the run must still pass."""
    def deco(fn):
        cases.append((name, expect, fn, extra, base)); return fn
    return deco


def edit_zip(path, fn):
    lines = read_lines(path)
    out = [json.dumps(r) + "\n" for r in (fn(json.loads(l)) for l in lines) if r is not None]
    rezip(path, os.path.basename(path)[:-4], out)


# ---- carried over from v1.2 (25 cases)
@case("browser duplicate file", "F3")
def _(o): shutil.copy(os.path.join(o, "REPORT.md"), os.path.join(o, "REPORT (1).md"))

@case("missing file", "F2")
def _(o): os.remove(os.path.join(o, "D09_limitations.md"))

@case("subfolder", "F1")
def _(o): os.mkdir(os.path.join(o, "extra"))

@case("tar archive present", "F3")
def _(o): open(os.path.join(o, "data.tar.gz"), "wb").write(b"x")

@case("zip with two members", "Z2")
def _(o):
    p = os.path.join(o, "per_game_D07.jsonl.zip"); lines = read_lines(p)
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("per_game_D07.jsonl", "".join(lines)); zf.writestr("notes.txt", "x")

@case("zip member inside a folder", "Z2")
def _(o):
    p = os.path.join(o, "per_game_D07.jsonl.zip"); lines = read_lines(p)
    rezip(p, "out/per_game_D07.jsonl", lines)

@case("truncated zip (bad download)", "Z1")
def _(o):
    p = os.path.join(o, "events_D07.jsonl.zip"); b = open(p, "rb").read(); open(p, "wb").write(b[: len(b) // 2])

@case("NaN in summary.json", "J3")
def _(o):
    p = os.path.join(o, "summary.json"); s = open(p).read().replace('"flags": []', '"flags": NaN'); open(p, "w").write(s)

@case("ledger game count off by one", "P2")
def _(o): edit_json(MAN(o), lambda d: d["simulation_ledger"][2].__setitem__("games", 999))

@case("ledger has an extra key", "M2")
def _(o): edit_json(MAN(o), lambda d: d["simulation_ledger"][0].__setitem__("events_log", None))

@case("non-enum purpose in ledger", "M3")
def _(o): edit_json(MAN(o), lambda d: d["simulation_ledger"][0].__setitem__("purpose", "D8_variant"))

@case("condition leaked into manifest", "M1")
def _(o): edit_json(MAN(o), lambda d: d["run"].__setitem__("condition", "SINGLE"))

@case("file changed after manifest (hash)", "M10")
def _(o): open(os.path.join(o, "D05_playtime.md"), "a").write("late edit\n")

@case("engine file missing", "M5")
def _(o): os.remove(os.path.join(o, "D02_engine_v2.py"))

@case("headline median wrong", "H4")
def _(o): edit_json(os.path.join(o, "headline.json"), lambda d: d["playtime"][2]["play_min"]["typical"].__setitem__("median", 99))

@case("headline seat share wrong", "H4")
def _(o): edit_json(os.path.join(o, "headline.json"), lambda d: d["outcome"][0]["win_share_by_seat"][0].__setitem__("share", 0.9))

@case("headline extra key", "H1")
def _(o): edit_json(os.path.join(o, "headline.json"), lambda d: d.__setitem__("my_extra", 1))

@case("D8 score diff wrong", "H7")
def _(o): edit_json(os.path.join(o, "headline.json"), lambda d: d["d8_arms"][0]["score_diff"].__setitem__("mean", 5.0))

@case("significant flag contradicts CI", "H7")
def _(o): edit_json(os.path.join(o, "headline.json"), lambda d: d["d8_arms"][1].__setitem__("significant", not d["d8_arms"][1]["significant"]))

@case("six designer questions", "H8")
def _(o): edit_json(os.path.join(o, "headline.json"), lambda d: d.__setitem__("designer_questions", [dict(d["designer_questions"][0], rank=i) for i in range(1, 7)]))

@case("bad end_condition in records", "P1")
def _(o):
    p = os.path.join(o, "per_game_other.jsonl.zip"); lines = read_lines(p)
    lines = [l.replace('"round_limit"', '"round_deck_empty"') for l in lines]; rezip(p, "per_game_other.jsonl", lines)

@case("events missing for a D5 game", "E3")
def _(o):
    p = os.path.join(o, "events_D05.jsonl.zip"); lines = read_lines(p)
    first = json.loads(lines[0])["game"]
    rezip(p, "events_D05.jsonl", [l for l in lines if json.loads(l)["game"] != first])

@case("D8 arm missing one seed", "S1")
def _(o):
    p = os.path.join(o, "per_game_D08.jsonl.zip"); lines = read_lines(p)
    lines = [l for l in lines if not ('"S2"' in l and '"seed": 600400' in l)]
    rezip(p, "per_game_D08.jsonl", lines)

@case("report over 1,200 words", "T4")
def _(o): open(os.path.join(o, "REPORT.md"), "w").write("w " * 1300)

@case("RUNLOG game count wrong", "L1", "--runlog", runlog(1))
def _(o): pass

# ---- new in v1.3
@case("d1_source missing", "M1c")
def _(o): edit_json(MAN(o), lambda d: d["run"].pop("d1_source"))

@case("d1_source not an allowed value", "M1c")
def _(o): edit_json(MAN(o), lambda d: d["run"].__setitem__("d1_source", "upstream"))

@case("extraction path without upstream files", "M1c")
def _(o): edit_json(MAN(o), lambda d: (d["run"].__setitem__("d1_source", "extraction"), d["run"].__setitem__("upstream_files", [])))

@case("raw path with empty game material", "M1b")
def _(o): edit_json(MAN(o), lambda d: (d["run"].__setitem__("d1_source", "raw"), d["run"].__setitem__("upstream_files", []),
                                        d["run"].__setitem__("game_material_files", [])))

@case("01 file listed as game material", "M1b")
def _(o): edit_json(MAN(o), lambda d: d["run"].__setitem__("game_material_files", ["01_rules.txt", "preview.webp"]))

@case("upper-case name outside readings/strategies", "M7")
def _(o): edit_json(MAN(o), lambda d: d["vocabulary"]["roles"].__setitem__("Shovel", "item"))

@case("id-style key in a category without the exemption", "M7")
def _(o): edit_json(MAN(o), lambda d: d["vocabulary"]["roles"].__setitem__("I3", "not a role"))

@case("malformed reading id", "M7")
def _(o): edit_json(MAN(o), lambda d: d["vocabulary"]["readings"].__setitem__("R-i3a", "lower-case i"))

@case("RUNLOG reports an undelivered file", "L3", "--runlog", runlog(None, "events_D08.jsonl.zip"))
def _(o): pass

@case("RUNLOG without files_failed", "L3", "--runlog", runlog(None).replace(" files_failed=none", ""))
def _(o): pass

# ---- new in v1.4
@case("D11 missing", "F2")
def _(o): os.remove(os.path.join(o, "D11_data_needed.md"))

@case("duration table missing", "F2")
def _(o): os.remove(os.path.join(o, "D03_duration_table.json"))

@case("PDF added to out (client README)", "F3")
def _(o): open(os.path.join(o, "README.pdf"), "wb").write(b"%PDF")

@case("duration row with unknown category", "D1")
def _(o): edit_json(os.path.join(o, "D03_duration_table.json"), lambda d: d["rows"][1].__setitem__("category", "walking"))

@case("headline duration value differs from table", "D2")
def _(o): edit_json(os.path.join(o, "headline.json"), lambda d: d["duration_table"][1].__setitem__("typical_s", 11))

@case("timings summary lists a category as provided", "D3")
def _(o): edit_json(os.path.join(o, "headline.json"), lambda d: d["timings"].__setitem__("categories_provided", ["move"]))

@case("events without dur", "D4")
def _(o):
    def f(r):
        r.pop("dur", None); return r
    edit_zip(os.path.join(o, "events_D05.jsonl.zip"), f)

@case("play_min not reproducible from events", "D4")
def _(o):
    def f(r):
        if r["game_id"] == "D5/v2/2p/520001":
            r["time"]["play_min"]["typical"] += 1.0
        return r
    edit_zip(os.path.join(o, "per_game_D05.jsonl.zip"), f)

@case("duplicate game_id in a main batch", "P1")
def _(o):
    p = os.path.join(o, "per_game_D07.jsonl.zip"); lines = read_lines(p); rezip(p, "per_game_D07.jsonl", lines + lines[:1])

@case("repeated test ids in per_game_other are allowed", None, "--skip-events")
def _(o):
    p = os.path.join(o, "per_game_other.jsonl.zip"); lines = read_lines(p); rezip(p, "per_game_other.jsonl", lines + lines)
    def f(d):
        d["simulation_ledger"][0]["games"] *= 2; d["totals"]["games_executed"] += 20; d["totals"]["games_new"] += 20
        import hashlib
        for x in d["files"]:
            if x["name"] == "per_game_other.jsonl.zip":
                b = open(p, "rb").read(); x.update(bytes=len(b), sha256=hashlib.sha256(b).hexdigest(), records=len(lines) * 2)
    edit_json(MAN(o), f)
    edit_json(os.path.join(o, "headline.json"), lambda d: d.__setitem__("games_executed", d["games_executed"] + 20))
    b = open(os.path.join(o, "headline.json"), "rb").read()
    def g(d):
        import hashlib
        for x in d["files"]:
            if x["name"] == "headline.json":
                x.update(bytes=len(b), sha256=hashlib.sha256(b).hexdigest())
    edit_json(MAN(o), g)

@case("ledger claims more test games than recorded", "P2")
def _(o): edit_json(MAN(o), lambda d: d["simulation_ledger"][0].__setitem__("games", 25))

@case("D8 arm on an engine without its own baseline", "S1")
def _(o):
    def f(r):
        if r.get("arm_id") == "S2":
            r["engine_version"] = "v1"; r["game_id"] = r["game_id"].replace("/v2/", "/v1/")
        return r
    edit_zip(os.path.join(o, "per_game_D08.jsonl.zip"), f)

@case("outcome.mode missing in records", "P1")
def _(o):
    def f(r):
        r["outcome"].pop("mode"); return r
    edit_zip(os.path.join(o, "per_game_D04.jsonl.zip"), f)

@case("headline schema still v1", "H1b")
def _(o): edit_json(os.path.join(o, "headline.json"), lambda d: d.__setitem__("schema", "headline_v1"))

@case("four focus items", "H9")
def _(o): edit_json(os.path.join(o, "headline.json"), lambda d: d.__setitem__("focus_items", d["focus_items"] * 4))

@case("focus spread wrong", "H9")
def _(o): edit_json(os.path.join(o, "headline.json"), lambda d: d["focus_items"][0]["by_player_count"][0].__setitem__("spread", 0.9))

@case("focus metric does not fit the mode", "H9")
def _(o): edit_json(os.path.join(o, "headline.json"), lambda d: d["focus_items"][0].__setitem__("outcome_metric", "mean_score"))

@case("RUN-END uploaded as game material", "M1b")
def _(o): edit_json(MAN(o), lambda d: d["run"]["game_material_files"].append("3d54339b-RUN-END.md"))

@case("game material left inside a zip", "M1b")
def _(o): edit_json(MAN(o), lambda d: d["run"].__setitem__("game_material_files", ["Bestanden.zip", "Bestanden.zip/rules.pdf"]))

@case("unknown 01 user input", "M1c")
def _(o): edit_json(MAN(o), lambda d: d["run"].__setitem__("user_input_files", ["01_notes.txt"]))

@case("cooperative: team win but no winner seats", "P1", base="coop")
def _(o):
    def f(r):
        if r["outcome"]["team_result"] == "win":
            r["outcome"]["winner_seats"] = []
        return r
    edit_zip(os.path.join(o, "per_game_D04.jsonl.zip"), f)

@case("cooperative: seat win shares reported", "H4", base="coop")
def _(o): edit_json(os.path.join(o, "headline.json"), lambda d: d["outcome"][0].__setitem__("win_share_by_seat", [{"seat": 1, "share": 0.3}]))

@case("cooperative: team success wrong", "H4", base="coop")
def _(o): edit_json(os.path.join(o, "headline.json"), lambda d: d["outcome"][1]["team_success_share"].__setitem__("share", 0.99))


tmp = tempfile.mkdtemp()
ok_all = True
# positive controls: the untouched runs with a correct RUNLOG must pass
for label, src in (("competitive", good), ("cooperative", good_coop)):
    d = os.path.join(tmp, "control_" + label, "out"); shutil.copytree(src, d)
    g_ = json.load(open(os.path.join(src, "run_manifest.json")))["totals"]["games_executed"]
    rc, items, rep = run(d, "--runlog", runlog(g_))
    fails = sorted({i for i, l in items if l == "FAIL"})
    print(f"{'PASSED' if rc == 0 and not fails else 'BROKEN'}  control ({label}, correct RUNLOG)  exit={rc} fails={fails}")
    ok_all &= rc == 0 and not fails
for name, expect, fn, extra, base in cases:
    extra = tuple(x.replace("games_simulated=None", f"games_simulated={games}") for x in extra)
    d = os.path.join(tmp, name.replace(" ", "_").replace(",", "").replace("/", "_").replace(":", ""), "out")
    shutil.copytree(good_coop if base == "coop" else good, d)
    fn(d)
    rc, items, rep = run(d, *extra)
    if expect is None:
        fails = sorted({i for i, l in items if l == "FAIL"})
        status = "allowed" if rc == 0 and not fails else "MISSED"
        ok_all &= status == "allowed"
        print(f"{status:7} {name:52} expected PASS exit={rc} fails={fails}")
        continue
    hit = (expect, "FAIL") in items or (expect == "M1" and ("M1", "WARN") in items)
    good_rc = rc == 1 or (expect == "M1" and rc == 0)
    status = "caught" if hit and good_rc else "MISSED"
    ok_all &= status == "caught"
    fails = sorted({i for i, l in items if l == "FAIL"})
    print(f"{status:7} {name:52} expected {expect:4} exit={rc} fails={fails}")
print(f"\n{len(cases)} breakages. " + ("ALL CAUGHT" if ok_all else "SOME MISSED"))
