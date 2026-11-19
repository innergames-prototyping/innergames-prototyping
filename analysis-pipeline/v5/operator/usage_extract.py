#!/usr/bin/env python3
"""Per-run token usage from Claude session transcripts (.jsonl). v4.1, 2026-10-26.

Standard library only. Written for Project Pipeline; provenance and validation are in
AB_usage_extract_explained.md.

    python usage_extract.py runs/*.jsonl --csv usage.csv --prices IN,OUT,CREAD,CW5M,CW1H

Each transcript is one run, exported with the RUN-END prompt in AB_usage_extract_explained.md:
  - run_id   comes from the {"type": "run-meta"} line that prompt appends (falls back to
             the file name, with a warning).
  - cut-off  everything from the human message containing "RUN-END" onward is ignored, so
             the export step itself is not billed to the run.

Reports, per run:
  measured_*  summed from each assistant message's `usage`, de-duplicated by message id
  reported_*  the last `cost-state` row before RUN-END (first-party running total).
              These snapshots are periodic and can lag badly in short runs: see
              reported_lag_msgs (assistant messages after the last snapshot). Publish
              measured_* priced with --prices; use reported_* only as a cross-check.

active_minutes = model working time: from each human message to the model's last output
before the next one. Includes tool execution (running simulations); excludes human replies.
Tool calls that could read outside material (skills, memory, project docs, past chats, the
user's computer) are listed in contamination_calls and raise a warning.
v4.1: skills_listed counts the skills the run could load (from the skill listing it was shown);
skills_flagged names any listed skill matching SKILL_WATCH (game-analysis skills that carry
study knowledge) and raises a warning; models_list names every model that wrote a message.

Cache writes are split by lifetime (5-minute vs 1-hour), because they are priced differently.

Known limits: plain input tokens disagree between the two sources (unexplained); sub-agent sessions are
not in the transcript.
"""
import argparse
import csv
import datetime as dt
import glob
import json
import os
import re
import sys
from collections import Counter

MARKER = "RUN-END"
# Tool calls that could let a test chat read material outside its own run (project docs,
# memory, past chats, skills, the user's computer). Any hit flags the run as contaminated.
CONTAMINATION = re.compile(r"Skill|memory|Projects|conversation_search|recent_chats|"
                           r"read_conversation|remote-devices|device_", re.I)


# Skills whose presence in a run's skill listing makes the run non-sterile, even if never called.
SKILL_WATCH = re.compile(r"boardgame|playtest|lethal|dungeon|critical-advisor", re.I)


def load(path):
    rows, bad = [], 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                bad += 1
    if bad:
        print(f"warn: {bad} unparsable line(s) skipped in {path}", file=sys.stderr)
    if not rows:
        sys.exit(f"error: no parsable JSON lines in {path}")
    return rows


def human_text(row):
    """Text typed by a person, or None if this user row is only tool results."""
    content = (row.get("message") or {}).get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [b.get("text", "") for b in content
                 if isinstance(b, dict) and b.get("type") in ("text", "image")]
        if parts:
            return " ".join(parts)
    return None


def scan(path):
    rows = load(path)
    name = os.path.basename(path)
    tok, tools, models = Counter(), Counter(), Counter()
    seen_ids, stamps = set(), []
    dup_rows = n_assistant = n_human = n_toolresult = 0
    cost_state, run_id, ended = None, None, False
    msgs_at_snapshot = 0
    tool_ids, tool_names = set(), Counter()
    timeline = []                              # (timestamp, is_human) in file order
    skills_listed = []

    for r in rows:
        kind = r.get("type")
        if kind == "run-meta":                 # appended after RUN-END, read regardless
            run_id = r.get("run_id")
            continue
        if ended:
            continue
        att = r.get("attachment") if kind == "attachment" else None
        if isinstance(att, dict) and att.get("type") == "skill_listing":
            text = att.get("content") or ""
            names = re.findall(r"(?m)^- ((?:[\w.-]+:)?[\w.-]+):\s", text)
            skills_listed = sorted(set(skills_listed) | {n.strip() for n in names})

        if kind == "user":
            text = human_text(r)
            if text is not None and MARKER in text:
                ended = True                   # export step starts here; stop counting
                continue
            if text is not None:
                n_human += 1
            else:
                n_toolresult += 1
        if r.get("timestamp"):
            stamps.append(r["timestamp"])
            if kind == "user":
                timeline.append((r["timestamp"], "human" if human_text(r) is not None else "work"))
            elif kind == "assistant":
                timeline.append((r["timestamp"], "work"))
        if kind == "assistant":
            # tool calls are spread over the duplicate rows, so collect them before de-dup
            for block in ((r.get("message") or {}).get("content") or []):
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    bid = block.get("id") or id(block)
                    if bid not in tool_ids:
                        tool_ids.add(bid)
                        tool_names[block.get("name") or "?"] += 1
        if kind == "cost-state":
            cost_state = r
            msgs_at_snapshot = n_assistant
        if kind != "assistant":
            continue

        msg = r.get("message") or {}
        mid = msg.get("id")
        if mid is not None and mid in seen_ids:
            dup_rows += 1                      # same message logged once per content block
            continue
        if mid is not None:
            seen_ids.add(mid)
        n_assistant += 1
        models[msg.get("model") or "unknown"] += 1
        u = msg.get("usage") or {}
        tok["input"] += u.get("input_tokens") or 0
        tok["output"] += u.get("output_tokens") or 0
        tok["cache_read"] += u.get("cache_read_input_tokens") or 0
        cw = u.get("cache_creation_input_tokens") or 0
        tok["cache_write"] += cw
        split = u.get("cache_creation")
        if isinstance(split, dict):
            tok["cache_write_5m"] += split.get("ephemeral_5m_input_tokens") or 0
            tok["cache_write_1h"] += split.get("ephemeral_1h_input_tokens") or 0
        else:
            tok["cache_write_unsplit"] += cw
        tok["thinking"] += (u.get("output_tokens_details") or {}).get("thinking_tokens") or 0
        for k, v in (u.get("server_tool_use") or {}).items():
            tools[k] += v or 0

    # --- run identity and integrity warnings --------------------------------------
    stem = os.path.splitext(name)[0]
    if run_id is None:
        print(f"warn: {name} has no run-meta line; using file name as run_id", file=sys.stderr)
        run_id = stem
    elif run_id != stem:
        print(f"warn: {name} run-meta says '{run_id}' but file is named '{stem}'",
              file=sys.stderr)
    if not ended:
        print(f"warn: {name} has no {MARKER} message; counting the whole file", file=sys.stderr)
    if n_assistant == 0:
        print(f"warn: {name} has no assistant messages before {MARKER} — wrong file?",
              file=sys.stderr)

    # active model time: for each human message, from that message to the model's last
    # output (assistant row or tool result) before the next human message. Waiting for the
    # human, and any rows logged while they type, fall outside these windows.
    def ts(x):
        return dt.datetime.fromisoformat(x.replace("Z", "+00:00"))
    active, turn_start, last_work = 0.0, None, None
    try:
        for t, what in timeline:
            if what == "human":
                if turn_start and last_work and last_work > turn_start:
                    active += (last_work - turn_start).total_seconds()
                turn_start, last_work = ts(t), None
            elif what == "work":
                last_work = ts(t)
        if turn_start and last_work and last_work > turn_start:
            active += (last_work - turn_start).total_seconds()
        active_minutes = round(active / 60, 1)
    except ValueError:
        active_minutes = "?"
        print(f"warn: {name} has unparsable timestamps; active_minutes unknown", file=sys.stderr)

    flagged = {n: c for n, c in tool_names.items() if CONTAMINATION.search(n)}
    if flagged:
        print(f"warn: {name} CONTAMINATION: called {flagged} — exclude or justify this run",
              file=sys.stderr)

    skills_flagged = [n for n in skills_listed if SKILL_WATCH.search(n)]
    if skills_flagged:
        print(f"warn: {name} NON-STERILE: the run could load {skills_flagged}", file=sys.stderr)

    span = ""
    if stamps:
        try:
            t0 = dt.datetime.fromisoformat(min(stamps).replace("Z", "+00:00"))
            t1 = dt.datetime.fromisoformat(max(stamps).replace("Z", "+00:00"))
            span = round((t1 - t0).total_seconds() / 60, 1)
        except ValueError:
            span = "?"

    row = {
        "run_id": run_id,
        "file": name,
        "run_end_found": ended,
        "model": models.most_common(1)[0][0] if models else "?",
        "models_seen": len(models),
        "assistant_msgs": n_assistant,
        "duplicate_rows_skipped": dup_rows,
        "human_turns": n_human,
        "tool_result_rows": n_toolresult,
        "active_minutes": active_minutes,
        "contamination_calls": ";".join(f"{n}x{c}" for n, c in sorted(flagged.items())),
        "tool_calls": sum(tool_names.values()),
        "web_search": tools.get("web_search_requests", 0),
        "web_fetch": tools.get("web_fetch_requests", 0),
        "span_minutes": span,
        "measured_input": tok["input"],
        "measured_output": tok["output"],
        "measured_thinking": tok["thinking"],
        "measured_cache_read": tok["cache_read"],
        "measured_cache_write": tok["cache_write"],
        "measured_cache_write_5m": tok["cache_write_5m"],
        "measured_cache_write_1h": tok["cache_write_1h"],
        "measured_cache_write_unsplit": tok["cache_write_unsplit"],
        "measured_total": tok["input"] + tok["output"] + tok["cache_read"] + tok["cache_write"],
    }

    if cost_state:
        mu = cost_state.get("modelUsage") or {}
        g = lambda k: sum((v.get(k) or 0) for v in mu.values())
        row.update({
            "reported_usd": round(cost_state.get("totalCostUSD") or 0, 4),
            "reported_input": g("inputTokens"),
            "reported_output": g("outputTokens"),
            "reported_cache_read": g("cacheReadInputTokens"),
            "reported_cache_write": g("cacheCreationInputTokens"),
            "api_minutes": round((cost_state.get("totalAPIDuration") or 0) / 60000, 1),
            "tool_minutes": round((cost_state.get("totalToolDuration") or 0) / 60000, 1),
            "reported_lag_msgs": n_assistant - msgs_at_snapshot,
        })
    else:
        print(f"warn: {name} has no cost-state rows; only measured_* available", file=sys.stderr)
        for k in ("reported_usd", "reported_input", "reported_output", "reported_cache_read",
                  "reported_cache_write", "api_minutes", "tool_minutes", "reported_lag_msgs"):
            row[k] = ""

    for field in ("output", "cache_read", "cache_write"):
        m, rep = row[f"measured_{field}"], row.get(f"reported_{field}")
        if isinstance(rep, int) and rep > 0 and abs(m - rep) / rep > 0.10:
            print(f"warn: {name} {field} differs by {abs(m - rep) / rep:.0%} "
                  f"(measured {m:,} vs reported {rep:,})", file=sys.stderr)
    row["skills_listed"] = len(skills_listed)
    row["skills_flagged"] = ";".join(skills_flagged)
    row["models_list"] = ";".join(f"{m}x{c}" for m, c in sorted(models.items()))
    if len(models) > 1:
        print(f"warn: {name} more than one model wrote messages: {dict(models)}", file=sys.stderr)
    return row


def main():
    ap = argparse.ArgumentParser(description="Token usage per Claude session transcript.")
    ap.add_argument("files", nargs="+", help="transcripts; wildcards work on Windows too")
    ap.add_argument("--csv", help="also write all rows to this CSV")
    ap.add_argument("--prices", help="USD per 1M tokens, five numbers: input,output,cache_read,"
                                     "cache_write_5m,cache_write_1h (adds priced_usd)")
    args = ap.parse_args()

    prices = None
    if args.prices:
        try:
            prices = [float(x) for x in args.prices.split(",")]
        except ValueError:
            sys.exit("error: --prices must be numbers, e.g. 4,20,0.2,5,8")
        if len(prices) != 5:
            sys.exit("error: --prices needs exactly 5 numbers: "
                     "input,output,cache_read,cache_write_5m,cache_write_1h")

    paths = []
    for pattern in args.files:              # Windows cmd does not expand *.jsonl itself
        hits = sorted(glob.glob(pattern))
        if not hits:
            print(f"warn: no file matches {pattern}", file=sys.stderr)
        paths.extend(hits)
    if not paths:
        sys.exit("error: no transcript files found")

    out, ids = [], Counter()
    for path in paths:
        row = scan(path)
        if prices:
            if row["measured_cache_write_unsplit"]:
                print(f"warn: {row['file']} has cache writes without a 5m/1h split; "
                      "priced_usd left blank rather than guessed", file=sys.stderr)
                row["priced_usd"] = ""
            else:
                row["priced_usd"] = round(sum(p * row[f"measured_{k}"] for p, k in zip(
                    prices, ["input", "output", "cache_read", "cache_write_5m",
                             "cache_write_1h"])) / 1e6, 4)
        ids[row["run_id"]] += 1
        out.append(row)
        print(f"\n{row['run_id']}  [{row['model']}]")
        for k, v in row.items():
            if k not in ("run_id", "model"):
                print(f"  {k:24s} {v:,}" if isinstance(v, int) and not isinstance(v, bool)
                      else f"  {k:24s} {v}")
    for rid, n in ids.items():
        if n > 1:
            print(f"warn: run_id '{rid}' appears in {n} files", file=sys.stderr)

    if args.csv:
        keys = list(out[0].keys())
        with open(args.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(out)
        print(f"\nwrote {args.csv} ({len(out)} row(s))")


if __name__ == "__main__":
    main()
