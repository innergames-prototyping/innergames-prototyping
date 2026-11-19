# PROMPT INSTRUMENTS v5.2: SINGLE only
Project Pipeline / InnerGames. Built 2026-11-19 from v5.1 (itself built the same day from v5,
after the v5 pilot Run12 and the first client run Run13). Study document: **never upload this
file to a test chat.**
Tags: [C] checked, [L] inference, [G] guess.

Every command in this document works as written, for every run. Nothing needs a folder name
filled in: the tools find the kit folder, the runs folder and the newest run themselves.

## 0. What changed from v5.1
v5.2 changes the operator side only. **The 8 instruction files are byte-identical to v5.1**, so
a run started from v5.2 sees exactly what a v5.1 run sees. Decided by Korulein on 2026-11-19,
after the Run13 failure review.

| # | Change | Why | Decided by |
|---|---|---|---|
| A | **Diagnostics on every run, study and client:** the validator result (`_check\check.json`), the usage numbers (`_check\usage.csv`) and the full transcript (`RUN_ID.jsonl`) are kept for every run. Never delete them | Korulein: "always in favour of more data, even in client versions"; keep everything for now | Korulein |
| B | **Your own files go in a subfolder of the run folder** (e.g. `mine\`). `AFTER_RUN` skips subfolders and lists them; a loose file of yours is copied and fails F3 | Run13's folder held a `README.pdf` guide made after the run, which failed F3 [C] | Korulein |
| C | **File-card check (§3 D2):** before RUN-END, check that every file has a card in the chat and that the browser saved it. `AFTER_RUN` adds this hint whenever `.py` files are missing | Run13 sent 17 non-zip files and its tool confirmed all 17, yet the 3 `.py` files are not in the folder [C]. Whether the cards were missing or the downloads were blocked is unknown [L] | Review |
| D | Validator v1.4.1: the F3 hint points to the subfolder. No check changed | Follows from B | — |
| E | Tools name "the kit folder" instead of "the v5.1 folder"; `kit_hashes.json` says `v5.2` | Snapshot per version (Korulein) | Korulein |
| F | **Deferred:** a self-check inside the run (the run validating its own outputs before delivery) is decided after Run14 and Run15 | Of Run13's 8 v1.3 failures a run-side check could have caught only one (M3) [C]; adding it now would also change what Run14/15 measure | Korulein (after the runs) |
| G | Corrections to v5.1's account of Run13 (row 9 below, `check_outputs_explained.md`): the 801 test records were an instrument conflict, not a gap; `README.pdf` was not a run output | Errors in the review, found on re-checking the ledger notes and the transcript [C] | Review |
| H | **`CONTINUE.md` confirmed** as the one message allowed after a usage-limit stop (§3 C). Use it instead of typing, and instead of the app's own continue option | Run12's restart was the text "Continue from where you left off." after a re-attachment of the start files [C, Run12 transcript]; whether you typed it or the app sent it is unknown [L]. One fixed file makes every restart identical and recognisable | Korulein |
| I | **AFTER_RUN lists every human message after the start** from the transcript: operator files (RUN-END, RESEND, CONTINUE), typed text and bare re-uploads. It flags an operator file in the start upload | Interventions were logged from memory. On Run13 it finds RUN-END in message 1; on Run12 it finds the re-upload, the continue text and RUN-END [C] | Review |
| J | **AFTER_RUN unpacks a "Download all" zip** in the run folder (contract files only, names only; the zip is kept and not checked as an extra) | The app offers Download all [C, Run1 screenshot]; whether it saves one zip is not known [G]. Without this, a bundle would fail F2 and F3 | Review |
| K | **Cross-platform launchers.** `kit.py` runs every tool on Windows, macOS and Linux (`python3 kit.py after`, or a menu with no command). Next to each `.bat` there is a `.sh` for macOS/Linux (`sh AFTER_RUN.sh`). AFTER_RUN also undoes Linux Firefox's `name(1)` copies and ignores macOS `.DS_Store` and `._` files. `.gitattributes` keeps the `.sh` files' line endings intact if the kit goes through git | The team works on macOS and Linux, where `.bat` files don't run (Korulein). Tested on Linux, including from another folder; macOS not tested [L: same POSIX shell and Python 3.8+, which macOS's python3 meets] | Korulein |

## 0b. What changed in v5.1 (from v5)
"Run12" is the v5 pilot (Lethal Dungeon, extraction path, `AB_v5_pilot_review.md`). "Run13" is the
first Kansen Keren-Senior run (raw path).

### 0b.1 Instruction files (`system\`)
| # | File | Change | Why | Decided by |
|---|---|---|---|---|
| 1 | `00a` | **`01` files are all optional and now four:** `01_rules.txt`, `01_components.json` (upstream extraction, as v5), plus `01_timings.json` and `01_focus.json` (client inputs). The extraction path is triggered by `01_rules.txt` alone | Timings and focus items come from the client, not from upstream | Korulein |
| 2 | `00a` | **"Read every attached file in full from disk"** | The app shows long attachments inline cut off at 2,000 lines [C, Run12 transcript]; the copy on disk is complete | Review |
| 3 | `00a` D3, `00b` §7 | **Duration table as data.** New file `D03_duration_table.json`; every row has one of 13 fixed **duration categories** (setup, teardown, turn_admin, move, draw_card, resolve_card, decide, random_device, token_handling, board_change, round_end, scoring, other); **every event carries `dur {row, n}`**, so every game's play time can be recomputed from its events | Run12 and Run13 playtimes could not be recomputed: event types didn't map to table rows [C]. Invented duration tables drive most of the playtime instability between runs (`AB_stability_runs_v3_to_v5.md`) | Korulein (Arjen's timing method); mechanism by review |
| 4 | `00b` §7.3 | **Dual function for timings.** With `01_timings.json`: provided categories replace the run's values; every other in-play category is scaled by provided ÷ assumed time; observed sessions are compared, not applied. Without it: everything stays `assumed`. Every value records its source (`provided`, `inferred`, `assumed`). One measured value = one occurrence as a person times it (a whole move, not one step) | Korulein: "use whatever statistics are provided and infer the rest from real and assumed statistics; record what is assumed and what is used" | Korulein |
| 5 | `00a`, `00b` §7.4 | **New deliverable D11 `D11_data_needed.md`:** what was used, what was assumed or inferred with its share of play time (largest first), where it is recorded, and what the client can supply next | Korulein | Korulein |
| 6 | `00a` D6, `00b` §8 | **Focus items:** the 1–3 elements gameplay revolves around (player characters, a central deck…), reported per option and player count: outcome, use rate, idle share, spread. Named in an optional `01_focus.json`; otherwise the run chooses and gives a reason | Korulein: a headline playability statistic for what the game revolves around. Mitigation: optional input, else the run's choice with a reason | Korulein |
| 7 | `00b` §4.1, §4.5, `00h` | **Outcome modes:** `competitive`, `cooperative` (with `team_result`, team success instead of seat win shares), `no_winner` | Run13 (Kansen Keren, played together) was forced into the competitive schema [C] | Review |
| 8 | `00b` §4.3 | `game_id` may repeat in `per_game_other` only | Run12 re-ran test seeds and failed P1/P2 for it [C]: an instrument gap, not a run error | Review |
| 9 | `00a` R3, `00b` §4.4 | **Every game simulated has a per-game record**, test and debug games included; **one D8 baseline per engine version**; D8 pairs by seed and engine version | Run13 re-ran test seeds, ledgered every execution, and stored each record once to keep ids unique as v2.2 demanded: 801 ledgered games had no record of their own [C, ledger notes]. The two rules contradicted each other; v5.1 allows the repeats. Run12 ran arms on two engine versions against one baseline [C] | Review |
| 10 | `00b` §1, §3 | **27 files:** rows 10 (`D03_duration_table.json`) and 18 (`D11_data_needed.md`) added. First send = files 1–18; zips = 19–27, one per send. Final check adds "play_min = sum of event durations" | Follows from 3 and 5 | — |
| 11 | `00e` | Headline schema **`headline_v2`**: duration rows gain `category` and `value_source`; new `timings` block; `outcome` gains `mode` and `team_success_share`; new `focus_items` block | Follows from 3, 4, 6, 7 | — |
| 12 | `00g` v0.8 | `run.user_input_files` | Follows from 1 | — |
| 13 | `00c` v0.7 | Event log fields gain `dur`; `D03_duration_table.json` listed | Follows from 3 | — |
| 14 | `00d`, `00f` | **Unchanged** (byte-identical to v5) | — | — |

### 0b.2 Operator procedure and kit
| # | Change | Why | Decided by |
|---|---|---|---|
| 15 | **No folder names in commands.** Double-click launchers in the v5.1 folder (`BEFORE_RUN.bat`, `AFTER_RUN.bat`, `PLAYTIME_RECOMPUTE.bat`, `IMPORT_SQLITE.bat`); each finds the newest run by itself, or takes a run dragged onto it | Korulein: v5's commands were written for Run12 and had to be edited per run | Korulein |
| 16 | **`before_run.py` (new):** checks `system\` against the kit hashes and the game folder against the intake rules (archives, Office files, spaces, `00`/`01` names, operator files); prints the upload list with hashes for the run log | Run13's upload held RUN-END.md and a zip of the game files [C]. Both are catchable before sending | Review |
| 17 | **`after_run.py` (new):** builds a clean `_check\out\` copy (browser renames undone, downloads untouched), finds the RUNLOG in the transcript, lists missing files and writes the ready-to-paste RESEND text, runs `usage_extract` and the validator, writes `_check\AFTER_RUN.md` | Replaces v5 steps E1–E5 (folder sorting, two long commands) | Review |
| 18 | **No `out\` folder to make.** Download everything straight into the run folder; the tools sort it | v5 asked for a hand-sorted `out\` [C, Run12 folder layout] | Review |
| 19 | **RESEND before RUN-END, generated:** `_check\RESEND.md`, ready to attach. Run `AFTER_RUN.bat` before RUN-END: without a transcript it works out the missing files from the contract and the manifest | Files can't be recovered after RUN-END (Run11) [C] | Review |
| 20 | **`operator\CONTINUE.md` (new):** the one message allowed when a usage limit stops a run | Run12 hit the session limit and was restarted by hand [C]; a fixed text keeps that intervention the same across runs | Review; confirmed by Korulein in v5.2 (row H) |
| 21 | **Never upload RUN-END at the start; unpack archives; check usage headroom first** | Run13 [C]; Run12 [C] | Korulein (findings); rules by review |
| 22 | `playtime_recompute.py` (new): a finished run + `01_timings.json` → play time under measured human times, with the D11-style record of what was provided, inferred and assumed. No AI | Arjen can fill in timings after a run; the run need not be repeated | Korulein (dual function) |
| 23 | `import_sqlite.py` (new): validated run → `runs\pipeline.sqlite` (events optional). JSON stays the source | Team decision: keep JSON, add an import | Korulein (team) |
| 24 | `usage_extract.py` v4.2: cuts at the **last** RUN-END, warns if RUN-END appears twice | Run13 uploaded RUN-END.md at the start, so v4.1 cut at turn one and reported $0 [C]. v4.2 on Run13: $10.73 reported, 29.5 active min, 95 tool calls; Run11 and Run12 unchanged | Review |
| 25 | `check_outputs.py` v1.4: see `tools\check_outputs_explained.md` | Follows from 1–12 | — |

### 0b.3 Deferred (not in v5.1)
- Testing-documentation template for Arjen: after Run14 and Run15, in another chat (Korulein).
- Human layer: Sprint 4 (Korulein).
- SQLite as primary storage: no; JSON stays (team).

**Unchanged:** the TASK, D1, D2, D4, D5, D7–D10 and R1, R2, R4–R7 wording; targets; sample sizes;
isolation rules; model and effort.

## 1. Held constant
1. Model `claude-opus-5-5`, effort `high`. Record both on every run.
2. Targets: per game, from the designer; Lethal Dungeon: play only; 30 / 45 / 60 min at 2 / 3 / 4
   players; ±20%.
3. Sample sizes: D4 = 1 logged + 1,000 at 4 players; D5 = 1,000 per player count; D7 = re-run of
   D4's 1,000; D8 = 400 per arm on its baseline's seeds.
4. Isolation:
   - never run in Project Pipeline (it holds the answer key);
   - use the empty "Analysis" project (0 docs);
   - memory and past-chat search off; **all skills off**;
   - no `LD_stat_catalogue`, rulings or study notes in any input (§2.4).
5. Linked computer: accepted, never mentioned by name in the brief. The safeguard stays
   `contamination_calls`.
6. No time cap. Runs go to completion.

## 2. The kit: `tokens\v5.2\`
```
tokens\
  v5.1\                              previous snapshot; leave it as it is
  v5.2\
    AB_prompt_instruments_v5.2.md     this file (never uploaded)
    kit.py                             one launcher for all tools, every OS (§2.5)
    BEFORE_RUN  .bat / .sh             check the upload set          (tools\before_run.py)
    AFTER_RUN  .bat / .sh              check a finished run          (tools\after_run.py)
    PLAYTIME_RECOMPUTE  .bat / .sh     apply measured timings        (tools\playtime_recompute.py)
    IMPORT_SQLITE  .bat / .sh          copy a run into SQLite        (tools\import_sqlite.py)
    system\                            the 8 instruction files: the same in every run
    games\lethal_dungeon\              upload set for Lethal Dungeon (extraction path)
    games\kansen_keren_senior\         upload set for Kansen Keren-Senior (raw path): make it, §2.2
    templates\                         01_timings / 01_focus forms for the client (never uploaded as is)
    operator\                          RUN-END.md, CONTINUE.md, RESEND.md (the template; AFTER_RUN fills it in)
    tools\                             the scripts, kit_hashes.json, check_outputs_explained.md
    tests\                             fake runs and mutation tests for the validator
    docs\backend_spec.md               what the backend must carry (for the backend developer)
  runs\
    Run14_<label>\                     one folder per run; every download goes straight in
      mine\                           your own files for that run (guides, notes): never checked
      _check\                         written by the tools; keep it
```
**Upload = everything in `system\` + everything in `games\<game>\`.** Nothing else, ever.
The tools need Python 3.8+ and nothing else; how to start them on each OS is in §2.5.

### 2.1 Instruction files (`system\`)
BEFORE_RUN checks these hashes for you (`tools\kit_hashes.json`). Identical in v5.1 and v5.2.

| File | Version | Bytes | sha256 (first 12) | vs v5 |
|---|---|---|---|---|
| `00a_START_HERE.md` | brief v5.1 | 9,667 | `7a290d1ae43c` | changed |
| `00b_output_contract.md` | contract v2.3 | 20,193 | `70778af7a076` | changed |
| `00c_reporting_standard.md` | standard v0.7 | 4,338 | `284698f01be3` | changed |
| `00d_stat_definitions.md` | definitions v0.1.1 | 16,831 | `0ba0018de63d` | same |
| `00e_template_headline.json` | headline_v2 | 4,455 | `cc40c372bf8d` | changed |
| `00f_template_summary.json` | v0.6 | 2,770 | `772f6243e830` | same |
| `00g_template_run_manifest.json` | v0.8 | 2,393 | `497b24ef0e06` | changed |
| `00h_template_per_game.json` | v0.7 | 2,683 | `bab86335bc4c` | changed |

### 2.2 Game inputs for field testing
**Equal inputs:** Run14 and Run15 use the same game files as Run12 and Run13, so the only
difference is the instrument version (v5 → v5.2, with v5.1's instruction files).

| Run | Game, path | Upload from `games\…` | Same as |
|---|---|---|---|
| Run14 | Lethal Dungeon, extraction | `01_rules.txt` (8,519 B, `e9ecc555f393`), `01_components.json` (76,203 B, `5bad12b6bf85`) | Run12, byte-identical [C] |
| Run15 | Kansen Keren-Senior, raw | the 3 PDFs from Run13's `Bestanden.zip`, **unpacked**, spaces → `_`: `Spelboekje_v5_18_sep_2026.pdf`, `Spelbord_18_sept_2026.pdf`, `Speelkaartjes_17_sept_2026_BRON.pdf` | Run13's game files; **not** its packaging |

- **Run15 is equal in content, not in packaging, on purpose.** Run13 got the PDFs inside a zip,
  plus `RUN-END.md` in the same upload [C, Run13 manifest]. Repeating that would test the
  operator mistake again, not v5.1. Renaming spaces to `_` changes nothing the model sees: the app
  already does it on upload (v5 row 17) [C].
- **Make the folder `games\kansen_keren_senior\` and put the 3 PDFs in it yourself.** The kit
  can't ship an empty folder, and a placeholder file in it would be uploaded.
  BEFORE_RUN then prints their hashes; copy them into the run log.
- **No `01_timings.json` or `01_focus.json` in Run14 or Run15.** Run12 and Run13 had neither, and
  equal inputs means none now. The runs choose their own focus items (with reasons) and mark every
  duration `assumed`. Arjen's timings are applied afterwards with PLAYTIME_RECOMPUTE (§6), so
  the runs don't need repeating.

### 2.3 Intake rules (every game, every client)
Keep the designer's file names; change a file only when a rule requires it, and log every change.
BEFORE_RUN checks rules 1, 2 and 4.
1. **Formats:** PDF, plain text (`.txt`, `.md`, `.csv`), JSON and images (`.jpg`, `.png`,
   `.gif`, `.webp`) go in as they are. Convert Office files (`.docx`, `.pptx`, `.xlsx`, …) to
   PDF. **Unpack archives** into the game folder, flat, and remove the archive.
2. **Names:** remove `< > : " | ? * \ /`; spaces become `_`. A client name starting with `00` or
   `01` gets `client_` in front. Upstream outputs are renamed exactly `01_rules.txt` and
   `01_components.json`. A client's timings and focus forms are saved as exactly
   `01_timings.json` and `01_focus.json`.
3. **Size:** under 500 MB per file.
4. **Nothing of ours in the game folder:** no operator files (RUN-END, RESEND, CONTINUE), notes,
   rulings, answer keys or earlier outputs.

### 2.4 Guard on what goes into an input
Test for every fact in an input file: *could the upstream stage, or the client, have known it
from the designer's files, components and real play, without being told by us?*
- **Allowed:** rulebook text, component kinds and counts, physical properties (tile shapes),
  measured times from real play (`01_timings.json`), the elements the designer says the game
  revolves around (`01_focus.json`).
- **Never:** the designer's rulings on questions the rulebook leaves open (K1, K3, …), and above
  all the deliberate benchmark flaws (K4, K5). A focus item may name a component; it may never
  hint at a flaw ("check whether the teleporter breaks the game" is out).
- **Rulebook errors stay as printed** (4 large scrap tokens, 2 risky jump markers): correcting
  them would remove the R4 test.

### 2.5 Starting the tools on Windows, macOS and Linux
Every tool works on the newest run by default; add a run number, part of its name or its folder
to pick another. Python 3.8+ is the only requirement.

| | Windows | macOS | Linux |
|---|---|---|---|
| Easiest | double-click `AFTER_RUN.bat` (or drag a run folder onto it) | in Terminal: `sh ` then drag `AFTER_RUN.sh` into the window, Enter | `sh AFTER_RUN.sh` in the kit folder |
| Any tool, any folder | `py kit.py after` | `python3 kit.py after` | `python3 kit.py after` |
| With a run | `py kit.py after 14` | `python3 kit.py after 14` | `python3 kit.py after 14` |
| Menu | `py kit.py` | `python3 kit.py` | `python3 kit.py` |

Commands: `before`, `after`, `recompute`, `import`. macOS without Python 3: run
`xcode-select --install` once. The `.sh` files run with `sh` and need no execute permission.

## 3. Operator procedure
### A. Before the run
- [ ] **Usage headroom:** start only with enough of the usage limit left for a full run
      (Run12 used about $27 of usage and hit the limit [C]). If unsure, wait for a reset.
- [ ] Open a **new chat** in the "Analysis" project. It shows **0 docs**; delete any report a
      previous run saved there.
- [ ] Memory off, past-chat search off, **all skills off**.
- [ ] Model picker shows **Opus 5.5**; effort `high`.
- [ ] Run **BEFORE_RUN** (§2.5). It must say `READY` for your game. Copy its upload list
      (names, bytes, hashes) into the run log.
- [ ] Make the run folder in `tokens\runs\`: `Run<number>_<label>` (e.g. `Run14_LD`,
      `Run15_KK`). The number must be new; the tools find a run by it.

### B. Start the run
1. Drag in **all files from `system\`** and **all files from `games\<game>\`**. Nothing from
   `operator\`, `templates\` or `tools\`.
2. Count the chips: 8 + the game files (BEFORE_RUN prints the total: 10 for Run14, 11 for
   Run15).
3. Leave the prompt box **empty**. Type nothing, not even a space.
4. Send.

### C. During the run
- Say nothing. If the model asks a question, don't answer; log the question and whether the run
  stalled.
- **If a usage limit stops the run:** wait for the reset, attach `operator\CONTINUE.md` alone
  with the prompt box empty, send, and log the stop and the restart time. This is the only
  message allowed during a run. Never type a "continue" yourself and don't use the app's own
  continue option: either would differ from run to run.
- If the app re-attaches the start files by itself after a pause, don't remove them; just log it.
  `AFTER_RUN` lists it as "attachments only".
- If the run stops for any other reason without the RUNLOG line, log it as stalled. Don't prompt it.

### D. End the run
1. When the final message ends with the `RUNLOG:` line, copy that line into the run log.
2. **Check the file cards, then download.**
   - *What a file card is:* each file the run sends appears in the chat as a box with a title,
     a type label and a Download button. The title is a display name made from the file name
     (Run1 showed "Test engine" with the label "PY") [C, Run1 screenshot], so match cards by
     title and type, not by exact name. The run's own text ("17 files delivered") is the tool's
     report, not proof: in Run11 it reported five files that never got a card [C].
   - *Count:* one card per name in the RUNLOG's `files_written` (27 + one per extra engine
     version). Find the `.py` cards in particular: label **PY**, titles like "D02 engine v1",
     "D02 run".
   - *Download* every card straight into the run folder, or use **Download all** if the chat
     offers it. If that saves one zip, leave it in the run folder: `AFTER_RUN` takes the files out
     of it (and keeps the zip). Don't rename anything; ` (1)` copies are fine.
   - *Check the browser's download list* (Ctrl+J). A file marked "blocked", "dangerous",
     "Keep / Discard" or "failed" did not land; choose Keep or download it again. Code files
     (`.py`) are the likeliest to be held back [G].
   - Log for any missing file whether its card was **absent** (a delivery loss: RESEND) or
     **present but not saved** (a download problem: download it again; no RESEND needed).
3. Run **AFTER_RUN** (§2.5). Read the `## Files` part of its summary.
   - **Nothing missing:** go to step 4.
   - **Files missing:** it writes `runs\<run>\_check\RESEND.md` with the missing names filled
     in. Attach that file alone with the prompt box empty, send, download the resent files, and
     run AFTER_RUN again. Log it as an operator intervention. At most once.
4. Attach `operator\RUN-END.md` **alone, as the file, unchanged**, with the prompt box empty, and
   send. (`RUN_ID` inside it is not a blank to fill in; the tools rename the result.)
5. Download `RUN_ID.jsonl` from the reply into the run folder. If no file comes back, or the app
   pauses the chat first, log it. Don't type anything else.

### E. After the run
1. Run **AFTER_RUN** (§2.5) once more. With `RUN_ID.jsonl` present it adds cost, time,
   model list, skills and contamination, and compares the RUNLOG. Open
   `runs\<run>\_check\AFTER_RUN.md`.
2. Check: validator `PASSED`; one model in the model line; skills flagged `none`; contamination
   calls `none`.
3. Run **IMPORT_SQLITE** (§2.5) if the team wants the run in `runs\pipeline.sqlite`
   (it refuses a run that didn't pass; for comparisons with older runs use
   `python3 kit.py import <run number> --force`).
4. Keep `RUN_ID.jsonl` and `_check\` for every run, study or client (row A). Put anything of
   your own for the run in `mine\`.
5. Fill in the run log (§4).

**To check an older run**, give its number: `python3 kit.py after 13` (Windows: `py kit.py after 13`,
or drag its folder onto `AFTER_RUN.bat`).

## 4. Run log (one row per run)
| Field | Value |
|---|---|
| Run folder | |
| Date, start time, end time | |
| Model, effort | |
| `BEFORE_RUN` result and upload list (names, bytes, hashes) / path (extraction or raw) | |
| Intake changes to game material (§2.3) | |
| Prompt box empty | yes / no |
| Questions asked by the model / stalled / usage-limit stops (CONTINUE sent at …); `AFTER_RUN`'s operator-messages line | |
| RUNLOG line | |
| Files missing after download: card absent or not saved? RESEND sent? | |
| From `AFTER_RUN.md`: validator result; cost; active minutes; models; skills flagged; contamination | |
| Deviations | |

## 5. Field testing: Run14 and Run15
The v5 pilot loop is closed: Run11 was pilot 1 (v4, non-sterile probe), Run12 the one repeat
(v5). v5.2 goes straight to field testing; problems found there are fixed and logged as a version
change, not answered with another pilot.

| | Run14 | Run15 |
|---|---|---|
| Game, path | Lethal Dungeon, extraction | Kansen Keren-Senior, raw |
| Compared with | Run12 (v5, same files) | Run13 (v5, same game files) |
| Main question | Do the v5.1 instruction files fix Run12's contract failures, and do the new duration and focus parts work on a game we can grade? | Do the outcome modes and the raw path work on a cooperative client game? |
| Graded against | the official accuracy table (`AB_accuracy_table_official.md`, 20 items, /19 on the extraction path) | no answer key: the validator, and Arjen (§6) |

**Each run passes when:**
1. it completes with no typed text, no question answered and no stall (a usage-limit stop with
   `CONTINUE.md` is logged, not a fail);
2. `AFTER_RUN.md` shows the validator `PASSED`, or every FAIL is traced to its cause;
3. contamination calls and skills flagged are both `none`;
4. Korulein can say what each delivered file is for and where it came from, using
   `tools\check_outputs_explained.md` and this document.

**What the pair can and cannot show:**
- Run14 vs Run12 isolates the instrument change (same files). Run15 vs Run13 does not fully: Run13
  also had the zip and RUN-END mistakes. A difference there may come from either [L].
- Playtimes stay `assumed` in both runs until Arjen's timings arrive. Comparing their playtimes
  with Run12/13 tests stability, not accuracy.
- One run per game shows whether things work, not how stable they are.

## 6. Applying Arjen's timings later (dual function)
1. Give Arjen `templates\01_timings.template.json` (and, if he wants to name focus items,
   `templates\01_focus.template.json`). He fills in only what he measured; everything is optional.
2. Save his file as `01_timings.json` in the run's folder (to recompute that run) or in
   `games\<game>\` (for the game's next run).
3. Run **PLAYTIME_RECOMPUTE** on the run folder (§2.5: drag it onto the `.bat`, or give its number). It writes
   `runs\<run>\_check\playtime_recompute\PLAYTIME_RECOMPUTE.md`: the recomputed play times per
   player count with the verdict against target, then the D11 record of what was provided,
   inferred and assumed, the share of play time each category carries, where everything is
   stored, and what to time next.
4. Without any timings file the same script still runs: its section 4 is the list of what to ask
   Arjen to time first.

## 7. Moving to the API later [C, Files API docs, 2026-10-26]
Unchanged from v5: text files as `document` blocks with `text/plain`, sent in name order (`00a`–`00h`,
then `01` files, then game material); 500 MB per file; outputs come from the code-execution
container through the Files API; no RUN-END needed (each response reports its own usage).

## 8. Open
1. After Run14 and Run15: which further games and how many runs per path.
2. Result stability is still open: layout policy and bot design. Duration tables are addressed
   by Arjen's timings (§6), once he supplies them.
3. Whether `D02_run.py` must reproduce the D8 strategy bots exactly, or only the main batches.
4. After Run14 and Run15: a self-check inside the run (row F).
5. The cause of Run13's missing `.py` files (row C). If Run14/15 show `.py` cards that never
   appear while other files do, deliver code as `.py.txt` in v5.3 (a file-list change).
