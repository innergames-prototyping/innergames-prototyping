"""runfolder.py: find the run folder and the files in it, so no command needs a path.

Layout this assumes (the kit folder, e.g. v5.2, sits next to the runs folder):
    tokens/
      v5.2/tools/<this file>
      runs/Run14_LD/...      <- one folder per run, downloads straight into it

Shared by after_run.py, playtime_recompute.py and import_sqlite.py. Standard library only.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)                                   # the kit folder (v5.2)
CHECK_DIR = "_check"                                          # what after_run.py writes, inside the run folder
# files in a run folder that are ours, not the run's: never copied into _check/out
OPERATOR_FILES = re.compile(r"^(RUN_ID.*\.jsonl|.*transcript.*\.jsonl|usage.*\.csv|01_timings.*\.json|01_focus.*\.json"
                            r"|run_?log.*\.(md|txt)|notes?.*\.(md|txt)|desktop\.ini|thumbs\.db|\.ds_store)$", re.I)


def runs_dir(override=None):
    """The folder that holds one folder per run."""
    if override:
        return os.path.abspath(override)
    for cand in (os.path.join(KIT, "..", "runs"), os.path.join(KIT, "..", "..", "runs"), os.path.join(KIT, "runs")):
        if os.path.isdir(cand):
            return os.path.abspath(cand)
    sys.exit(f"No 'runs' folder found next to {KIT}. Pass --runs <folder> once, or move the kit folder next to 'runs'.")


def newest_file_time(folder):
    t = 0.0
    for name in os.listdir(folder):
        p = os.path.join(folder, name)
        if name != CHECK_DIR and os.path.isfile(p):
            t = max(t, os.path.getmtime(p))
    return t


def find_run(arg=None, runs=None):
    """arg: nothing (newest run), a full path, a folder name, a run number (14) or part of a name."""
    if arg and os.path.isdir(arg):
        return os.path.abspath(arg)
    base = runs_dir(runs)
    folders = [os.path.join(base, d) for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))]
    if not folders:
        sys.exit(f"No run folders in {base}.")
    if not arg:
        return max(folders, key=newest_file_time)
    a = str(arg).lower()
    if a.isdigit():
        hits = [f for f in folders if re.match(rf"run0*{a}(\D|$)", os.path.basename(f).lower())]
    else:
        hits = [f for f in folders if os.path.basename(f).lower() == a] or \
               [f for f in folders if a in os.path.basename(f).lower()]
    if len(hits) == 1:
        return hits[0]
    names = ", ".join(sorted(os.path.basename(f) for f in hits)) or "none"
    sys.exit(f"'{arg}' matches {len(hits)} run folders in {base} ({names}). Give more of the name.")


def transcript(run):
    """The exported session log: RUN_ID.jsonl, or another .jsonl that is not a run output."""
    names = [n for n in os.listdir(run) if n.lower().endswith(".jsonl")]
    pref = [n for n in names if n.upper().startswith("RUN_ID")]
    pick = pref or names
    if not pick:
        return None
    return os.path.join(run, max(pick, key=lambda n: os.path.getmtime(os.path.join(run, n))))


def own_folders(run):
    """Subfolders of a run folder other than _check: the operator's own files (guides, notes), never checked."""
    return sorted(d for d in os.listdir(run) if d != CHECK_DIR and os.path.isdir(os.path.join(run, d)))


def check_out(run):
    """The clean copy of the outputs that after_run.py builds."""
    return os.path.join(run, CHECK_DIR, "out")
