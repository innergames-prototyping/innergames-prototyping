# check_outputs.py: what it does and how to use it
Project Pipeline / InnerGames. Validator version 1.4 (2026-11-19), for output contract v2.3
(`00b_output_contract.md` in `v5.1\system\`) and brief v5.1.

**You normally don't run it yourself:** `AFTER_RUN.bat` (or `tools\after_run.py`) runs it for
you on a clean copy of the newest run, with the RUNLOG filled in. This page explains what it
checks and how to run it by hand if you need to.

**What changed in v1.4:**
- **F2** now requires 26 fixed files: `D03_duration_table.json` and `D11_data_needed.md` are new.
  **F3** names PDFs and Office files as extras (Run13 delivered a `README.pdf`).
- **M1c** also checks `run.user_input_files` (the optional `01_timings.json`, `01_focus.json`).
- **M1b** fails when RUN-END or RESEND was uploaded as game material, or when game material
  arrived inside a zip or a folder (both happened in Run13).
- **P1** allows repeated test ids in `per_game_other` only (Run12 re-ran test seeds), and checks
  `outcome.mode` on every record, with `team_result` for cooperative games.
- **P2** still compares the ledger with the records; Run13's 801 test games without records now
  fail here for the right reason.
- **S1 / H7:** one D8 baseline **per engine version**; arms are paired by seed *and* engine version
  (Run12 ran arms on two versions).
- **H1b:** `schema` must be `headline_v2`. **H4** handles cooperative and no-winner games.
  **H8** accepts any declared vocabulary name in the duration table and checks its category and
  value source. **H9 (new):** focus items.
- **Section 10 (new), Durations:** D1 table structure; D2 headline matches the table; D3 the
  timings summary matches the table; D4 every event carries `dur` and every D5 game's play time is
  reproduced from its events.

## 1. What it is, in one paragraph
`check_outputs.py` is a small Python program that inspects one run's output folder and tells you
whether the run followed the output contract. It checks four things:
1. that the right files are there with the right names, packaged the right way;
2. that the fixed names inside them are used;
3. that the counts add up;
4. that the numbers in `headline.json` (the file the UI will read) can be rebuilt from the raw
   per-game data.

It prints a list of checks, each marked PASS, FAIL, WARN or SKIP, and ends with one line:
`RESULT: PASSED` or `RESULT: FAILED`. It only reads; it never changes, moves or creates anything
in the folder it checks.

What a PASS means: the run's files are complete and consistent, so the UI can load them safely.
It does **not** mean the analysis is correct. That stays your grading job (§7).

## 2. What you need
- Python 3.8 or newer (`py --version` in PowerShell prints `Python 3.x`).
- Nothing else. The script uses only Python's built-in modules.

## 3. Setting it up (once)
Nothing to set up beyond the v5.1 folder layout: `tokens\v5.1\` next to `tokens\runs\`, one
folder per run in `runs\`, every download straight into it. `after_run.py` builds the clean
`_check\out\` copy the validator needs, so you never sort files by hand.

## 4. Running it
**Normal use:** double-click `AFTER_RUN.bat` in the v5.1 folder. It finds the newest run folder,
undoes browser renames, finds the RUNLOG in `RUN_ID.jsonl`, runs this validator and writes
`_check\check.txt`, `_check\check.json` and `_check\AFTER_RUN.md`.
To check a different run, drag its folder onto `AFTER_RUN.bat`.

**By hand** (PowerShell opened in the v5.1 folder: in File Explorer, click the address bar, type
`powershell`, Enter):

| What you want | Command |
|---|---|
| Check the newest run, the normal way | `py tools\after_run.py` |
| Check run 14 (by number or part of its name) | `py tools\after_run.py 14` |
| Quick check, skipping the large event logs | `py tools\after_run.py --skip-events` |
| The validator alone on any folder | `py tools\check_outputs.py <folder>` (add `--runlog "<line>"`, `--json <file outside the folder>`, `--skip-events`) |

**Run time:** the fake run (6,621 records, 271,136 events) takes about 2 s; Run13 (14,249
records, events included) takes under a minute [C].

**Exit codes:** 0 = no failures (warnings allowed); 1 = at least one failure; 2 = the checker
couldn't run (it says why and that the result is incomplete).

## 5. Reading the output
Each line looks like `[FAIL] F3  extra file: 'REPORT (1).md'`, followed by a `fix:` hint where
the script can tell what went wrong.
- **PASS:** checked and passed. **FAIL:** the run broke the contract. **WARN:** worth a look,
  not a breach. **SKIP:** couldn't be checked (usually a missing file); a SKIP is never a pass.

**Read from the top.** One root problem often causes several failures further down: a missing
`per_game_other.jsonl.zip` fails F2 and also P2 (ledger vs records). Fix the first failure in
each section, then run the check again.

## 6. Every check, in order
### Section 1: Files
| ID | Checks |
|---|---|
| F1 | No subfolders in `out\` |
| F2 | All 26 fixed-name files are present, with exact names (v1.4: `D03_duration_table.json`, `D11_data_needed.md`) |
| F2e | At least one `D02_engine_v<n>.py` |
| F3 | No files other than the contract's; names the likely cause (browser copy, wrong case, bundle zip, archive type, PDF or Office file) |

### Section 2: Text files
| ID | Checks |
|---|---|
| T1 | Every Markdown and Python file is UTF-8 and not empty |
| T3 (WARN) | Windows line endings |
| T4 | `REPORT.md` is under 1,200 words |

### Section 3: JSON files
| ID | Checks |
|---|---|
| J1–J4 | `run_manifest.json`, `headline.json`, `summary.json`, `D01_board_layout.json` are strict JSON (no `NaN`/`Infinity`) |

### Section 4: Manifest
| ID | Checks |
|---|---|
| M1 (WARN) | No `run_id` or `condition` field |
| **M1c** | `run.d1_source` is `extraction` or `raw`. On `extraction`, `upstream_files` lists `01_rules.txt` (and `01_components.json`); on `raw`, it is empty. `user_input_files` lists only `01_timings.json` / `01_focus.json` |
| **M1b** | `run.game_material_files` lists the game material, with no `00` or `01` file, no operator file (RUN-END, RESEND) and nothing inside a zip or folder. Empty is allowed only on the extraction path |
| M2 | Every ledger entry has exactly the 13 fixed keys |
| M3 | Ledger values use the fixed strings |
| M4 | `totals` = the ledger sums |
| M5 / M5b | One engine file per declared version; the ledger uses only declared versions |
| M6 | Vocabulary uses only the 17 fixed categories |
| **M7** | Vocabulary names are lowercase snake_case, except ids in `readings` (`I<n>`, `R-I<n>[a-z]`) and `strategies` (`S<n>`) |
| M8 (WARN) | The same name in two categories |
| M9 | The `files` list names every delivered file |
| M10 | Each file's size, SHA-256 and record count match the list |

### Section 5: Per-game data
| ID | Checks |
|---|---|
| Z1–Z5 | Readable zip; one member named like the zip at the root; DEFLATE (WARN); not truncated; every line valid JSON |
| **P1** | `game_id` unique (repeats allowed in `per_game_other` only), well-formed and consistent; fixed strings incl. `outcome.mode`; cooperative games carry `team_result` and agree with `winner_seats`; D8 arm fields; purposes in the right file |
| P2 | Ledger vs records, batch by batch: every simulated game has a record, test and debug games included |
| P3 | Every seed lies inside its ledger batch's range |

### Section 6: Sample sizes
| ID | Checks |
|---|---|
| **S1** | D4 = 1 + 1,000; D5 = 1,000 per player count; D7 = 1,000 (1,001 WARN); D8 = 400 per baseline and 400 per arm, each arm on the seeds of the baseline of **its own engine version** |

### Section 7: Event logs
| ID | Checks |
|---|---|
| Z1–Z5 | As above |
| E1 | Every event has `game` and `type` (`dur` is checked in section 10) |
| E2 | No events for games that don't exist |
| E3 | Events for every D4, D5 and D7 game, and for the 100 lowest-seed games of the D8 baseline and each arm |

### Section 8: headline.json
| ID | Checks |
|---|---|
| H1 / **H1b** | Top-level keys exactly as in the template (v2 adds `timings`, `focus_items`); `schema` = `headline_v2` |
| H2 / H3 | Player counts, targets, `games_executed` and final engine version match the manifest |
| **H4** | Playtime and outcome per player count **recomputed from the D5 games**, and agreement with `summary.json`. Competitive: seat and role win shares. Cooperative: `team_success_share`, empty seat/role lists. Mode matches the records |
| H5 | D4 single game and batch percentiles match the D4 records |
| H6 | D7 before/after medians match; gaps found = fixed + unfixed |
| **H7** | D8 arms match the per-game data; `significant` agrees with the CI; score (and, for strategy arms, win or team-success) differences recomputed from pairs with the same seed and engine version |
| **H8** | Interpretation ids and tags; at most 5 designer questions, ranked; cited arms exist; duration table rows declared in any vocabulary category, with a fixed `category` and `value_source` |
| **H9** (new) | 1–3 focus items; each a declared name; `chosen_by` `input` or `run` with a reason; `outcome_metric` fits the outcome mode; every `spread` = largest − smallest option outcome |

Recompute rules: percentiles by linear interpolation (numpy's default); ties split wins equally;
tolerances are rounding only (minutes ±0.011, shares ±0.0025, points ±0.011, win difference ±0.11 pp).

### Section 10: Durations (new)
| ID | Checks |
|---|---|
| D1 | `D03_duration_table.json`: schema, unique row ids, declared names, fixed `category`, `per` and `value_source`, 0 ≤ low ≤ typical ≤ high, `assumed` values kept, `scale_factors` present |
| D2 | `headline.duration_table` has the same rows and values as the table |
| D3 | `headline.timings` lists the same provided / inferred / assumed categories and scale factors as the table; `timings_file` set only when something was provided |
| D4 | Every event carries `dur {row, n}` with a known row, and every D5 game's low, typical and high `play_min` equals the sum of its events' durations (contract §7.2) |

### Section 9: RUNLOG (only with `--runlog`)
| ID | Checks |
|---|---|
| L1 | `games_simulated` equals the manifest total |
| L2 | `files_written` lists exactly the contract's files, in order (wrong order = WARN) |
| **L3** | `files_failed` is present; `none` passes; any listed file fails, because it never reached you |

## 7. What it does **not** check
- **Whether the analysis is right.** A wrong tile mix or a missed exploit passes. Grading stays
  with you.
- **Whether delivery reached you.** The validator sees only the folder you made. In Run11 the
  run's delivery tool reported five files as sent that never appeared in the chat. Count the
  downloaded files against `files_written` yourself (instruments §3, step D2).
- The text of the Markdown deliverables (D11 included), `summary.json` beyond the D5 playtime and
  the strategy list, statistic labels, event content beyond `game`, `type` and `dur`, and the CI
  values themselves.
- Whether the duration values are realistic. D4 proves the clocks follow from the table, not that
  the table is right. That is what Arjen's timings and `playtime_recompute.py` are for.
- Whether the engines and `D02_run.py` run. It never executes code from a run, by design.
- **Runs before v5.1.** Run12 and Run13 fail F2, M1c, P1 (`outcome.mode`), H1/H1b, H8 and H9
  because those files and fields didn't exist yet. That shows the contract changed, not that the
  runs broke it.

## 8. How it was tested (2026-11-19) [C]
- **Three synthetic runs** written exactly to contract v2.3 (6,621 games, 271,136 events each):
  raw competitive, extraction competitive, raw cooperative. All **PASSED**, 51 checks, 0 failures.
- **58 deliberate breakages**, one at a time (`tests/mutation_tests.py`): the 35 from v1.3 plus 23
  new ones, among them D11 or the duration table missing, a PDF in the folder, an unknown
  category, headline vs table mismatch, events without `dur`, one game's play time off by a
  minute, a duplicate id in a main batch, more test games ledgered than recorded, a D8 arm on an
  engine without its own baseline, `outcome.mode` missing, four focus items, a wrong spread,
  RUN-END or a zip listed as game material, and three cooperative-game errors. **All 58 caught**
  with the expected ID; one allowed case (repeated test ids in `per_game_other`) passes.
- **Real runs:** Run12's v1.3 failures from instrument ambiguity (duplicate test ids, dual
  baselines, vocabulary category) are gone. Run12 and Run13 fail only on the new v2.3 items, and
  Run13 also on its real problems (missing engine files, README.pdf, RUN-END uploaded at the start,
  test games without records).

## 9. Troubleshooting
| Symptom | Likely cause and fix |
|---|---|
| `py` is not recognised | Python isn't on PATH; reinstall with "Add python.exe to PATH", or use `python` |
| `No 'runs' folder found` | The v5.1 folder isn't next to `runs\`. Move it, or add `--runs <folder>` once |
| `matches 2 run folders` | Two folder names contain the number or text you gave; give more of the name |
| F3 failures for files ending in ` (1)` | `after_run.py` undoes these itself. If two different files share a name, its summary says which one it used |
| F2 for files the RUNLOG lists | They never reached the chat, or weren't downloaded. `_check\RESEND.md` is the filled-in message to attach, before RUN-END (instruments §3 D) |
| Z4 "damaged or truncated" | Incomplete download; download it again |
| M10 hash mismatch on one file | The file changed after the manifest, or the download is damaged; re-download first |
| "the checker itself crashed", exit 2 | A checker bug or a very unusual file; send me the error text |

## 10. If the contract changes
The fixed lists sit together at the top of the script under `# contract constants`
(`FIXED_FILES`, `PURPOSES`, `END_CONDITIONS`, `LEDGER_KEYS`, `VOCAB_CATEGORIES`, `ID_KEYS`,
`D1_SOURCES`, `UPSTREAM`, `USER_INPUTS`, `OUTCOME_MODES`, `HEADLINE_KEYS`, `EXPECTED`,
`EVENTS_D08_PER_ARM`); the duration categories sit in `tools/timings.py`. Change the contract and
these lists together, bump `VERSION`, and re-run the tests before using it on real runs:
`py tests\make_fake_run.py <empty folder>\out raw competitive` (also `extraction competitive`
and `raw cooperative`), then
`py tests\mutation_tests.py <competitive out> tools\check_outputs.py <cooperative out>`.
