# Output contract
Output contract v2.1.

This file fixes which files you write, what they are called, how they are packaged, and which
names are used inside them. It works together with `00c_reporting_standard.md` and `00d_stat_definitions.md`.
Where any of them disagree, this file wins. A program reads your outputs, so follow the
names and formats exactly.

## 1. Exact file list
Write all output files into one flat folder, `out/`, with no subfolders. Write exactly the files
below, with exactly these names (upper/lower case included), and no other output files.
- If a file has nothing to hold for this game, still write it:
  - Markdown gets one line saying why;
  - `D01_board_layout.json` gets `null`;
  - a data file gets a zip holding an empty `.jsonl` member.
- Scratch and working files may live elsewhere; they are not outputs and are not sent.

| # | File | Format | Holds |
|---|---|---|---|
| 1 | `REPORT.md` | Markdown | the final report, under 1,200 words |
| 2 | `headline.json` | JSON | the key aggregate results, exactly as in `00e_template_headline.json` (§5) |
| 3 | `summary.json` | JSON | all aggregates, as in `00f_template_summary.json`; D8 results go in `strategies`, one entry per arm, with `id` = the arm_id |
| 4 | `run_manifest.json` | JSON | as in `00g_template_run_manifest.json`, including the `files` list (§6) |
| 5 | `D01_rules_dossier.md` | Markdown | D1 |
| 6 | `D01_board_layout.json` | JSON | the board read from the photographs, or `null` |
| 7 | `D02_engine_v<n>.py` | Python | one file per engine version from v1 up that is listed in the manifest (`D02_engine_v1.py`, `D02_engine_v2.py`, …). Each file is complete and runs on its own. Development builds (`v0`) are not delivered |
| 8 | `D02_run.py` | Python | re-runs any ledger batch from the command line, e.g. `python D02_run.py --engine v2 --purpose D5 --players 3 --seed-from 500001 --seed-to 501000` |
| 9 | `D03_playtime_model.md` | Markdown | D3, including the duration table |
| 10 | `D04_single_vs_batch.md` | Markdown | D4 |
| 11 | `D05_playtime.md` | Markdown | D5 |
| 12 | `D06_game_statistics.md` | Markdown | D6 |
| 13 | `D07_self_audit.md` | Markdown | D7 |
| 14 | `D08_exploits_and_rulebook_audit.md` | Markdown | D8 |
| 15 | `D09_limitations.md` | Markdown | D9 |
| 16 | `D10_designer_questions.md` | Markdown | D10 |
| 17 | `per_game_D04.jsonl.zip` | zipped JSON Lines | every D4_logged and D4_batch game |
| 18 | `per_game_D05.jsonl.zip` | zipped JSON Lines | every D5 game, all player counts |
| 19 | `per_game_D07.jsonl.zip` | zipped JSON Lines | every D7_rerun game |
| 20 | `per_game_D08.jsonl.zip` | zipped JSON Lines | every D8_baseline and D8_arm game |
| 21 | `per_game_other.jsonl.zip` | zipped JSON Lines | every test and debug game |
| 22 | `events_D04.jsonl.zip` | zipped JSON Lines | event log, all D4 games |
| 23 | `events_D05.jsonl.zip` | zipped JSON Lines | event log, all D5 games |
| 24 | `events_D07.jsonl.zip` | zipped JSON Lines | event log, all D7_rerun games |
| 25 | `events_D08.jsonl.zip` | zipped JSON Lines | event log, the first 100 games (lowest seeds) of the baseline and of each arm |

## 2. Formats and packaging
1. **Zip is the only packaging, and each zip holds exactly one file.** `X.jsonl.zip` contains one
   member called `X.jsonl` at its root: no folders, no other members. Use DEFLATE compression.
   Only files 17–25 are zipped. Nothing else is zipped, and files are never bundled together.
2. **No other packaging:** no `.tar`, `.tar.gz`, `.tgz`, `.gz`, `.xz`, `.7z` or `.rar`.
3. **Writing a zip safely.** Stream the records straight into the zip, so no huge temporary
   file is needed:
   ```python
   import zipfile, json
   with zipfile.ZipFile("out/per_game_D05.jsonl.zip", "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
       with zf.open("per_game_D05.jsonl", "w", force_zip64=True) as f:
           for record in records:
               f.write((json.dumps(record, allow_nan=False) + "\n").encode("utf-8"))
   ```
4. Text is UTF-8 with LF line endings. JSON uses `null` for missing values, never `NaN` or
   `Infinity`.
5. No other file formats: no CSV, spreadsheets, images, HTML or notebooks.

## 3. Delivery
1. Send the files **once**, at the very end, in one delivery, in the order of the table in §1.
   Do not send files at any other time.
2. `files_written` in the RUNLOG line lists exactly the file names in §1, in that order.

## 4. Names
### 4.1 Fixed strings: use exactly these
| Field | Allowed values |
|---|---|
| `purpose` | `D4_logged`, `D4_batch`, `D5`, `D7_rerun`, `D8_baseline`, `D8_arm`, `test`, `debug` |
| `arm_kind` (D8 only) | `strategy` (one player plays differently), `reading` (an alternative reading of a rule, applied to every player) |
| `arm_id` (D8 only) | `B0` for the baseline; `S1`, `S2`, … for strategies; `R-I<n>` for an alternative reading of interpretation I<n>, with a lowercase letter when one interpretation has several alternatives (`R-I3a`, `R-I3b`) |
| `engine_version` | `v0` for every development build before v1; then `v1`, `v2`, `v3`, …, whole numbers only |
| `new_or_rerun` | `new`, `deterministic_rerun` |
| `status` | `ok`, `na`, `nm`, `ni` |
| clocks | `low`, `typical`, `high`, `sampled` |
| `end_condition` | `round_limit`, `deck_exhausted`, `goal_reached`, `all_players_out`, `elimination`, `safety_cap`, `other` |
| `level` | `G`, `P`, `R`, `T`, `E`, `agg` |
| `verdict` (headline) | `short` (median below target − tolerance), `on_target`, `long` (median above target + tolerance) |
| `game_id` | `<purpose>/<engine_version>/<player_count>p/<seed>`; for D8: `<purpose>/<engine_version>/<arm_id>/<seed>` |

### 4.2 Names of game things
This covers vocabulary entries, roles, statistic parameters, event types and readings.
1. Lowercase ASCII `snake_case`.
2. **Take the name from the rulebook, word by word, in the same order:** "Monster Rush" →
   `monster_rush`. Never reorder, abbreviate or invent a name. If the rulebook uses more than one
   name for the same thing, use the name in its component list. If the thing is not in the
   component list, use the first name the rules text gives it.
3. One name per thing. Declare every name once in `run_manifest.json → vocabulary`, with a
   one-line description.
4. Use only these vocabulary categories: `roles`, `abilities`, `resources`, `sources`, `causes`,
   `decks`, `cards`, `zones`, `entity_classes`, `npcs`, `hazards`, `goals`, `phases`,
   `action_types`, `event_types`, `readings`, `strategies`.
5. Statistic labels are `family:param1:param2`, as in the statistics definitions.

### 4.3 Records
- Every per-game record follows `00h_template_per_game.json` and carries `game_id`, `seed`, `engine_version`, `purpose`, `player_count`.
  D8 records also carry `arm_id`, `arm_kind` and `focal_seat` (the seat playing the strategy, or
  `null` for a reading arm). `outcome.end_condition` uses §4.1.
- Every event record carries `game`, which equals that game's `game_id`.

### 4.4 Simulation ledger entries
Each entry in `run_manifest.json → simulation_ledger` has exactly these keys, and no others:
`purpose`, `arm_id`, `arm_kind`, `engine_version`, `player_count`, `seed_from`, `seed_to`,
`games`, `new_or_rerun`, `per_game_file`, `events_file`, `logged_games`, `note`.
Use `null` where a key doesn't apply. `note` is one sentence or `null`. Every game in a ledger
batch appears in the per-game file it names.

## 5. headline.json
This is the file the results screen reads first. Fill every key in `00e_template_headline.json`,
keep the key names and order, and add no keys. Game-specific names (roles, event types) appear
only as values and follow §4.2.
- `playtime` and `outcome`: one entry per player count, computed from the D5 games.
- Percentiles use linear interpolation between order statistics (numpy's default). Shares are
  0–1.
- Win shares split ties equally between the tied winners. `ci95` is a 95% interval. `fair` is
  1 ÷ players (seats), or the share expected for the role.
- `players_with_zero_score_per_game_mean` and `players_reaching_zero_lives_per_game_mean` are the
  per-game counts from the per-game records, averaged over games.
- `d8_arms`: one entry per arm, baseline excluded.
  - `score_diff` for a `strategy` arm: the focal player's score minus the same seat's score in the
    baseline game with the same seed, averaged over pairs.
  - `score_diff` for a `reading` arm: the mean score per player minus the baseline's, same seeds.
  - `win_diff_pp`: the same for win share, in percentage points; `null` for `reading` arms.
  - `significant` is `true` when the `score_diff` ci95 excludes 0.
- `designer_questions`: at most five, in rank order.
- The same numbers in `summary.json` must agree with `headline.json`.

## 6. File list in the manifest
`run_manifest.json` gets a top-level array `files`. It has one entry per file in §1 other than
the manifest itself: `{"name": …, "bytes": …, "sha256": …, "records": …}`.
- `bytes` and `sha256` are of the file as written (for a zip, the zip file).
- `records` is the line count of the JSON Lines member for zipped files, and `null` otherwise.

Compute these after all other files are final.
