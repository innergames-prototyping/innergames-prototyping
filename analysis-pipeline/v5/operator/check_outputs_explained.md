# check_outputs.py: what it does and how to use it
Project Pipeline / InnerGames. Validator version 1.3 (2026-10-26), for output contract v2.2
(`00b_output_contract.md` in `tokens\v5\system\`) and brief v5.

**What changed in v1.3:**
- **M1c (new)** checks `run.d1_source` (`extraction` or `raw`) and that it fits `upstream_files`.
- **M1b** now allows an empty `game_material_files` on the extraction path, and rejects any `00`
  or `01` file listed as game material.
- **M7** now accepts the upper-case ids in `readings` and `strategies` (`I3`, `R-I3a`, `S1`), as
  the contract's §4.2 rule 5 allows. Run11 failed this check because contract v2.1 contradicted
  itself here.
- **L3 (new)** reads `files_failed` from the RUNLOG. `none` passes; any listed file fails.

All other rules are unchanged from v1.2.

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
1. Put `check_outputs.py` in your tokens folder, next to `usage_extract.py`.
2. For each run, make a folder such as `runs\Run12_V5_PILOT\`, with `out\` inside it.
   - Put **only** the run's delivered files in `out\`.
   - Keep `RUN_ID.jsonl`, `usage.csv` and `check.json` one level up. Inside `out\` they would
     count as extra files and fail check F3.

## 4. Running it
Open PowerShell in the tokens folder and run one of these. Keep the quotes.

| What you want | Command |
|---|---|
| Standard check | `py check_outputs.py "runs\Run12_V5_PILOT\out"` |
| Also compare the RUNLOG line | `py check_outputs.py "runs\Run12_V5_PILOT\out" --runlog "RUNLOG: phases=… files_failed=… files_written=…"` |
| Save the results as JSON too | `py check_outputs.py "runs\Run12_V5_PILOT\out" --json "runs\Run12_V5_PILOT\check.json"` |
| Quick check, skipping the large event logs | `py check_outputs.py "runs\Run12_V5_PILOT\out" --skip-events` |

- **`--runlog`:** copy the whole `RUNLOG: …` line from the run's last message.
- **`--json`:** the JSON file must go **outside** `out\`.
- **Run time:** Run11 (25,801 per-game records, no event logs) took 22 s [C]. A full run with
  event logs (about 2.4 million event lines in Run11's manifest) will take longer [L].

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
| F2 | All 24 fixed-name files are present, with exact names |
| F2e | At least one `D02_engine_v<n>.py` |
| F3 | No files other than the contract's; names the likely cause (browser copy, wrong case, bundle zip, archive type) |

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
| **M1c** | `run.d1_source` is `extraction` or `raw`. On `extraction`, `upstream_files` lists the `01` files; on `raw`, it is empty |
| M1b | `run.game_material_files` lists the game material, with no `00` or `01` file among them. Empty is allowed only on the extraction path |
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
| P1 | `game_id` unique, well-formed and consistent; fixed strings; D8 arm fields; purposes in the right file |
| P2 | Ledger vs records, batch by batch |
| P3 | Every seed lies inside its ledger batch's range |

### Section 6: Sample sizes
| ID | Checks |
|---|---|
| S1 | D4 = 1 + 1,000; D5 = 1,000 per player count; D7 = 1,000 (1,001 WARN); D8 = 400 baseline and 400 per arm on exactly the baseline's seeds |

### Section 7: Event logs
| ID | Checks |
|---|---|
| Z1–Z5 | As above |
| E1 | Every event has `game` and `type` |
| E2 | No events for games that don't exist |
| E3 | Events for every D4, D5 and D7 game, and for the 100 lowest-seed games of the D8 baseline and each arm |

### Section 8: headline.json
| ID | Checks |
|---|---|
| H1 | Top-level keys exactly as in the template; `schema` = `headline_v1` |
| H2 / H3 | Player counts, targets, `games_executed` and final engine version match the manifest |
| H4 | Playtime and outcome per player count **recomputed from the D5 games**, and agreement with `summary.json` |
| H5 | D4 single game and batch percentiles match the D4 records |
| H6 | D7 before/after medians match; gaps found = fixed + unfixed |
| H7 | D8 arms match the per-game data; `significant` agrees with the CI; score (and, for strategy arms, win) differences recomputed from the paired seeds |
| H8 | Interpretation ids and tags; at most 5 designer questions, ranked; cited arms exist; duration table rows ordered and declared |

Recompute rules: percentiles by linear interpolation (numpy's default); ties split wins equally;
tolerances are rounding only (minutes ±0.011, shares ±0.0025, points ±0.011, win difference ±0.11 pp).

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
- The text of the Markdown deliverables, `summary.json` beyond the D5 playtime and the strategy
  list, statistic labels, event content beyond `game` and `type`, and the CI values themselves.
- Whether the engines and `D02_run.py` run. It never executes code from a run, by design.
- **v3/v4 runs.** Run11 (v4) fails M1c and L3 because those fields didn't exist yet. That shows
  the contract changed, not that the run broke it.

## 8. How it was tested (2026-10-26) [C]
- **Two synthetic runs** written exactly to contract v2.2 (6,621 games each), one per path:
  both **PASSED** with 0 failures, including `--runlog` (48 checks).
- **35 deliberate breakages**, one at a time: the 25 from v1.2 plus 10 new ones (`d1_source`
  missing or invalid; extraction path without upstream files; raw path with no game material; a
  `01` file listed as game material; an upper-case name outside `readings`/`strategies`; an id-style
  key in `roles`; a malformed reading id; a RUNLOG reporting an undelivered file; a RUNLOG without
  `files_failed`). **All 35 caught** with the expected ID and exit code.
- **A real run (Run11, v4):** M7 now passes; F2/P2 fail on the five files that never arrived;
  M1c and L3 fail because v4 had no such fields. All as expected.

## 9. Troubleshooting
| Symptom | Likely cause and fix |
|---|---|
| `py` is not recognised | Python isn't on PATH; reinstall with "Add python.exe to PATH", or use `python` |
| `ERROR: '…' is not a folder` | Wrong path, or missing quotes around a path with spaces |
| F3 failures for files ending in ` (1)` | Browser copies; delete or rename them |
| F2 for files the RUNLOG lists | They never reached the chat, or weren't downloaded. Check the chat before RUN-END (instruments §3 D2) |
| Z4 "damaged or truncated" | Incomplete download; download it again |
| M10 hash mismatch on one file | The file changed after the manifest, or the download is damaged; re-download first |
| "the checker itself crashed", exit 2 | A checker bug or a very unusual file; send me the error text |

## 10. If the contract changes
The fixed lists sit together at the top of the script under `# contract constants`
(`FIXED_FILES`, `PURPOSES`, `END_CONDITIONS`, `LEDGER_KEYS`, `VOCAB_CATEGORIES`, `ID_KEYS`,
`D1_SOURCES`, `HEADLINE_KEYS`, `EXPECTED`, `EVENTS_D08_PER_ARM`). Change the contract and these
lists together, bump `VERSION`, and re-run `tests/make_fake_run.py` (both paths) and
`tests/mutation_tests.py` before using it on real runs.
