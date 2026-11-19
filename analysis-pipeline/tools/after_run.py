"""after_run.py: everything the operator does after a run, in one step, with no paths to type.

    python tools/after_run.py            # the newest run folder in ../runs
    python tools/after_run.py 14         # Run14_..., by number
    python tools/after_run.py Run15_KK   # by name, or part of it, or a full path

It never changes the files you downloaded. It writes <run>/_check/:
    out/                 clean copy of the outputs, browser renames (" (1)", "_2") undone
    check.txt/.json      check_outputs.py result
    usage.txt/.csv       usage_extract.py result (cost, time, contamination)
    RESEND.md            the RESEND message with the missing names filled in, ready to attach
    AFTER_RUN.md         one-page summary of all of the above
Exit code 0 = validator passed, 1 = something to look at.
"""
import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import zipfile
import sys
from contextlib import redirect_stdout, redirect_stderr

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import runfolder as RF                                         # noqa: E402
import check_outputs as CO                                     # noqa: E402
import usage_extract as UE                                     # noqa: E402

EXTS = (".jsonl.zip", ".json", ".md", ".py")
DUP = re.compile(r"^(.*?)(?: ?\(\d+\)|_\d+|-\d+)$")   # "x (1)" Windows/macOS, "x(1)" Linux Firefox, "x_2"
RUNLOG_RE = re.compile(r"RUNLOG:\s*phases=\d+[^\n]*")


def known(name):
    return name in CO.FIXED_FILES or bool(CO.ENGINE_FILE_RE.match(name))


def canonical(name):
    """The contract name a downloaded file stands for, or None."""
    if known(name):
        return name
    for ext in EXTS:
        if name.endswith(ext):
            m = DUP.match(name[: -len(ext)])
            if m and known(m.group(1) + ext):
                return m.group(1) + ext
    return None


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def build_out(run):
    """Copy the run's outputs into _check/out under their contract names. Returns a report dict."""
    out = RF.check_out(run)
    for d in (out, os.path.join(run, RF.CHECK_DIR, "bundles")):
        if os.path.isdir(d):
            shutil.rmtree(d)
    os.makedirs(out)
    groups, extras, operator = {}, [], []
    for name in sorted(os.listdir(run)):
        p = os.path.join(run, name)
        if name == RF.CHECK_DIR or not os.path.isfile(p) or name.startswith("."):
            continue                  # dotfiles: .DS_Store, macOS "._" copies on USB/exFAT drives
        if RF.OPERATOR_FILES.match(name):
            operator.append(name)
            continue
        c = canonical(name)
        if c is None:
            extras.append(name)
            continue
        groups.setdefault(c, []).append(p)
    # a browser "Download all" bundle: take the contract files out of it (names only, no paths)
    bundles, keep_extras = [], []
    for name in extras:
        p = os.path.join(run, name)
        if name.lower().endswith(".zip") and zipfile.is_zipfile(p):
            with zipfile.ZipFile(p) as zf:
                found = [m for m in zf.namelist() if not m.endswith("/") and canonical(os.path.basename(m))]
                if found:
                    tmp = os.path.join(run, RF.CHECK_DIR, "bundles", name)
                    os.makedirs(tmp, exist_ok=True)
                    for m in found:
                        dst = os.path.join(tmp, os.path.basename(m))
                        with zf.open(m) as src, open(dst, "wb") as fo:
                            shutil.copyfileobj(src, fo)
                        groups.setdefault(canonical(os.path.basename(m)), []).append(dst)
                    bundles.append(f"{name} ({len(found)} files)")
                    continue
        keep_extras.append(name)
    extras = keep_extras
    renamed, conflicts = [], []
    for c, paths in groups.items():
        pick = max(paths, key=os.path.getmtime)
        if len(paths) > 1:
            hashes = {sha(p) for p in paths}
            if len(hashes) > 1:
                conflicts.append(f"{c}: {len(paths)} different downloads ({', '.join(os.path.basename(p) for p in paths)}); "
                                 f"used the newest, {os.path.basename(pick)}")
        if os.path.basename(pick) != c:
            renamed.append(f"{os.path.basename(pick)} -> {c}")
        shutil.copy2(pick, os.path.join(out, c))
    for name in extras:                       # extras go in too, so the validator reports them (F3)
        shutil.copy2(os.path.join(run, name), os.path.join(out, name))
    return {"out": out, "files": sorted(groups), "renamed": renamed, "conflicts": conflicts,
            "extras": extras, "operator": operator, "own": RF.own_folders(run), "bundles": bundles}


def text_blocks(row):
    msg = row.get("message") or {}
    c = msg.get("content")
    if isinstance(c, str):
        yield c
    elif isinstance(c, list):
        for b in c:
            if isinstance(b, dict) and b.get("type") == "text":
                yield b.get("text") or ""


def find_runlog(tx):
    """The last RUNLOG line the run wrote itself (assistant text, not the instructions)."""
    last = None
    with open(tx, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "RUNLOG" not in line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("type") != "assistant":
                continue
            for t in text_blocks(row):
                for m in RUNLOG_RE.finditer(t):
                    if "<" not in m.group(0):
                        last = m.group(0).strip()
    return last


OPERATOR_MSG = re.compile(r"(RUN-END|RESEND|CONTINUE)\.md|^(RUN-END|RESEND|CONTINUE)\.", re.M)


APP_NOTICES = ("The files from earlier in this conversation", "[Attachment from earlier in this conversation")


def operator_messages(tx):
    """Every human message after the start, in order: [(message number, [operator files] or
    ['text: ...'])]. Message 1 is the start upload; app notices are skipped."""
    out, n = [], 0
    with open(tx, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if row.get("type") != "user":
                continue
            c = (row.get("message") or {}).get("content")
            texts = [c] if isinstance(c, str) else [b.get("text") or "" for b in c or []
                                                    if isinstance(b, dict) and b.get("type") == "text"]
            if not texts or all(not t.strip() for t in texts):
                continue                      # tool results are 'user' rows without text
            body = " ".join(texts)
            clean = re.sub(r"<system-reminder>.*?</system-reminder>", "", body, flags=re.S).strip()
            if not clean or clean.startswith(APP_NOTICES):
                continue
            n += 1
            hits = sorted({(m.group(1) or m.group(2)) for m in OPERATOR_MSG.finditer(clean)})
            if hits:
                out.append((n, hits))
            elif n > 1:
                typed = re.sub(r'@"[^"]*"', "", clean).strip()
                out.append((n, [f"text: '{typed[:70]}'" if typed else "attachments only (re-upload?)"]))
    return out


def files_written(runlog):
    m = re.search(r"files_written=\[?([^\]]*)\]?\s*$", runlog or "")
    return [x.strip() for x in m.group(1).split(",") if x.strip()] if m else []


def main(argv=None):
    for _s in (sys.stdout, sys.stderr):        # Windows code pages: never crash on a character
        try:
            _s.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run", nargs="?", help="run number, name or path (default: the newest run folder)")
    ap.add_argument("--runs", help="the folder holding the run folders (default: ../runs next to the kit folder)")
    ap.add_argument("--skip-events", action="store_true", help="skip the slow event-log checks")
    a = ap.parse_args(argv)

    run = RF.find_run(a.run, a.runs)
    name = os.path.basename(run)
    chk = os.path.join(run, RF.CHECK_DIR)
    print(f"Run folder: {run}")
    rep = build_out(run)
    print(f"  {len(rep['files'])} contract file(s) found, {len(rep['renamed'])} renamed, {len(rep['extras'])} extra")

    tx = RF.transcript(run)
    runlog = find_runlog(tx) if tx else None
    ops = operator_messages(tx) if tx else []
    usage, usage_txt = None, ""
    if tx:
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(buf):
            usage = UE.scan(tx)
        usage["run_id"] = name
        usage_txt = buf.getvalue()
        with open(os.path.join(chk, "usage.csv"), "w", encoding="utf-8", newline="") as fh:
            import csv
            w = csv.DictWriter(fh, fieldnames=list(usage))
            w.writeheader()
            w.writerow(usage)
        with open(os.path.join(chk, "usage.txt"), "w", encoding="utf-8") as fh:
            fh.write(usage_txt + "\n".join(f"{k:26s} {v}" for k, v in usage.items()) + "\n")

    # files the run says it wrote but that are not in the folder
    want, want_from = files_written(runlog), "the RUNLOG"
    if not want:                     # before RUN-END there is no transcript: use the contract and manifest
        want_from = "the contract and run_manifest.json"
        engines = []
        try:
            man = json.load(open(os.path.join(rep["out"], "run_manifest.json"), encoding="utf-8"))
            engines = [f.get("name") for f in man.get("files") or [] if CO.ENGINE_FILE_RE.match(str(f.get("name")))]
        except (OSError, ValueError, AttributeError):
            pass
        engines = engines or [f for f in rep["files"] if CO.ENGINE_FILE_RE.match(f)] or ["D02_engine_v1.py"]
        want = []
        for f in CO.ORDER:
            want += engines if f == "<engines>" else [f]
    missing = [f for f in want if f not in rep["files"]]
    resend = None
    stale = os.path.join(chk, "RESEND.md")
    if os.path.isfile(stale):
        os.remove(stale)             # from an earlier check; only a current one may be attached
    if missing:
        resend = open(os.path.join(RF.KIT, "operator", "RESEND.md"), encoding="utf-8").read() \
            .replace("FILE_NAMES", ", ".join(missing)).strip()
        with open(os.path.join(chk, "RESEND.md"), "w", encoding="utf-8") as fh:
            fh.write(resend + "\n")

    cmd = [sys.executable, os.path.join(RF.HERE, "check_outputs.py"), rep["out"],
           "--json", os.path.join(chk, "check.json")]
    if runlog:
        cmd += ["--runlog", runlog]
    if a.skip_events:
        cmd.append("--skip-events")
    print("  running the validator ...")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    check_txt = p.stdout + p.stderr
    with open(os.path.join(chk, "check.txt"), "w", encoding="utf-8") as fh:
        fh.write(check_txt)
    result = next((l.strip() for l in check_txt.splitlines() if l.startswith("RESULT")), "RESULT: validator did not finish")
    fails = [l.strip() for l in check_txt.splitlines() if l.strip().startswith("[FAIL]")]
    warns = [l.strip() for l in check_txt.splitlines() if l.strip().startswith("[WARN]")]

    L = [f"# After-run check: {name}", "",
         f"- Validator: **{result}** (full output: `_check/check.txt`)",
         f"- RUNLOG: {'found' if runlog else '**not found** in the transcript' if tx else '**no transcript** (RUN_ID.jsonl) in the folder'}"]
    if usage:
        L += [f"- Model: {usage['models_list']}; active {usage['active_minutes']} min; "
              f"{usage['tool_calls']} tool calls; reported cost ${usage['reported_usd']}",
              f"- RUN-END found: {usage['run_end_found']}; skills listed: {usage['skills_listed']}; "
              f"skills flagged: {usage['skills_flagged'] or 'none'}; contamination calls: {usage['contamination_calls'] or 'none'}"]
    if tx:
        if ops:
            L += ["- Operator messages: " + "; ".join(f"message {n}: {', '.join(h)}" for n, h in ops)]
        else:
            L += ["- Operator messages: none found"]
        early = [h for n, h in ops if n == 1]
        if early:
            L += [f"- **Operator file in the start upload:** {', '.join(early[0])}. It was in front of the model "
                  "for the whole run; log it as a deviation (instruments §3 B1)."]
        other = [(n, h[0]) for n, h in ops if h[0].startswith(("text:", "attachments only"))]
        if other:
            L += ["- **Other human messages** (a deviation unless logged): "
                  + "; ".join(f"message {n}: {t}" for n, t in other)]
        n_cont = sum("CONTINUE" in h for _, h in ops)
        if n_cont:
            L += [f"- CONTINUE sent {n_cont}x: log each usage-limit stop and restart time (instruments §3 C)."]
    warn_lines = [l for l in usage_txt.splitlines() if l.startswith("warn")]
    L += ["", "## Files", f"- Contract files present: {len(rep['files'])} of {len(want)} expected (from {want_from})"]
    if missing:
        L += [f"- **Missing:** {', '.join(missing)}", "- Attach `_check/RESEND.md` alone in the run's chat, prompt box empty, **before RUN-END**. It says:", "",
              "```", resend, "```"]
    if rep["bundles"]:
        L += ["- Unpacked download bundles (original kept): " + "; ".join(rep["bundles"])]
    if rep["renamed"]:
        L += ["- Renamed browser copies: " + "; ".join(rep["renamed"])]
    if rep["conflicts"]:
        L += ["- **Different downloads under one name:** " + "; ".join(rep["conflicts"])]
    if missing and any(m.endswith(".py") for m in missing):
        L += ["- **Code files missing.** In the run's chat, check that a file card shows for each `.py` file, "
              "and that your browser actually saved it (the downloads list: Ctrl+J in Chrome/Edge on Windows and Linux, Option+Cmd+L on macOS; "
              "look for 'blocked', 'Keep' or a warning). Log which of the two it was (instruments §3 D2)."]
    if rep["extras"]:
        L += ["- Files that are not in the contract (copied, so the validator reports them): " + ", ".join(rep["extras"])
              + ". If they are yours, move them into a subfolder such as `mine`."]
    if rep["own"]:
        L += ["- Your own subfolders, not checked: " + ", ".join(f"`{d}`" for d in rep["own"])]
    if rep["operator"]:
        L += ["- Operator files, not checked: " + ", ".join(rep["operator"])]
    if fails or warns or warn_lines:
        L += ["", "## To look at"] + [f"- {x}" for x in fails + warns] + [f"- usage: {x}" for x in warn_lines]
    L += ["", "Downloaded files were not changed. Re-run this script after adding resent files."]
    with open(os.path.join(chk, "AFTER_RUN.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"\nWritten: {chk}")
    return 0 if p.returncode == 0 and not missing else 1


if __name__ == "__main__":
    sys.exit(main())
