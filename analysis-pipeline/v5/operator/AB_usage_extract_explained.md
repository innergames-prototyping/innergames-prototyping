# Token capture: instructions
Project Pipeline A/B study. v4, 2026-10-11. Uses `usage_extract.py` v4 (in the project).

Only §1 goes to the test chat, and only as the run's final message. Never paste this file into a
test chat: the model must not know about the measurement while it works, and the marker word in
§1 would cut the count short.

## 1. Final message of every run (both conditions)
Send this as a separate message once the run has ended: RUNLOG line printed, stall, or cap hit.
Use exactly the same text every time. Only `<<RUN_ID>>` changes, and it comes from the run log
(`<game>_<SINGLE|STAGED>_<replicate>`).

````
RUN-END. The task is finished; do not continue it or comment on it.
Run this code exactly, then send me the file it prints as a downloadable file. Reply with nothing else.

python3 - <<'EOF'
import glob, os, json, shutil
RUN_ID = "<<RUN_ID>>"
src = max(glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl")), key=os.path.getmtime)
dst = os.path.join(os.getcwd(), RUN_ID + ".jsonl")
shutil.copyfile(src, dst)
with open(dst, "a", encoding="utf-8") as f:
    f.write("\n" + json.dumps({"type": "run-meta", "run_id": RUN_ID, "source": os.path.basename(src)}) + "\n")
print(dst)
EOF
````

The code copies the session transcript to `<RUN_ID>.jsonl` and writes the run ID inside it as its
last line. The script drops everything from the `RUN-END` message onward, so this export step is
not counted in the run.

If the chat does not send the file, the run's token data is gone. Mark it missing in the run log;
do not re-run in the same session.

## 2. After the runs (on your Windows PC)
**One-time setup**
1. Open PowerShell (Start menu, type `powershell`) and run `py --version`.
   - If it prints `Python 3.x`, you are set.
   - If not, install Python 3 from python.org and tick "Add python.exe to PATH" in the installer.
2. Make a study folder, for example `E:\Project Files\ProjectPipeline\tokens\`. Put
   `usage_extract.py` (download it from the project) there, and make an empty `runs` folder
   inside it.

**After each run**
1. Download the `.jsonl` file the chat sends. Move it from Downloads into `runs\` without
   renaming it.
   - If your browser added ` (1)` to the name, delete just that part.
   - The script compares the file name with the run ID written inside the file and warns if they
     differ.

**To analyse (any time, as often as you like)**
1. In File Explorer, open the study folder. Click the address bar, type `powershell` and press
   Enter. PowerShell opens already inside that folder.
2. Paste this command and press Enter. The prices are for Opus 5.5; see
   `AB_token_measurement.md`.
   ```
   py usage_extract.py runs\*.jsonl --csv usage.csv --prices 4,20,0.2,5,8
   ```
   It prints each run's figures and writes `usage.csv`, one row per run, which opens in Excel.
   The script reads the `runs` folder and never changes it, so re-running is safe.
3. **Primary figures: `priced_usd` and `active_minutes`.** Report the five `measured_*` token
   classes next to them. Any line starting `warn:` belongs in that run's log.
4. **`contamination_calls` must be empty.** If it is not, the run reached outside material:
   exclude the run, or justify keeping it in the paper.

Command Prompt works too. The script expands `*.jsonl` itself, so the command is the same in
either.

## 3. For the paper: provenance and validation
- The script was written from scratch for this study and uses only the Python standard library.
  Field names were read off a real transcript, not taken from documentation.
- **Bug caught during validation.** The transcript writes one row per content block, and every
  copy carries the same `usage` (pilot: 225 assistant rows, 110 distinct ids). Summing rows
  overcounted by about 2.5x. v2 de-duplicates by `message.id`.
- **Pilot check (v2)**, measured vs the transcript's own `cost-state`: output +10%, cache read
  +7%, cache write +0.1%. Plain input tokens disagree (226 vs 36,862), unexplained but small in
  cost. Pilot headline: 31.2M tokens, 94% cache reads, $33.08 reported.
- **v3 changes:**
  - run ID read from the file
  - `RUN-END` cut-off
  - Windows wildcards
  - cache writes split into 5-minute and 1-hour, since they are priced differently
  - `--prices` takes five numbers
  - a `reported_lag_msgs` column
- **v4 changes (2026-10-11):**
  - `active_minutes`, the model's working time:
    - It runs from each human message to the model's last output before the next one, and
      includes the time spent running simulations.
    - On this session it gave 9.3 min. The transcript's own counter gave 9.7 min (8.9 min
      generating plus 0.8 min running tools) for the same stretch.
  - `contamination_calls` lists any call to skills, memory, project docs, past chats or the
    user's computer.
  - **Bug fixed:** tool calls are spread over the duplicate rows, so de-duplicating dropped most of
    them. On this session v3 counted 2 of 39.
- **Measured vs reported:** publish the measured figures, priced with `--prices`. They count up to
  `RUN-END` exactly and split the two kinds of cache write. The `cost-state` snapshots turn out to
  be written at the end of each turn. The 5-of-8 lag found in v3 came from copying a transcript in
  the middle of a turn. In a real run `RUN-END` is its own turn, so reported and measured should
  agree [L]. Treat a large `reported_lag_msgs` as a warning.
- **Limits:**
  - work done by sub-agents in other sessions is not in the transcript
  - `span_minutes` includes idle time; use `active_minutes`
  - `active_minutes` uses row timestamps, so the tail of a turn's final message may be missed [G: under a minute per turn]
  - thinking tokens sit inside output
  - `human_turns` also counts system-injected messages, so treat it as a sanity check only
