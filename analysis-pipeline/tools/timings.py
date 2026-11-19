"""timings.py: play time from event logs and a duration table (output contract v2.3, section 7).

Shared by check_outputs.py (does the run's own table reproduce its play times?) and
playtime_recompute.py (play times under measured human timings). Standard library only.
"""
import collections
import json
import zipfile

CATEGORIES = ["setup", "teardown", "turn_admin", "move", "draw_card", "resolve_card", "decide",
              "random_device", "token_handling", "board_change", "round_end", "scoring", "other"]
PER = {"event", "step", "player", "item"}
SOURCES = {"provided", "inferred", "assumed"}
CLOCKS = ("low", "typical", "high")
KEY = {"low": "low_s", "typical": "typical_s", "high": "high_s"}


def iter_jsonl_zip(path):
    """Yield one record per non-empty line of a single-member .jsonl.zip."""
    with zipfile.ZipFile(path) as zf:
        member = zf.namelist()[0]
        with zf.open(member) as fh:
            for raw in fh:
                if raw.strip():
                    yield json.loads(raw)


def load_table(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def table_problems(table, vocab_names=None):
    """Structural problems in a D03_duration_table.json object, as a list of strings."""
    out = []
    if not isinstance(table, dict) or table.get("schema") != "duration_table_v1":
        return ["not an object with schema 'duration_table_v1'"]
    rows = table.get("rows")
    if not isinstance(rows, list) or not rows:
        return ["rows missing or empty"]
    seen = set()
    for r in rows:
        rid = r.get("id")
        if rid in seen:
            out.append(f"duplicate row id '{rid}'")
        seen.add(rid)
        if vocab_names is not None and rid not in vocab_names:
            out.append(f"row '{rid}' is not a declared vocabulary name")
        if r.get("category") not in CATEGORIES:
            out.append(f"row '{rid}': category '{r.get('category')}' not in the fixed list")
        if r.get("per") not in PER:
            out.append(f"row '{rid}': per '{r.get('per')}'")
        if not isinstance(r.get("in_play"), bool):
            out.append(f"row '{rid}': in_play is not true/false")
        if r.get("value_source") not in SOURCES:
            out.append(f"row '{rid}': value_source '{r.get('value_source')}'")
        vals = [r.get("low_s"), r.get("typical_s"), r.get("high_s")]
        if not all(isinstance(v, (int, float)) and v >= 0 for v in vals) or not vals[0] <= vals[1] <= vals[2]:
            out.append(f"row '{rid}': need 0 <= low <= typical <= high, got {vals}")
        a = r.get("assumed") or {}
        if not all(isinstance(a.get(KEY[c]), (int, float)) for c in CLOCKS):
            out.append(f"row '{rid}': assumed values missing")
    sf = table.get("scale_factors") or {}
    if not all(isinstance(sf.get(c), (int, float)) for c in CLOCKS):
        out.append("scale_factors missing low/typical/high")
    return out


def rows_by_id(table):
    return {r["id"]: r for r in table["rows"]}


def game_clocks(events, rows):
    """Play minutes per clock for one game's events, and any unknown row ids charged."""
    tot = dict.fromkeys(CLOCKS, 0.0)
    unknown = set()
    for e in events:
        d = e.get("dur") or {}
        rid, n = d.get("row"), d.get("n", 1)
        if rid is None:
            continue
        r = rows.get(rid)
        if r is None:
            unknown.add(rid)
            continue
        if not r.get("in_play", True):
            continue
        for c in CLOCKS:
            tot[c] += (n or 0) * r[KEY[c]]
    return {c: tot[c] / 60 for c in CLOCKS}, unknown


def events_by_game(events_zip, keep=None):
    """Group an event file's records by game id. keep: optional set of game ids."""
    cur, buf = None, []
    for e in iter_jsonl_zip(events_zip):
        g = e.get("game")
        if keep is not None and g not in keep:
            continue
        if g != cur and buf:
            yield cur, buf
            buf = []
        cur = g
        buf.append(e)
    if buf:
        yield cur, buf


def category_stats(events_zip, table):
    """Per category, over all games in the file: total seconds per clock (assumed values) and
    number of occurrences (one player action, or one event without an action_id).
    Out-of-play rows (setup, teardown) are counted too; callers use in_play_categories() to keep
    them out of play-time shares and scale factors."""
    rows = rows_by_id(table)
    sec = {c: dict.fromkeys(CLOCKS, 0.0) for c in CATEGORIES}
    occ = collections.Counter()
    row_sec = collections.defaultdict(lambda: dict.fromkeys(CLOCKS, 0.0))
    seen_actions = set()
    for g, evs in events_by_game(events_zip):
        for e in evs:
            d = e.get("dur") or {}
            r = rows.get(d.get("row"))
            if r is None:
                continue
            n = d.get("n", 1) or 0
            cat = r["category"]
            a = r["assumed"]
            for c in CLOCKS:
                sec[cat][c] += n * a[KEY[c]]
                row_sec[r["id"]][c] += n * a[KEY[c]]
            aid = e.get("action_id")
            if aid is None:
                occ[cat] += 1
            elif (g, aid, cat) not in seen_actions:
                seen_actions.add((g, aid, cat))
                occ[cat] += 1
    return sec, occ, row_sec


def in_play_categories(table):
    """Categories with at least one in_play row."""
    return {r["category"] for r in table["rows"] if r.get("in_play", True)}


def apply_timings(table, timings, events_zip):
    """Return (new_table, report) after applying measured timings (contract section 7.3)."""
    prov = {}
    for cat, v in ((timings or {}).get("categories") or {}).items():
        if cat in CATEGORIES and isinstance(v, dict) and isinstance(v.get("min_s"), (int, float)) \
                and isinstance(v.get("max_s"), (int, float)):
            t = v.get("typical_s")
            if not isinstance(t, (int, float)):
                t = (v["min_s"] + v["max_s"]) / 2
            prov[cat] = {"low": v["min_s"], "typical": t, "high": v["max_s"]}
    sec, occ, _ = category_stats(events_zip, table)
    live = in_play_categories(table)
    new = json.loads(json.dumps(table))
    factor = {}                      # per provided category and clock: provided total / assumed total
    for cat, p in prov.items():
        factor[cat] = {}
        for c in CLOCKS:
            assumed_total = sec[cat][c]
            provided_total = p[c] * occ[cat]
            factor[cat][c] = (provided_total / assumed_total) if assumed_total > 0 else None
    # the inferred scale uses in-play categories only: setup and teardown say little about play speed
    num = {c: sum(prov[cat][c] * occ[cat] for cat in prov if cat in live) for c in CLOCKS}
    den = {c: sum(sec[cat][c] for cat in prov if cat in live) for c in CLOCKS}
    scale = {c: (num[c] / den[c]) if den[c] > 0 else 1.0 for c in CLOCKS}
    basis = [c for c in prov if c in live and sec[c]["typical"] > 0]
    for r in new["rows"]:
        a = r["assumed"]
        cat = r["category"]
        if cat in prov:
            # scale so the category's mean time per occurrence on the D5 games equals the measured value;
            # a one-row category charged once per occurrence simply takes the measured values
            f = factor[cat]
            if all(f[c] is not None for c in CLOCKS):
                vals = {c: a[KEY[c]] * f[c] for c in CLOCKS}
            else:                    # never charged in the D5 games: nothing to scale against
                vals = {c: prov[cat][c] for c in CLOCKS}
            src = "provided"
        else:
            vals = {c: a[KEY[c]] * scale[c] for c in CLOCKS}
            src = "inferred" if basis else "assumed"
        lo, ty, hi = sorted([vals["low"], vals["typical"], vals["high"]])
        r.update({"low_s": round(lo, 3), "typical_s": round(ty, 3), "high_s": round(hi, 3), "value_source": src})
    new["scale_factors"] = {c: round(scale[c], 4) for c in CLOCKS}
    new["timings_file"] = "01_timings.json" if prov else None
    total_typ = sum(sec[cat]["typical"] for cat in live) or 1.0
    shares = {cat: sec[cat]["typical"] / total_typ for cat in live if sec[cat]["typical"] > 0}
    cats = {r["category"] for r in new["rows"]}
    rest = sorted(c for c in cats if c not in prov)
    report = {"provided": sorted(prov), "inferred": rest if basis else [],
              "assumed": [] if basis else rest, "scale_factors": new["scale_factors"],
              "scale_basis": sorted(basis),
              "share_of_play_time_assumed_typical": {c: round(s, 4) for c, s in sorted(shares.items(), key=lambda x: -x[1])},
              "occurrences": dict(occ)}
    return new, report


def percentile(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)
