# PROMPT INSTRUMENTS v4 (DRAFT, NOT FROZEN): SINGLE only
Project Pipeline / InnerGames. Drafted 2026-10-26 from v3 and output contract v2; revised the
same day after Korulein's review (open-ended game material, folder layout, pilot criteria).
Study document: **never upload this file to a test chat.** Freeze it before the v4 pilot, and
note any change made after a run has started.
Tags: [C] checked, [L] inference, [G] guess.

## 0. What changed from v3
| # | Change | Why |
|---|---|---|
| 1 | **STAGED dropped.** One condition: the whole task in one turn | v3: STAGED cost 1.68× SINGLE and was no more accurate (`AB_v3_results_comparison.md`) |
| 2 | **No typed text.** The brief, including the old SINGLE wrapper, is a file (`00a_START_HERE.md`). The message is sent with an empty prompt box | Needed for the API, where everything arrives as files. In v3 the wrapper was typed in the wrong place in all six runs; inside a file it can't be. An empty prompt box already worked: Run8 and Run9 had no typed text, only attachments [C] |
| 3 | **Two kinds of input file.** *Instruction files* have fixed names with a reserved `00a`–`00h` prefix, and there are always eight of them. *Game material* keeps whatever names the designer gave it, in any number. The brief tells the run to treat every non-`00` file as game material, list it in D1 and record it in the manifest | Future clients' files can't be predicted by name or count (Korulein, 2026-10-26). Only the files we write get fixed names |
| 4 | **CONTEXT "Material" line** now refers to "the attached game material (see above)" instead of "the attached rulebook, plus any attached photographs" | Follows from 3. The only wording change to CONTEXT/TASK/D/R besides R6 and OUTPUT |
| 5 | **Output contract v2.1, `headline.json`, zip-per-file data.** R6 and OUTPUT point to the contract | Consistent, machine-readable outputs (`AB_output_contract_v2_notes.md`) |
| 6 | Reporting standard v0.6; statistics definitions v0.1.1 | Removes contradictions with the contract (gzip event logs; `end_trigger` example values) |
| 7 | **Templates fixed.** Manifest: no `run_id`/`condition`, 13 ledger keys, a `files` list, `run.game_material_files`. Per-game: new `game_id`; `arm_id`, `arm_kind`, `focal_seat`. Summary: D8 arm fields. Headline: new | The v3 manifest template leaked the condition names to all six runs [C] |
| 8 | **Rulebook as PDF**, converted from the docx (6 pages; text and layout checked visually). Intake rule: no .docx ever (§2.3) | The API's document blocks accept PDF and plain text, not .docx [C, Files API docs]. This changes how the model receives the rulebook compared with v3, so v4 is a new baseline |
| 9 | **RUN-END is a file** (`RUN-END.md`), sent with an empty prompt box. The run ID is fixed as `RUN_ID` | No typed text, and no indentation damage from pasting (Run8). The cut-off still works: the file name puts "RUN-END" into the message, and `usage_extract.py` was tested on exactly that [C] |
| 10 | **Validator after every run:** `check_outputs.py` v1.2 | The contract is checked automatically, not by hand |

**Unchanged:** the TASK, D1–D10 and R1–R5/R7 wording; targets; sample sizes; isolation rules;
model and effort; `usage_extract.py`.

## 1. Held constant
1. Model `claude-opus-5-5`, effort `high`. Record both on every run.
2. Targets: play only; 30 / 45 / 60 min at 2 / 3 / 4 players; ±20%.
3. Sample sizes: D4 = 1 logged + 1,000 at 4 players; D5 = 1,000 per player count; D7 = re-run of
   D4's 1,000; D8 = 400 per arm on the baseline's seeds.
4. Isolation:
   - never run in Project Pipeline (it holds the answer key);
   - use the empty "Analysis" project (0 docs);
   - memory and past-chat search off; custom skills off;
   - no `LD_stat_catalogue`, rulings or study notes.
5. **Linked computer: accepted, not instructed against.**
   - All v3 runs were linked even though they were run in the browser (Korulein); the app links
     sessions either way.
   - No run used the link [C, v3 transcripts]. Adding a "don't use the computer" line would tell
     every run a computer exists, so the brief stays silent.
   - The safeguard is the post-run check: `contamination_calls` must be empty.
6. No time cap. Runs go to completion.

## 2. Inputs: `tokens\v4\`
```
tokens\v4\
  AB_prompt_instruments_v4.md      this file (never uploaded)
  system\                          the 8 instruction files: the same in every run
  games\lethal_dungeon\            game material for this game, as received (after §2.3)
  operator\RUN-END.md              sent once, after the run
```
**Upload = everything in `system\` + everything in `games\<game>\`.** Nothing else.

### 2.1 Instruction files (`system\`): fixed names
| File | Version | Bytes | sha256 (first 12) |
|---|---|---|---|
| `00a_START_HERE.md` | brief v4 | 6,935 | `49ca70b6b416` |
| `00b_output_contract.md` | contract v2.1 | 9,191 | `609f5878f02e` |
| `00c_reporting_standard.md` | standard v0.6 | 4,000 | `2c9e79ce8f07` |
| `00d_stat_definitions.md` | definitions v0.1.1 | 16,831 | `0ba0018de63d` |
| `00e_template_headline.json` | v1 | 3,258 | `32c7f657858b` |
| `00f_template_summary.json` | v0.6 | 2,770 | `772f6243e830` |
| `00g_template_run_manifest.json` | v0.6 | 1,974 | `2b05196dda2f` |
| `00h_template_per_game.json` | v0.6 | 2,565 | `547f1dfab417` |

**Why `00a`–`00h`:**
- These names sort first and in this order everywhere: Explorer (case-insensitive), the upload
  dialog, and code (ASCII).
- The `00` prefix marks a file as ours, so the run can tell instructions from game material
  without knowing the game material's names.
- A colon (as in "Step 1:") is not allowed in Windows file names, and the Files API rejects it
  too [C].

**What the prefix does not do:**
- It doesn't make the model read files in that order. In the app, text files are placed into the
  conversation in full, whatever their names [C, v3 transcripts].
- The reading order is an instruction inside `00a_START_HERE.md`. In the API, it is the order in
  which your code sends the files.

### 2.2 Game material (`games\lethal_dungeon\`): names as received
| File | Source | Bytes | sha256 (first 12) |
|---|---|---|---|
| `PRJ Lethal Dungeon - Rulebook.pdf` | `LDFiles\PRJ Lethal Dungeon - Rulebook.docx` (v1.1.2), converted | 114,332 | `927dd0b4208f` |
| `preview.webp` | `LDFiles\preview.webp` | 113,956 | `6de9b51c46a1` |

### 2.3 Intake rules for game material (every game, every client)
Keep the designer's file names, and change a file only when one of these rules requires it.
Record every change in the run log.
1. **Formats:**
   - PDF, plain text (`.txt`, `.md`, `.csv`), and images (`.jpg`, `.png`, `.gif`, `.webp`) go in
     as they are.
   - Convert `.docx`, `.doc`, `.odt`, `.pptx`, `.xlsx` and similar to PDF.
   - Unpack archives (`.zip` etc.) into the game folder, flat.
2. **Names:**
   - Remove any of `< > : " | ? * \ /` from a name.
   - If a name starts with `00`, add `client_` in front. `00` is reserved for instruction files.
3. **Size:** under 500 MB per file (API limit) [C].
4. **Nothing of ours in the game folder:** no notes, rulings, answer keys or earlier outputs.

## 3. Operator procedure
### A. Before the run
- [ ] Open a **new chat** in the "Analysis" project. The project shows **0 docs**; delete any
      report a previous run saved there.
- [ ] Memory off, past-chat search off, custom skills off.
- [ ] Model `claude-opus-5-5`, effort `high`.
- [ ] `system\` holds exactly the 8 files in §2.1. The game folder follows §2.3.
- [ ] Write down: run label (e.g. `V4_PILOT`), date, start time, the number of files to upload.

### B. Start the run
1. Drag in all files from `tokens\v4\system\` and all files from `tokens\v4\games\lethal_dungeon\`.
2. Count the chips: 8 + game files (10 for Lethal Dungeon).
3. Leave the prompt box **empty**. Type nothing, not even a space.
4. Send.

### C. During the run
- Say nothing. If the model asks a question, don't answer; log the question and whether the run
  stalled.
- If the run stops without the RUNLOG line, log it as stalled. Do not prompt it to continue.

### D. End the run
1. When the final message ends with the `RUNLOG:` line, copy that line into the run log.
2. Attach `tokens\v4\operator\RUN-END.md` **alone**, with the prompt box empty, and send.
3. Download `RUN_ID.jsonl` from the reply. If no file comes back, log it. Don't type anything else.

### E. After the run
1. Make the run folder `tokens\runs\Run11_V4_PILOT\`, with `out\` inside it.
2. Put `RUN_ID.jsonl` in `Run11_V4_PILOT\`.
3. Download all the run's delivered files into `out\`. Check none ends in ` (1)`.
4. Usage, from the tokens folder:
   `py usage_extract.py runs\Run11_V4_PILOT\RUN_ID.jsonl --csv runs\Run11_V4_PILOT\usage.csv --prices 4,20,0.2,5,8`
5. Validation:
   `py check_outputs.py "runs\Run11_V4_PILOT\out" --runlog "<the RUNLOG line>" --json "runs\Run11_V4_PILOT\check.json"`
6. Fill in the run log (§4).

## 4. Run log (one row per run)
| Field | Value |
|---|---|
| Label / folder | |
| Date, start time | |
| Model, effort | |
| Instruction files verified (8, hashes) / game files uploaded (names) | |
| Intake changes to game material (§2.3) | |
| Prompt box empty | yes / no |
| Questions asked by the model / stalled | |
| RUNLOG line | |
| `priced_usd`, `active_minutes`, `contamination_calls` | |
| `check_outputs.py` result (pass / fail / warn counts) | |
| Deviations | |

## 5. Pilot, then field testing
The pilot exists to find problems in the system, not to produce results. Decide in advance what
"good enough" means, so it can't turn into an open-ended loop.

**Pilot exit criteria (proposed; Korulein to confirm):**
1. The run completes with no typed text, no question answered and no stall.
2. `check_outputs.py` shows no FAIL; or every FAIL is traced to its cause and fixed in the
   instruments, not in the run's outputs.
3. `contamination_calls` is empty.
4. Korulein can say what each delivered file is for and where it came from, using
   `check_outputs_explained.md` and this document.

**If all four hold:** freeze v4 and go to field testing.
**If not:** fix and run **one** more pilot at most. Problems that remain after that are fixed
during field testing and logged as a version change, not as further pilots.

## 6. Moving to the API later [C, Files API docs, 2026-10-26]
- Upload `.md`, `.json` and other text files with the `text/plain` content type, as `document`
  blocks. PDFs go as `document` blocks, images as `image` blocks.
- **Send the files in name order:** `00a`–`00h`, then the game material.
- **Each file is capped at 500 MB.** Run10's largest delivered file was 325 MB [C].
- **Output files are produced in the code-execution container** and downloaded through the Files
  API.
- **RUN-END isn't needed:** each API response reports its own token usage.
- **A file-only message with no text block** works in the app (Run8, Run9) [C]. In the API it
  should too [L]; confirm in the first API test.

## 7. Open before freezing
1. Pilot exit criteria (§5): confirm or change.
2. How many field-test runs, and on which games.
3. Result stability is still open: duration tables, layout policy, bot design.
4. Whether `D02_run.py` must reproduce the D8 strategy bots exactly, or only the main batches.
