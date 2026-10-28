# PROMPT INSTRUMENTS v5 (DRAFT, NOT FROZEN): SINGLE only
Project Pipeline / InnerGames. Drafted 2026-10-26 from v4, after the v4 pilot (Run11) and
Korulein's review of it. Study document: **never upload this file to a test chat.** Freeze it
before the v5 pilot, and note any change made after a run has started.
Tags: [C] checked, [L] inference, [G] guess.

## 0. What changed from v4
Every change, with its reason and who decided it. "Run11" is the v4 pilot
(`AB_v4_pilot_review.md`).

### 0.1 Instruction files (`system\`)
| # | File | Change | Why | Decided by |
|---|---|---|---|---|
| 1 | `00a` | **CONTEXT rewritten.** The studio needs a complete picture of the game (components, rules, systems, balance, exploits, playtime); playtime is one part | The v4 text framed the whole job as a playtime study. Run11's report led with playtime [C] | Korulein (wording reviewed; last sentence dropped) |
| 2 | `00a` | **No outside sources:** no skills or plugins, web search, past conversations or project documents (read or write), connected apps or devices | Run11 loaded `boardgame-playtest-sim`, whose text holds Lethal Dungeon lessons and points at all three benchmark flaws [C]. The v3 runs used no skills [C] and Run5/6/9 wrote into the Project [C]. All skills banned: none was ever needed, and the API has none | Korulein (all skills, after confirming none are needed) |
| 3 | `00a` | **Third kind of input file:** upstream extraction files `01_rules.txt` and `01_components.json`. Two paths: **extraction** (the `01` files replace the raw rulebook; no recount of components) and **raw** (as v4) | Field testing receives the output of an earlier pipeline stage, not raw rulebooks | Korulein (the requirement); mechanism by name, not content, after review |
| 4 | `00a` | **D1 on the extraction path:** the components table comes from `01_components.json`; the rest of the dossier and the I1..In list are still written. R4 checks the JSON's counts against what the rules text requires | The extraction has no interpretations, subsystems or layout, so D1 can't be skipped whole [C, template inspected]. D8, R7 and `headline.interpretations` depend on the I-list | Korulein asked to skip D1; revised after inspecting the template |
| 5 | `00a` | Reading order: `00a`, then `01` files, then game material, then `00b`–`00h` | Follows from 3 | — |
| 6 | `00a` | Material line: "the attached upstream extraction or game material" | Follows from 3 | — |
| 7 | `00a` | **RUNLOG gains `files_failed=<none|list>`**, placed before `files_written` | The run's own record of undelivered files; checked by L3 | Korulein (retry rule); field name by review |
| 8 | `00b` | **§3 Final check before delivery** (run side): every file present with its exact name, nothing empty, strict JSON, every zip one member with a matching line count, the manifest's `files` list computed last | Korulein: "implement a final check for all deliverable files". Run11 did this voluntarily [C]; now required | Korulein |
| 9 | `00b` | **§3 Batched delivery and retries:** all non-zip files in one send, then each zip on its own; after each send compare the tool's report; up to **three attempts** per file; report every retry | Run11: `per_game_D08` (116 MiB) failed with a 502 and was retried; the five files sent after it in the same call never appeared in the chat although the tool reported them delivered [C pattern, L cause]. Separate sends stop one failure taking others with it | Korulein (3 tries, loosened retry); batching by review |
| 10 | `00b` | **§4.2 rule 5:** keys in `readings` and `strategies` are the ids (`I<n>`, `R-I<n>[a-z]`, `S<n>`) with their case | v2.1 required upper-case arm ids (§4.1) and snake_case for every name (§4.2) at once; Run11 failed M7 on 96 ids for following §4.1 [C] | Review (instrument ambiguity, class b) |
| 11 | `00b` | `d1_source` added to the fixed strings (`extraction`, `raw`); rows 5–6, §4.2 rule 2 and §5 (`rulebook_file` = `01_rules.txt`) adjusted for the extraction path | Follows from 3 | — |
| 12 | `00g` | Manifest template v0.7: `run.d1_source`, `run.upstream_files`; `game_material_files` may be empty on the extraction path; id placeholders in `readings`/`strategies` | Follows from 3 and 10 | — |
| 13 | `00c`, `00d`, `00e`, `00f`, `00h` | **Unchanged** (byte-identical to v4) | — | — |

### 0.2 Game input for the pilot (`games\lethal_dungeon\`)
| # | Change | Why | Decided by |
|---|---|---|---|
| 14 | **Upstream extraction instead of raw material:** `01_rules.txt` and `01_components.json` only. No PDF, no photo | The pilot tests the path field testing will use | Korulein (upstream path; dossier only) |
| 15 | **`01_components.json` corrected** from the upstream operator's file: the 4 `item_card` entries merged into the 4 player cards (222 → 218 items); every map tile given its `tile_shape` (8 Cross, 10 T-junction, 9 Corner, 6 Straight, 3 Dead end, per K7). `01_rules.txt` unchanged: it matches the rulebook docx except for straight vs curly quotes and the table-of-contents page numbers [C] | The upstream file double-counted the cards and had no shapes. The tile mix is "the number 1 mistake every run makes" (Korulein; 1 of 10 runs exact, `AB_v3_tile_mix_check.md`) | Korulein (the errors; shapes in); correction script `fix_components.py` |
| 16 | **Guard on upstream inputs** (§2.4): only what a correct extraction of the designer's files and components contains. Rulebook errors stay as printed (4 large scrap, 2 jump markers); rule clarifications (K1, K3) and benchmark flaws (K4, K5) stay out | Anything in the input reaches the test chat; answers in the input void the grading | Review; explained to Korulein |

### 0.3 Intake rules (§2.3)
| # | Change | Why |
|---|---|---|
| 17 | Spaces in client file names become `_` | The app already does this on upload: Run11's manifest recorded `PRJ_Lethal_Dungeon_-_Rulebook.pdf` for a file named with spaces [C]. Renaming at intake keeps our records and the run's identical |
| 18 | `01` prefix reserved, like `00`; a client file starting with `01` gets `client_` in front | Follows from 3 |
| 19 | Upstream outputs are renamed to exactly `01_rules.txt` and `01_components.json` | The run detects the path by these names |

### 0.4 Operator procedure (§3)
| # | Change | Why |
|---|---|---|
| 20 | **RUN-END v5:** the export leaves out every reasoning block | Run11's RUN-END was flagged by the app's safeguards (`reasoning_extraction`) because it copies the raw session log, reasoning included [label C, cause L]. Usage numbers don't depend on those blocks: Run11 stripped vs unstripped gives identical `usage.csv` columns, 136 blocks removed [C]. Whether this stops the flag is unknown [G] |
| 21 | RUN-END is **attached as the file**, not pasted | Run11's arrived as pasted text [C] |
| 22 | **New step D2:** before RUN-END, count the file cards in the chat against the RUNLOG's `files_written`; if any are missing, send `operator\RESEND.md` with the names filled in, and log it | Run11's missing files could not be recovered once RUN-END had been sent and the chat was paused [C] |
| 23 | Before sending: confirm the model picker shows **Opus 5.5** and skills are off | Run11's first three rows were written by `claude-sonnet-4-6` with zero usage, before a model-upgrade marker [C]; cause unknown [L] |
| 24 | Run folder: delivered files in `out\` only | Run11's folder held deliverables next to `RUN_ID.jsonl` and `usage*` [C] |

### 0.5 Tools
| # | Tool | Change | Tested |
|---|---|---|---|
| 25 | `usage_extract.py` v4.1 | New columns `skills_listed`, `skills_flagged` (watch list: game-analysis skills that carry study knowledge), `models_list`; warnings for a flagged skill and for more than one model | On Run11: flags `boardgame-playtest-sim` and `critical-advisor`, and Sonnet 4.6 ×1; every v4 column identical [C] |
| 26 | `check_outputs.py` v1.3 | M1c (`d1_source`), M1b (empty game material allowed on the extraction path; no `00`/`01` names), M7 (id exemption), L3 (`files_failed`) | Fake runs on both paths pass; 35 of 35 breakages caught; Run11 now passes M7 [C] |

### 0.6 Pilot policy (§5)
| # | Change | Why | Status |
|---|---|---|---|
| 27 | Exit criterion 3: `contamination_calls` **and** `skills_flagged` empty | A skill can shape a run from the listing without being called | Proposed |
| 28 | Run11 counts as pilot 1 (non-sterile probe). The v5 pilot (Run12) is the **one repeat**, sterile, on the extraction path | Reclassifying Run11 after the fact to keep a spare repeat would reopen the loop the exit criteria prevent | Proposed; Korulein to confirm |
| 29 | The raw path's first sterile run happens in field testing | Run12 tests the extraction path (Korulein); one pilot can test only one path | Follows from 28 |

**Unchanged:** the TASK, D2–D10 and R1–R3/R5–R7 wording; targets; sample sizes; isolation rules;
model and effort; the 25 output files and their formats.

## 1. Held constant
1. Model `claude-opus-5-5`, effort `high`. Record both on every run.
2. Targets: play only; 30 / 45 / 60 min at 2 / 3 / 4 players; ±20%.
3. Sample sizes: D4 = 1 logged + 1,000 at 4 players; D5 = 1,000 per player count; D7 = re-run of
   D4's 1,000; D8 = 400 per arm on the baseline's seeds.
4. Isolation:
   - never run in Project Pipeline (it holds the answer key);
   - use the empty "Analysis" project (0 docs);
   - memory and past-chat search off; skills off (all of them);
   - no `LD_stat_catalogue`, rulings or study notes in any input (see §2.4).
5. **Linked computer:** accepted, never mentioned by name in the brief. The brief's generic "connected
   apps or devices" line covers it. The safeguard stays `contamination_calls`.
6. No time cap. Runs go to completion.

## 2. Inputs: `tokens\v5\`
```
tokens\v5\
  AB_prompt_instruments_v5.md      this file (never uploaded)
  system\                          the 8 instruction files: the same in every run
  games\lethal_dungeon\            the input for this game (after §2.3)
  operator\RUN-END.md              sent once, after the run
  operator\RESEND.md               only if files are missing (§3 D2)
```
**Upload = everything in `system\` + everything in `games\<game>\`.** Nothing else.
For the v5 pilot that is 8 + 2 = **10 files**.

### 2.1 Instruction files (`system\`)
| File | Version | Bytes | sha256 (first 12) | vs v4 |
|---|---|---|---|---|
| `00a_START_HERE.md` | brief v5 | 8,632 | `c3e1bd595eb7` | changed |
| `00b_output_contract.md` | contract v2.2 | 11,051 | `e4649e9ca431` | changed |
| `00c_reporting_standard.md` | standard v0.6 | 4,000 | `2c9e79ce8f07` | same |
| `00d_stat_definitions.md` | definitions v0.1.1 | 16,831 | `0ba0018de63d` | same |
| `00e_template_headline.json` | v1 | 3,258 | `32c7f657858b` | same |
| `00f_template_summary.json` | v0.6 | 2,770 | `772f6243e830` | same |
| `00g_template_run_manifest.json` | v0.7 | 2,274 | `2dadfc3f995e` | changed |
| `00h_template_per_game.json` | v0.6 | 2,565 | `547f1dfab417` | same |

The Project holds the three changed files in `claude/v5/system/`. Copy the five unchanged ones from
`tokens\v4\system\` and check their hashes against this table.

### 2.2 Pilot input (`games\lethal_dungeon\`)
| File | Source | Bytes | sha256 (first 12) |
|---|---|---|---|
| `01_rules.txt` | upstream operator's `rules.txt`, unchanged | 8,519 | `e9ecc555f393` |
| `01_components.json` | upstream operator's `components.json`, corrected (§0 row 15) | 76,203 | `5bad12b6bf85` |

### 2.3 Intake rules (every game, every client)
Keep the designer's file names, and change a file only when one of these rules requires it.
Record every change in the run log.
1. **Formats:**
   - PDF, plain text (`.txt`, `.md`, `.csv`), JSON, and images (`.jpg`, `.png`, `.gif`, `.webp`)
     go in as they are.
   - Convert `.docx`, `.doc`, `.odt`, `.pptx`, `.xlsx` and similar to PDF.
   - Unpack archives (`.zip` etc.) into the game folder, flat.
2. **Names:**
   - Remove any of `< > : " | ? * \ /` from a name, and replace spaces with `_`.
   - If a client name starts with `00` or `01`, add `client_` in front. Both prefixes are ours.
   - Upstream extraction outputs are renamed to exactly `01_rules.txt` and `01_components.json`.
3. **Size:** under 500 MB per file (API limit) [C].
4. **Nothing of ours in the game folder:** no notes, rulings, answer keys or earlier outputs.

### 2.4 Guard on what goes into an input
Test for every fact in an input file: *could the upstream stage have known it from the designer's
files and components alone, without asking the designer?*
- **Yes → allowed:** rulebook text, component kinds and counts, physical properties of components
  (such as tile shapes).
- **No → never:** the designer's rulings on questions the rulebook leaves open (K1 game end, K3
  Monster Rush movement, …), and above all the deliberate benchmark flaws (K4, K5).
- **Rulebook errors stay as printed:** 4 large scrap tokens, 2 risky jump markers. Correcting them
  would remove the R4 test.

## 3. Operator procedure
### A. Before the run
- [ ] Open a **new chat** in the "Analysis" project. The project shows **0 docs**; delete any
      report a previous run saved there.
- [ ] Memory off, past-chat search off, **all skills off**.
- [ ] Model picker shows **Opus 5.5**; effort `high`.
- [ ] `system\` holds exactly the 8 files in §2.1, with matching hashes. The game folder follows
      §2.3 and §2.4.
- [ ] Write down: run label (e.g. `V5_PILOT`), date, start time, the number of files to upload.

### B. Start the run
1. Drag in all files from `tokens\v5\system\` and all files from `tokens\v5\games\<game>\`.
2. Count the chips: 8 + game files (10 for the Lethal Dungeon pilot).
3. Leave the prompt box **empty**. Type nothing, not even a space.
4. Send.

### C. During the run
- Say nothing. If the model asks a question, don't answer; log the question and whether the run
  stalled.
- If the run stops without the RUNLOG line, log it as stalled. Do not prompt it to continue.

### D. End the run
1. When the final message ends with the `RUNLOG:` line, copy that line into the run log.
2. **Count the files.** Compare the file cards in the chat with the RUNLOG's `files_written`
   (25 + one per engine version). If any are missing, fill their names into
   `operator\RESEND.md`, attach it alone with the prompt box empty, send, and log it as an
   operator intervention (its cost is inside the measured run). Repeat at most once.
3. Attach `tokens\v5\operator\RUN-END.md` **alone, as the file**, with the prompt box empty, and
   send.
4. Download `RUN_ID.jsonl` from the reply. If no file comes back, or the app pauses the chat
   first, log it. Don't type anything else.

### E. After the run
1. Make the run folder `tokens\runs\Run12_V5_PILOT\`, with `out\` inside it.
2. Put `RUN_ID.jsonl` in `Run12_V5_PILOT\`, not in `out\`.
3. Download all the run's delivered files into `out\`. Check none ends in ` (1)`.
4. Usage (v4.1), from the tokens folder:
   `py usage_extract.py runs\Run12_V5_PILOT\RUN_ID.jsonl --csv runs\Run12_V5_PILOT\usage.csv --prices 4,20,0.2,5,8`
   Check: `contamination_calls`, `skills_flagged` and a single model in `models_list`.
5. Validation (v1.3):
   `py check_outputs.py "runs\Run12_V5_PILOT\out" --runlog "<the RUNLOG line>" --json "runs\Run12_V5_PILOT\check.json"`
6. Fill in the run log (§4).

## 4. Run log (one row per run)
| Field | Value |
|---|---|
| Label / folder | |
| Date, start time | |
| Model, effort | |
| Instruction files verified (8, hashes) / game files uploaded (names) / path (extraction or raw) | |
| Intake changes to game material (§2.3) | |
| Prompt box empty | yes / no |
| Questions asked by the model / stalled | |
| RUNLOG line | |
| File count in chat vs `files_written`; RESEND sent? | |
| `priced_usd`, `active_minutes`, `contamination_calls`, `skills_flagged`, `models_list` | |
| `check_outputs.py` result (pass / fail / warn counts) | |
| Deviations | |

## 5. Pilot, then field testing
The pilot exists to find problems in the system, not to produce results.

**Pilot exit criteria:**
1. The run completes with no typed text, no question answered and no stall.
2. `check_outputs.py` shows no FAIL; or every FAIL is traced to its cause and fixed in the
   instruments, not in the run's outputs.
3. `contamination_calls` and `skills_flagged` are empty.
4. Korulein can say what each delivered file is for and where it came from, using
   `check_outputs_explained.md` and this document.

**Status:** Run11 (v4) was pilot 1: a deliberate non-sterile probe that met criterion 1 and not 3
(`AB_v4_pilot_review.md`). **Run12 (v5, extraction path) is the one repeat** [proposed;
Korulein to confirm].
**If all four hold:** freeze v5 and go to field testing.
**If not:** no further pilots. Remaining problems are fixed during field testing and logged as a
version change.

**What Run12 can and cannot compare:**
- It is the first run on the extraction path: no photo and no layout. The run must make up its
  own starting maze from the tile shapes. Playtime and scores will differ from Run11 for that
  reason alone (Run11's random-layout reading R-I23a: −0.52 points per player, −3.3 min [C]).
- It is the first run where the tile mix is given rather than read; tile-mix accuracy is no
  longer a measure on this path.

## 6. Moving to the API later [C, Files API docs, 2026-10-26]
- Upload `.md`, `.txt`, `.json` and other text files with the `text/plain` content type, as
  `document` blocks. PDFs go as `document` blocks, images as `image` blocks.
- **Send the files in name order:** `00a`–`00h`, then `01` files, then game material. (Run11's
  app upload order was mixed; it didn't matter in the app, where every text file is placed in
  full.)
- **Each file is capped at 500 MB.** Run11's largest delivered file was 116 MiB [C].
- **Output files are produced in the code-execution container** and downloaded through the Files
  API, so the app's delivery failures (Run11) don't apply there [L].
- **RUN-END isn't needed:** each API response reports its own token usage.

## 7. Open before freezing
1. Confirm rows 27–29 (exit criterion 3, Run11 as pilot 1, Run12 as the one repeat).
2. How many field-test runs, and on which games; how many on each path.
3. Result stability is still open: duration tables, layout policy, bot design.
4. Whether `D02_run.py` must reproduce the D8 strategy bots exactly, or only the main batches.
