# Analysis v5.2: inputs and outputs

Research for the ticket "What does analysis v5.2 take in and give out?". Source: the kit at `analysis-pipeline/` on `feat/backend-with-pipelines` (commit `f131f43`), Korulein's backend spec (comment on the ticket "Get analysis v5.1 onto the branch"), and Luc's `backend/app/pipeline.py` on `feature/extraction-to-simulation`. Every claim cites a file and line. Line numbers are for these commits. Paths under `system/`, `tools/`, `templates/`, `operator/` and `tests/` are inside `analysis-pipeline/`.

Tags: **[verified]** checked by running a command; **[not verified]** an inference that no file or run confirms. All other claims are read from the cited file.

## 1. Kit layout and versions

- v5.2 changes only the operator side. The 8 instruction files are byte-identical to v5.1 (`analysis-pipeline/AB_prompt_instruments_v5.2.md:11-12`).
- Versions: brief v5.1 (`system/00a_START_HERE.md:2`), contract v2.3 (`system/00b_output_contract.md:2`), reporting standard v0.7 (`system/00c_reporting_standard.md:2`), headline schema `headline_v2` (`system/00e_template_headline.json:2`), manifest schema 0.8 (`system/00g_template_run_manifest.json:2`), validator 1.4.1 (`tools/check_outputs.py:29`).
- The hashes of the 8 files are in `tools/kit_hashes.json` (kit `v5.2`, line 2). `tools/before_run.py:41-55` fails when a file in `system/` differs from them.
- The instruments describe a layout that is not the repo layout: `games\<game>\` inside the kit and `runs\` next to it (`AB_prompt_instruments_v5.2.md:89-112`), and `docs\backend_spec.md` (line 107). In the repo the game material is at `games/LethalDungeon/`, outside the kit. The kit has no `runs/` folder and no `docs/backend_spec.md`. [verified] on DevBox: `python3 kit.py before` stops with `FileNotFoundError` on `analysis-pipeline/games` (`tools/before_run.py:23,116`), and `python3 kit.py after` stops with "No 'runs' folder found" (`tools/runfolder.py:22-29`).

## 2. Inputs

### 2.1 The upload set

The upload is everything in `system/` plus everything in the game folder, and nothing else (`AB_prompt_instruments_v5.2.md:113`; `system/00a_START_HERE.md:6-32`).

| Kind | Files | Required | Source |
|---|---|---|---|
| Instruction files | `00a_START_HERE.md`, `00b_output_contract.md`, `00c_reporting_standard.md`, `00d_stat_definitions.md`, `00e_template_headline.json`, `00f_template_summary.json`, `00g_template_run_manifest.json`, `00h_template_per_game.json` | always all 8 | `system/00a_START_HERE.md:8-19` |
| `01` files | `01_rules.txt`, `01_components.json` (upstream extraction); `01_timings.json`, `01_focus.json` (client inputs) | all optional | `system/00a_START_HERE.md:21-28`; `AB_prompt_instruments_v5.2.md:36` |
| Game material | every other attached file: rulebook, photos, other designer files | may be empty on the extraction path | `system/00a_START_HERE.md:30-32` |

- Path choice: if `01_rules.txt` is present, the run takes the extraction path. `01_rules.txt` is then the rulebook and `01_components.json` holds the authoritative counts. Otherwise the run takes the raw path and builds D1 from the game material (`system/00a_START_HERE.md:34-40`). `before_run.py` uses the same test (`tools/before_run.py:101`) and rejects `01_components.json` without `01_rules.txt` (lines 93-94).
- The only allowed `01` names are the four above (`tools/before_run.py:24,79-80`). Upstream outputs must be renamed to exactly `01_rules.txt` and `01_components.json` (`AB_prompt_instruments_v5.2.md:158-160`). Luc's pipeline does this rename (`backend/app/pipeline.py:18,95-96`).
- Intake rules: PDF, `.txt/.md/.csv`, JSON and images pass as they are. Office files become PDF. Archives are unpacked flat. Spaces become `_`. A client file named `00…` or `01…` gets the prefix `client_`. Each file must be under 500 MB. Operator files, notes, rulings and earlier outputs stay out (`AB_prompt_instruments_v5.2.md:151-163`). `tools/before_run.py:58-102` implements rules 1, 2 and 4, and checks the `schema` field of `01_timings.json` (`timings_v1`) and `01_focus.json` (`focus_v1`) (lines 95-100).
- Guard: no designer rulings, answer keys or hints at known flaws go into any input. Rulebook errors stay as printed (`AB_prompt_instruments_v5.2.md:165-175`).
- The run starts with an empty prompt. `00a` is the whole instruction (`AB_prompt_instruments_v5.2.md:209`; `system/00a_START_HERE.md:2-3`).

### 2.2 Order

- Reading order for the model: `00a` first, then the `01` files, then all game material, then `00b` to `00h` in order (`system/00a_START_HERE.md:49-50`).
- Send order planned for the API: name order, so `00a`–`00h`, then the `01` files, then game material (`AB_prompt_instruments_v5.2.md:323-326`; backend spec §8). This differs from the reading order, but `00a` tells the model the reading order [not verified that the send order has an effect].
- The model must read every attached file in full from disk, because an inline copy can be cut off (`system/00a_START_HERE.md:46-47`; reason in `AB_prompt_instruments_v5.2.md:37`).

### 2.3 Where designer numbers enter

| Designer number | Where it enters | Notes |
|---|---|---|
| Target play time per player count, tolerance, play or session basis | Written into the brief: "30 minutes at 2 players, 45 minutes at 3 players, 60 minutes at 4 players, tolerance ±20%" (`system/00a_START_HERE.md:73-74`) | These are the Lethal Dungeon numbers. The instruments say targets are "per game, from the designer" (`AB_prompt_instruments_v5.2.md:76-77`), but no input file holds them. Changing them changes `00a`, which then fails the hash check (`tools/before_run.py:52-53`). The run copies them into `run_manifest.json → config` (`system/00g_template_run_manifest.json:17-27`) and `headline.json → targets` (`system/00e_template_headline.json:6-10`). The validator only checks that those two agree (`tools/check_outputs.py:786-794`). |
| Player counts to cover | Written into the brief: "Player counts to cover: 2-4" (`system/00a_START_HERE.md:75`) | Same problem as the targets. D4 is fixed at 4 players (`system/00a_START_HERE.md:94`). |
| Measured times per duration category, observed sessions | `01_timings.json`, schema `timings_v1` (`templates/01_timings.template.json`) | Per category: `min_s`, `max_s`, optional `typical_s`, `observations`, `note` (lines 5-18). Sessions: `player_count`, `play_min`, `setup_min`, `first_play` (lines 19-21). A category counts as provided only when `min_s` and `max_s` are both filled (line 25). Applied by contract §7.3 (`system/00b_output_contract.md:234-256`). |
| Focus items | `01_focus.json`, schema `focus_v1` (`templates/01_focus.template.json`) | 1 to 3 names in the rulebook's words (line 8). Without the file the run chooses them and gives a reason (`system/00b_output_contract.md:275-276`). |

- Timings can also be added after a run. `tools/playtime_recompute.py` applies a `01_timings.json` to a finished run, with no AI (`AB_prompt_instruments_v5.2.md:310-321`; `tools/playtime_recompute.py:1-19`). It looks for the file in this order: `--timings`, the run folder, `<kit>/games/*/01_timings.json` (lines 38-52).
- The sample sizes (1,000 per player count, 400 per D8 arm) are fixed in the brief (`system/00a_START_HERE.md:94-111`) and in the validator (`tools/check_outputs.py:90-91`). They are kit constants, not designer numbers.

## 3. Outputs

### 3.1 Files the model writes

The model writes exactly 27 files, plus one for each extra engine version, into one flat folder `out/` (`system/00b_output_contract.md:9-46`). The validator has the same list (`tools/check_outputs.py:32-43`).

| # | File | Format | Holds |
|---|---|---|---|
| 1 | `REPORT.md` | Markdown | the final report, under 1,200 words |
| 2 | `headline.json` | JSON, `headline_v2` | the key results; the file the results screen reads first (`00b:159-184`) |
| 3 | `summary.json` | JSON | all aggregates; D8 arms under `strategies` |
| 4 | `run_manifest.json` | JSON, schema 0.8 | inputs used, targets, engine versions, simulation ledger, vocabulary, `files` list (bytes, SHA-256, records) |
| 5 | `D01_rules_dossier.md` | Markdown | D1, with interpretations I1..In |
| 6 | `D01_board_layout.json` | JSON or `null` | the board layout |
| 7 | `D02_engine_v<n>.py` | Python | one file per engine version from v1 |
| 8 | `D02_run.py` | Python | re-runs any ledger batch |
| 9 | `D03_playtime_model.md` | Markdown | the duration table, its assumptions and sources |
| 10 | `D03_duration_table.json` | JSON, `duration_table_v1` | the duration table as data (`00b:214-232`) |
| 11-18 | `D04_single_vs_batch.md` … `D11_data_needed.md` | Markdown | D4 to D11 |
| 19-23 | `per_game_D04/D05/D07/D08/other.jsonl.zip` | zip with one JSON Lines member | one record per game |
| 24-27 | `events_D04/D05/D07/D08.jsonl.zip` | zip with one JSON Lines member | one record per event |

Format rules: each zip holds one member and uses DEFLATE; text is UTF-8 with LF line endings; JSON is strict (no `NaN` or `Infinity`); no other formats are allowed (`system/00b_output_contract.md:48-64`). A file with nothing to hold is still written (lines 12-15).

### 3.2 Files the scripts write

All scripts use only the standard library, except `tests/make_fake_run.py`, which imports `numpy` (`tests/make_fake_run.py:5`).

| Producer | Output | Path | Format |
|---|---|---|---|
| `tools/check_outputs.py` (validator) | one result per check, then `RESULT: PASSED/FAILED` | stdout; `--json <file>` outside the checked folder (`tools/check_outputs.py:1170-1230`) | text; JSON `{tool, folder, result, counts, items}` |
| `tools/after_run.py` | clean copy of the outputs, validator result, usage, RESEND text, summary | `<run>/_check/out/`, `check.txt`, `check.json`, `usage.txt`, `usage.csv`, `RESEND.md`, `AFTER_RUN.md` (`tools/after_run.py:7-12,219-225,249-263,317`) | files, text, JSON, CSV, Markdown |
| `tools/usage_extract.py` | tokens, cost, active minutes, tool calls, models, skills, contamination | called by `after_run.py`, or with `--csv` (`tools/usage_extract.py:7-31`) | CSV row |
| `tools/playtime_recompute.py` | play time under measured timings, as a D11-style record | `<run>/_check/playtime_recompute/PLAYTIME_RECOMPUTE.md`, `playtime_recomputed.json`, `D03_duration_table_recomputed.json` (`tools/playtime_recompute.py:18-19,164-236`) | Markdown, JSON |
| `tools/import_sqlite.py` | a read copy of a passed run | `runs/pipeline.sqlite` (`tools/import_sqlite.py:5,103,129`); 13 tables (lines 32-67) | SQLite |
| `tools/before_run.py` | upload list with sizes and hashes, then `READY` or `NOT READY` | stdout only (`tools/before_run.py:120-140`) | text |
| `backend/app/pipeline.py` (Luc) | session stream, stderr, validator JSON | `simulation/claude.jsonl`, `claude.err`, `check.json` (`backend/app/pipeline.py:57-61,105-109`) | stream-json, text, JSON |

### 3.3 Where assumptions, missing numbers, designer questions and the run log appear

The model writes all of these, and only at the end of the run. The brief asks for all deliverables in order, in one turn (`system/00a_START_HERE.md:56-59,80`), and the contract forbids sending files before the end (`system/00b_output_contract.md:78`). The kit does not say whether the model may write files to `out/` earlier [not verified].

| Item | Where | Notes |
|---|---|---|
| Assumptions: rule readings | `D01_rules_dossier.md`, numbered I1..In (`00a:81-84`); `headline.json → interpretations` with `id`, `topic`, `reading`, `tag`, `tested_arm_ids` (`00e:111-119`); `run_manifest.json → vocabulary.readings` (`00g:78-80`) | Each reading must be tested as a D8 arm (`00a:108-112,138-141`) |
| Assumptions: durations | `D03_duration_table.json` rows with `value_source` (`assumed`, `inferred` or `provided`) and the run's own `assumed` values (`00b:214-226`); `headline.json → duration_table` and `timings` (`00e:14-35`); `D03_playtime_model.md` | `timings.categories_assumed` and `assumed_share_of_play_time` (`00e:29,31`) |
| Assumptions: everything else | `D09_limitations.md`: "what in the analysis is an assumption, what could not be verified" (`00a:113-114`); `headline.json → untested` (`00e:144-146`) | Rule R1 tags every load-bearing claim [C], [L] or [G] (`00a:122-123`) |
| Missing numbers | `D11_data_needed.md`: what was used, what was assumed or inferred with its share of play time, where it is recorded, what the client can supply (`00b:258-270`; `00a:117-119`) | The backend can rebuild this list from `playtime_recomputed.json → share_of_play_time_typical` (backend spec §6; `tools/playtime_recompute.py:171`) |
| Designer questions | `D10_designer_questions.md`: at most five, ranked, each with the measured difference from D5 or D8 (`00a:115-116`); `headline.json → designer_questions` with `rank`, `question`, `measured_difference`, `source_arm_ids` (`00e:136-143`) | Validator check H8 enforces at most 5, ranks 1..n and known arm ids (`tools/check_outputs.py:977-985`) |
| Run log (model) | The last line of the final message: `RUNLOG: phases=<n> interpretations=<n> games_simulated=<n> files_failed=<none or list> files_written=<list>` (`00a:146-150`); `run_manifest.json → simulation_ledger` and `totals` (`00b:140-150`) | Validator section 9 compares it with the manifest and the file list (`tools/check_outputs.py:1124-1162`). Luc's pipeline reads it from the stream's `result` event (`backend/app/pipeline.py:104-109`) |
| Run log (operator) | A table filled in by hand (`AB_prompt_instruments_v5.2.md:268-281`) | Partly replaced by `_check/AFTER_RUN.md` |
| Session log | `RUN_ID.jsonl`, exported with `operator/RUN-END.md` | Kept for every run, client runs included (`AB_prompt_instruments_v5.2.md:17,261-262`) |

## 4. Instructions that assume the Claude app

| # | Instruction (quoted) | Location | What the environment note must say instead |
|---|---|---|---|
| 1 | "There is no other message: everything you need is in the attached files." | `system/00a_START_HERE.md:2-3` | The "attached files" are the files in the working directory. |
| 2 | "Three kinds of file can be attached." / "All of them are optional." / "every other attached file" | `system/00a_START_HERE.md:6,21,30` | Name what is in the working directory: the eight `00` files, the `01` files present, and the game material. Luc's note says "the two 01 files" (`backend/app/pipeline.py:22-23`). For v5.2 it must allow up to four `01` files plus game material. |
| 3 | "Read every attached file in full from disk (its path is given with the attachments)." | `system/00a_START_HERE.md:46-47` | The files are in the current working directory. No paths come with an upload. |
| 4 | "Do not ask questions and do not stop for confirmation: nobody will reply until you have finished." | `system/00a_START_HERE.md:56-57` | This is true for a run that does not wait. It conflicts with steering at checkpoint B (see the ticket on where analysis breaks for checkpoint B). |
| 5 | "Do not load skills or plugins, search the web, read or write past conversations or project documents, or use connected apps or devices." | `system/00a_START_HERE.md:61-63` | No change to the text is needed. The session options must enforce it. Luc uses `--safe-mode`, `--strict-mcp-config`, `--no-chrome`, `--disable-slash-commands` and `--tools Bash,Read,Write,Edit` (`backend/app/pipeline.py:34-44`). |
| 6 | "Check them and deliver them as `00b_output_contract.md` §3 describes." | `system/00a_START_HERE.md:144-145` | A file counts as delivered once it is in `out/` in the working directory. |
| 7 | "`files_failed` lists any file still undelivered after three attempts, or `none`." | `system/00a_START_HERE.md:149-150` | Report `files_failed=none` unless a file is missing from `out/`. |
| 8 | "how you check and deliver them" | `system/00b_output_contract.md:5-6` | Same as row 6. |
| 9 | "Scratch and working files may live elsewhere; they are not outputs and are not sent." | `system/00b_output_contract.md:16` | Keep scratch files outside `out/`. Nothing may land in `out/` by accident: importing an engine creates a `__pycache__` folder, so Luc sets `PYTHONDONTWRITEBYTECODE=1` (`backend/app/pipeline.py:97-99`). |
| 10 | "Deliver at the end, in batches, in the order of §1. Do not send files at any other time." | `system/00b_output_contract.md:78-80` | There is no delivery tool and no send. Skip §3.2. |
| 11 | "After each send, compare the delivery tool's report with the files you sent. … at most three attempts" | `system/00b_output_contract.md:81-83` | Skip §3.3. |
| 12 | "In the final message, list every file that needed more than one attempt … `files_written` lists exactly the file names in §1, in that order." | `system/00b_output_contract.md:84-87` | Keep the `files_written` rule of §3.4, because the validator checks the order (`tools/check_outputs.py:1145-1162`). There are no attempts to list. Luc's note says "skip the sends of §3.2 to §3.4" (`backend/app/pipeline.py:24-25`), which also drops this rule. Skip §3.2 and §3.3 only. |
| 13 | §3.1 "Check before delivering." | `system/00b_output_contract.md:67-77` | Keep. It checks `out/` and works the same in a working directory. |
| 14 | (no runtime statement) | none | Say that `python3` is on the PATH, with the standard library only, as Luc's note does (`backend/app/pipeline.py:26`). The kit does not say whether the app sandbox has `numpy` [not verified]. |

Operator files and procedure that apply only to the app:

| Item | Quote | Location | Backend replacement |
|---|---|---|---|
| `operator/RUN-END.md` | "Run this code exactly, then send me the file it prints as a downloadable file." | `operator/RUN-END.md:2` | Not needed. The session log is already on disk (the code reads `~/.claude/projects/*/*.jsonl`, line 8). The backend copies it and removes the thinking blocks itself (backend spec §8). |
| `operator/RESEND.md` | "These files did not arrive: FILE_NAMES" | `operator/RESEND.md:1-2` | Not needed when the model writes straight to disk [not verified in a run]. A missing file is a validator FAIL. |
| `operator/CONTINUE.md` | "The run was interrupted by a usage limit. Continue the task from where it stopped." | `operator/CONTINUE.md:1` | Resume the same session with the SDK option `resume`; the backend spec calls this "a retry of the request" (§3). |
| Procedure §3 B-E | "Drag in all files …", "Leave the prompt box empty", "Check the file cards, then download" | `AB_prompt_instruments_v5.2.md:205-250` | The backend copies the files into the working directory and starts the session with a fixed prompt. Luc uses "Read 00a_START_HERE.md and follow it." (`backend/app/pipeline.py:33`). The spec says to keep the request free of other text, or to record the difference as a version change (§8). |
| Isolation §1.4 | "use the empty 'Analysis' project (0 docs); memory and past-chat search off; all skills off" | `AB_prompt_instruments_v5.2.md:80-84` | Session options, as in row 5. |

Tools that depend on the app transcript:

- `tools/usage_extract.py` cuts the transcript at the last human message that contains "RUN-END" (`tools/usage_extract.py:47,101`). Without that message it warns and counts the whole file (line 183). It reads the reported cost from `cost-state` rows (line 143) and warns if there are none (line 268). Whether an SDK session log has `cost-state` rows is not verified.
- `usage_extract.py` flags any tool name that matches `Skill|memory|Projects|…` as contamination (`tools/usage_extract.py:50-51,209-211`).
- `tools/after_run.py` undoes browser renames such as ` (1)` and unpacks "Download all" zips (`tools/after_run.py:33,61-114`). With the output on disk, the backend can run `check_outputs.py` on `out/` directly, as Luc does (`backend/app/pipeline.py:105-109`).

### 4.1 Draft environment note for v5.2

Based on Luc's note (`backend/app/pipeline.py:19-27`), with the fixes from rows 2, 12 and 14:

```text
You run in Claude Code, not in a chat. The files the brief calls attached are the files in the
working directory: the eight 00 files, any 01 files (01_rules.txt, 01_components.json,
01_timings.json, 01_focus.json) and any game material. Read them from there. Write out/ in the
working directory. There is no delivery tool: a file is delivered once it is in out/. Do the final
check of the output contract's §3.1, skip §3.2 and §3.3, and in the RUNLOG report
files_failed=none unless a file is missing and files_written as §3.4 says. python3 is on the PATH,
with the standard library only.
```

Not verified: no v5.2 run with an environment note exists. Luc's pipeline ran v5.

## 5. Facts for the neighbour tickets

- Luc's extraction changes: his pipeline copies `results/rules.txt` and `results/components.json` to `01_rules.txt` and `01_components.json` (`backend/app/pipeline.py:18,95-96`).
- How extraction results and designer numbers become analysis input: the targets and player counts have no input file and sit in the hashed brief (section 2.3). `01_timings.json` and `01_focus.json` have fixed schemas. The kit reads no game model file; the only upstream files are `01_rules.txt` and `01_components.json` (`tools/check_outputs.py:85`).
- Where analysis breaks for checkpoint B: the brief demands one turn with no questions (`system/00a_START_HERE.md:56-57`). D9, D10 and D11 come after the simulation batches D4 to D8, and D10 and D11 use D5 and D8 results (`system/00a_START_HERE.md:80-119`).

## 6. Not verified

- No v5.2 run in Claude Code or the Agent SDK. The draft note is untested.
- `tests/make_fake_run.py` and `tests/mutation_tests.py` were not run (DevBox has no `numpy`).
- Whether an SDK session log has `cost-state` rows for `usage_extract.py`.
- Whether the API send order has an effect, given that `00a` sets the reading order.
