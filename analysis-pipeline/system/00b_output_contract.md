# Output contract
Output contract v2.3.

This file fixes which files you write, what they are called, how they are packaged, which
names are used inside them, and how you check and deliver them. It works together with
`00c_reporting_standard.md` and `00d_stat_definitions.md`. Where any of them disagree, this file
wins. A program reads your outputs, so follow the names and formats exactly.

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
| 5 | `D01_rules_dossier.md` | Markdown | D1. On the extraction path, its components table comes from `01_components.json` |
| 6 | `D01_board_layout.json` | JSON | the board read from the material, or `null` when the material has no layout |
| 7 | `D02_engine_v<n>.py` | Python | one file per engine version from v1 up that is listed in the manifest (`D02_engine_v1.py`, `D02_engine_v2.py`, …). Each file is complete and runs on its own. Development builds (`v0`) are not delivered |
| 8 | `D02_run.py` | Python | re-runs any ledger batch from the command line, e.g. `python D02_run.py --engine v2 --purpose D5 --players 3 --seed-from 500001 --seed-to 501000` |
| 9 | `D03_playtime_model.md` | Markdown | D3: the duration table in readable form, its assumptions, and where each value came from |
| 10 | `D03_duration_table.json` | JSON | the duration table as data (§7) |
| 11 | `D04_single_vs_batch.md` | Markdown | D4 |
| 12 | `D05_playtime.md` | Markdown | D5 |
| 13 | `D06_game_statistics.md` | Markdown | D6, including the focus items (§8) |
| 14 | `D07_self_audit.md` | Markdown | D7 |
| 15 | `D08_exploits_and_rulebook_audit.md` | Markdown | D8 |
| 16 | `D09_limitations.md` | Markdown | D9 |
| 17 | `D10_designer_questions.md` | Markdown | D10 |
| 18 | `D11_data_needed.md` | Markdown | D11 (§7.4) |
| 19 | `per_game_D04.jsonl.zip` | zipped JSON Lines | every D4_logged and D4_batch game |
| 20 | `per_game_D05.jsonl.zip` | zipped JSON Lines | every D5 game, all player counts |
| 21 | `per_game_D07.jsonl.zip` | zipped JSON Lines | every D7_rerun game |
| 22 | `per_game_D08.jsonl.zip` | zipped JSON Lines | every D8_baseline and D8_arm game |
| 23 | `per_game_other.jsonl.zip` | zipped JSON Lines | every test and debug game |
| 24 | `events_D04.jsonl.zip` | zipped JSON Lines | event log, all D4 games |
| 25 | `events_D05.jsonl.zip` | zipped JSON Lines | event log, all D5 games |
| 26 | `events_D07.jsonl.zip` | zipped JSON Lines | event log, all D7_rerun games |
| 27 | `events_D08.jsonl.zip` | zipped JSON Lines | event log, the first 100 games (lowest seeds) of each D8 baseline and of each arm |

## 2. Formats and packaging
1. **Zip is the only packaging, and each zip holds exactly one file.** `X.jsonl.zip` contains one
   member called `X.jsonl` at its root: no folders, no other members. Use DEFLATE compression.
   Only files 19–27 are zipped. Nothing else is zipped, and files are never bundled together.
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
5. No other file formats: no CSV, spreadsheets, images, HTML, PDF or notebooks.

## 3. Final check and delivery
1. **Check before delivering.** When every file is final, confirm all of these, fix anything that
   fails, and only then deliver:
   - every file in §1 exists in `out/` with its exact name, and there are no other files;
   - no Markdown or Python file is empty;
   - every JSON file parses as strict JSON (no `NaN` or `Infinity`);
   - every zip opens, holds exactly one member named as in §2, and that member's line count
     equals its `records` value in the manifest;
   - every D5 game's `play_min` on the low, typical and high clocks equals the sum over its
     events of the duration rows they were charged to (§7.2);
   - the manifest's `files` list (§6) was computed after every other file was final, and its
     sizes and SHA-256 values match the files.
2. **Deliver at the end, in batches, in the order of §1.** Do not send files at any other time.
   - First send: every file that is not a zip (files 1–18, with all engine files at row 7).
   - Then each zip (files 19–27) in a send of its own.
3. **Compare and retry.** After each send, compare the delivery tool's report with the files you
   sent. Send any file reported as not delivered again, on its own. Each file gets at most three
   attempts in total. Never resend a file reported as delivered.
4. **Report the delivery.** In the final message, list every file that needed more than one
   attempt, with its number of attempts and the outcome. The RUNLOG's `files_failed` lists every
   file still undelivered after three attempts, or `none`. `files_written` lists exactly the file
   names in §1, in that order.

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
| `outcome_mode` | `competitive` (players win or lose against each other), `cooperative` (all players win or lose together), `no_winner` (the game has no winner or loser) |
| `team_result` (cooperative only) | `win`, `loss` |
| `level` | `G`, `P`, `R`, `T`, `E`, `agg` |
| `verdict` (headline) | `short` (median below target − tolerance), `on_target`, `long` (median above target + tolerance) |
| `d1_source` (manifest) | `extraction` (built from `01_rules.txt` and `01_components.json`), `raw` (built from the game material) |
| `duration_category` | `setup`, `teardown`, `turn_admin`, `move`, `draw_card`, `resolve_card`, `decide`, `random_device`, `token_handling`, `board_change`, `round_end`, `scoring`, `other` (definitions in §7.1) |
| `per` (duration rows) | `event` (once per event), `step` (per step or tile of a move), `player` (per player at the table), `item` (per card, token or piece handled) |
| `value_source` (duration rows) | `provided` (from `01_timings.json`), `inferred` (assumed, then scaled from provided values, §7.3), `assumed` (the run's own estimate, no data) |
| `focus_chosen_by` | `input` (named in `01_focus.json`), `run` (chosen by the run) |
| `focus_outcome_metric` | `win_share`, `team_success`, `mean_score` |
| `game_id` | `<purpose>/<engine_version>/<player_count>p/<seed>`; for D8: `<purpose>/<engine_version>/<arm_id>/<seed>` |

### 4.2 Names of game things
This covers vocabulary entries, roles, statistic parameters, event types and readings.
1. Lowercase ASCII `snake_case`.
2. **Take the name from the rulebook, word by word, in the same order:** "Monster Rush" →
   `monster_rush`. Never reorder, abbreviate or invent a name. If the rulebook uses more than one
   name for the same thing, use the name in its component list. If the thing is not in the
   component list, use the first name the rules text gives it. On the extraction path, the
   component list is `01_components.json`.
3. One name per thing. Declare every name once in `run_manifest.json → vocabulary`, with a
   one-line description.
4. Use only these vocabulary categories: `roles`, `abilities`, `resources`, `sources`, `causes`,
   `decks`, `cards`, `zones`, `entity_classes`, `npcs`, `hazards`, `goals`, `phases`,
   `action_types`, `event_types`, `readings`, `strategies`.
5. **Exception to rule 1:** in `readings` and `strategies`, the keys are the ids fixed in §4.1 and
   the dossier, with their upper case: interpretation ids `I<n>`, reading arm ids `R-I<n>[a-z]`,
   strategy arm ids `S<n>`.
6. Statistic labels are `family:param1:param2`, as in the statistics definitions.

### 4.3 Records
- Every per-game record follows `00h_template_per_game.json` and carries `game_id`, `seed`,
  `engine_version`, `purpose`, `player_count`. D8 records also carry `arm_id`, `arm_kind` and
  `focal_seat` (the seat playing the strategy, or `null` for a reading arm).
  `outcome.end_condition` and `outcome.mode` use §4.1.
- `game_id` is unique in every per-game file except `per_game_other.jsonl.zip`, where test and
  debug batches that re-run the same seeds may repeat ids.
- Every event record carries `game` (that game's `game_id`) and `dur` (§7.2).

### 4.4 Simulation ledger entries
Each entry in `run_manifest.json → simulation_ledger` has exactly these keys, and no others:
`purpose`, `arm_id`, `arm_kind`, `engine_version`, `player_count`, `seed_from`, `seed_to`,
`games`, `new_or_rerun`, `per_game_file`, `events_file`, `logged_games`, `note`.
Use `null` where a key doesn't apply. `note` is one sentence or `null`.
- **Every game you simulate is in the ledger and has a per-game record**, including quick tests
  and interactive checks: use purpose `test` or `debug` and `per_game_other.jsonl.zip`. A batch
  in the ledger with fewer records than games is a contract breach.
- **One D8 baseline per engine version.** If D8 arms run on more than one engine version, run the
  baseline (arm `B0`) on each of those versions, on the same seeds, and pair each arm with the
  baseline of its own version.

### 4.5 Outcome by mode
| `outcome.mode` | `winner_seats` | `tie` | `team_result` | Headline outcome |
|---|---|---|---|---|
| `competitive` | the winning seats | true if more than one | `null` | win shares by seat and role |
| `cooperative` | every seat if the team won, `[]` if it lost | `false` | `win` / `loss` | `team_success_share`; seat and role win shares empty |
| `no_winner` | `[]` | `false` | `null` | mean score (if the game scores); win shares empty |

## 5. headline.json
This is the file the results screen reads first. Fill every key in `00e_template_headline.json`,
keep the key names and order, and add no keys. Game-specific names (roles, event types) appear
only as values and follow §4.2.
- `rulebook_file`: the rulebook's file name; on the extraction path, `01_rules.txt`.
- `playtime` and `outcome`: one entry per player count, computed from the D5 games.
- Percentiles use linear interpolation between order statistics (numpy's default). Shares are
  0–1.
- Win shares split ties equally between the tied winners. `ci95` is a 95% interval. `fair` is
  1 ÷ players (seats), or the share expected for the role. Cooperative and no-winner games leave
  the seat and role lists empty (§4.5).
- `players_with_zero_score_per_game_mean` and `players_reaching_zero_lives_per_game_mean` are the
  per-game counts from the per-game records, averaged over games; `null` where the game has no
  score or no lives.
- `timings`: the summary of §7.3.
- `focus_items`: §8.
- `d8_arms`: one entry per arm, baseline excluded.
  - `score_diff` for a `strategy` arm: the focal player's score minus the same seat's score in the
    baseline game with the same seed and engine version, averaged over pairs.
  - `score_diff` for a `reading` arm: the mean score per player minus the baseline's, same seeds
    and engine version.
  - `win_diff_pp`: the same for win share (team success for cooperative games), in percentage
    points; `null` for `reading` arms.
  - `significant` is `true` when the `score_diff` ci95 excludes 0.
- `designer_questions`: at most five, in rank order.
- The same numbers in `summary.json` must agree with `headline.json`.

## 6. File list in the manifest
`run_manifest.json` gets a top-level array `files`. It has one entry per file in §1 other than
the manifest itself: `{"name": …, "bytes": …, "sha256": …, "records": …}`.
- `bytes` and `sha256` are of the file as written (for a zip, the zip file).
- `records` is the line count of the JSON Lines member for zipped files, and `null` otherwise.

Compute these after all other files are final.

## 7. Durations and playtime
### 7.1 Duration categories
Every row of the duration table belongs to exactly one category. A person timing a real game can
time a category without knowing how the simulation names its events.
| Category | What a person times |
|---|---|
| `setup` | preparing the game before the first turn |
| `teardown` | packing up after the game |
| `turn_admin` | starting a turn, passing to the next player, checking whose turn it is |
| `move` | moving a piece (use `per: step` for the part that grows with distance) |
| `draw_card` | taking a card from a deck |
| `resolve_card` | reading a card and carrying out what it says |
| `decide` | choosing between options, including discussion between players |
| `random_device` | rolling dice, flipping a coin, spinning |
| `token_handling` | placing, taking or moving tokens, chips, markers |
| `board_change` | shifting, rotating, swapping or removing parts of the board |
| `round_end` | the steps at the end of a round |
| `scoring` | counting points, final scoring |
| `other` | anything that fits no category; say what in `note` |

### 7.2 The table as data, and how events use it
`D03_duration_table.json` is an object:
```json
{"schema": "duration_table_v1", "timings_file": "01_timings.json or null",
 "rows": [{"id": "<vocabulary name>", "category": "<duration_category>", "per": "<per>",
           "in_play": true, "low_s": 0, "typical_s": 0, "high_s": 0,
           "value_source": "<value_source>", "assumed": {"low_s": 0, "typical_s": 0, "high_s": 0},
           "note": "<one line or null>"}],
 "scale_factors": {"low": 1.0, "typical": 1.0, "high": 1.0}}
```
- `id` is a name declared in the vocabulary. `in_play` is `false` only for time outside play
  (setup, teardown); play time counts `in_play` rows only.
- `assumed` always holds the run's own estimate, even when a provided value replaced it.
- **Every event record carries `dur`:** `{"row": "<row id or null>", "n": <multiplier>}`. `row` is
  the duration row the event was charged to (`null` if the event takes no time). `n` is how many
  times the row's value applies: 1 for `per: event`, the steps, players or items otherwise.
- **The clocks follow from the table:** for every game, `play_min` on the low, typical and high
  clocks equals the sum over its events of `n × <row value>` for `in_play` rows, divided by 60.
  The sampled clock draws each event's duration from triangular(low, typical, high).

### 7.3 Provided timings (`01_timings.json`, optional)
When a file `01_timings.json` is attached, it holds measured human times for some categories
(template: `min_s`, `max_s`, optional `typical_s`, per category), and optionally observed real
sessions. Apply it in this order, and record every value's source:
1. **Provided categories.** For each category in the file, its rows become
   `value_source: provided`. Scale each of its rows' assumed values by one factor per clock, chosen
   so the category's average time per occurrence over the D5 games equals the provided value
   (`min_s` for low, `typical_s` or the midpoint for typical, `max_s` for high). Relative
   differences between rows are kept. A one-row category charged once per occurrence therefore
   takes the provided values exactly. A category never charged in the D5 games takes them as they are.
   **A provided value is per occurrence**, as a person times it at the table: one occurrence is
   one player action (all events sharing an `action_id`, such as a move and its steps) or, for an
   event without an `action_id`, the event itself. The category's average is its total time on
   the D5 games divided by its number of occurrences.
2. **Inferred categories.** For every category not in the file, multiply the assumed values by the
   scale factor of each clock: provided time ÷ assumed time, both summed over the D5 games for the
   provided categories. These rows become `value_source: inferred`. Only `in_play` categories
   count for the factors (setup and teardown say little about play speed). With no provided
   `in_play` category, the factors are 1 and the other rows stay `assumed`.
3. **Sessions.** Observed sessions are not applied to the clocks. Report each next to the
   simulated median for its player count, with the ratio observed ÷ simulated.
4. Record the result in `D03_duration_table.json` (`value_source`, `assumed`, `scale_factors`),
   in `headline.json → timings`, and in D11.

### 7.4 D11: data needed
`D11_data_needed.md` tells the client which real data would make the results more accurate. It
holds, in this order:
1. **What was used:** the provided categories with their values, and the observed sessions, or a
   line saying none were supplied.
2. **What was assumed or inferred:** every category with `assumed` or `inferred` values, its
   values, and its **share of D5 play time** (typical clock, all player counts). Rank by share,
   largest first: timing those first improves the estimate most.
3. **Where it is recorded:** `D03_duration_table.json` (row level), `headline.json → timings`
   (summary), and this file.
4. **What else can be supplied,** in a form the client can fill in: a filled `01_timings.json`
   (any subset of categories), observed sessions per player count (play minutes, setup minutes,
   whether it was a first play), and the designer questions in D10.

## 8. Focus items
Focus items are the 1–3 game elements the gameplay revolves around (for example the player
characters, a central deck, or a shared track). They are the headline playability statistics.
- If `01_focus.json` is attached, use the items it names (`focus_chosen_by: input`).
- Otherwise choose 1–3 yourself (`focus_chosen_by: run`) and give a one-line reason with a tag.
- Every focus item is a declared vocabulary name with **options** (the values it can take, such as
  each character). For each player count and each option, report from the D5 games:
  - `outcome`: the option's outcome on `focus_outcome_metric` (win share for competitive games,
    team success when the option is present for cooperative games, mean score for no-winner
    games), with its 95% CI;
  - `use_per_player_turn`: how often the option's player uses it, per player turn (`null` if the
    option is not something a player uses);
  - `idle_share`: the share of turns in which the option had no legal use (`null` as above).
  - `spread` per player count is the largest option `outcome` minus the smallest.
