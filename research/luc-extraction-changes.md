# Luc's extraction changes that are not in the Agent SDK port

Ticket: #127. Sources: `git log`, `git show` and `git diff` of `origin/feature/extraction-to-simulation` (Luc's branch, author `oxey`) and `origin/staging` at `7a6a4c3` (PR #122 merged). Checked on 19 Nov 2026.

## Skill version the port is based on

The port is `3b12d9d` (12 Nov 2026). Its docstring (`backend/app/extraction/__init__.py`) says it ports `extract-game-components` (`extract.py`). The port matches the skill as it was at `4816cec` (4 Nov 2026), Luc's branch head at that time:

- `images.py:trim` has the grouped-region logic of `08700db` (4 Nov).
- `rules.py` has the coloured-dot rule and `voting.py:space_dots` of `4816cec` (4 Nov).
- `grouping.py:differs_small` (`2f620c9`), `orient.py` (`39ac59f`), the mismatch stop (`7787b5f`), the orientation cost (`2dd1b9f`), the `KeyError` fix (`c3d39f5`), the credits rule (`2d2a7bb`) and the flag instructions printed with the flags (`b92226f`, `f6fcc1f`, `d7376fc`) are all there.
- `render.py` already uses pypdfium2 with a lock, so the renderer part of `afd35ec` is already in the port.

The three commits of 16 Nov are newer than the port (`a1a8c06`, `3d39aae`, `afd35ec`). They are the only skill changes missing from the port. Commits `d4d4e51` to `c6f9a78` (Oct) are the older skill, the FastAPI wrapper and the pipeline; see the last table.

## Changes not in the port

| Commit | What it does | Agent SDK module it would touch | Changes Lethal Dungeon output |
|---|---|---|---|
| `afd35ec` (a) own backs | A back that no other design shares belongs to that component. Those designs are read with both sides; the back text is voted, spell-checked and exported as the item's `back`. Shared backs are still ignored. | `components.py` (`reader_prompt`, `reader_schema`, back vote in the read step), `grouping.py` or `layout.py` (find designs with an own back), `voting.py`, `check.py` (spelling and uncertain flags on `back`), `prompts/agent.md`. `Item.back` already exists in `models.py`; no code fills it. | No. LD has no component sheet and no backs. |
| `afd35ec` (b) tiles | A front over twice `MAX_SIDE` (1568 px) is sent scaled down plus a grid of overlapping full-resolution tiles (`TILE_SIDE` 2000). Readers are told board labels are content. | `components.py` (reader call), `images.py` (new `tiles()`), `prompts/agent.md` | No. LD has no large component. |
| `afd35ec` (c) uncertain flag | A text is flagged uncertain only when an alternative has a word the kept text lacks (`placed_elsewhere`). Same labels in another order no longer flag. | `voting.py`, `components.py` (`resolve`) | No. LD has no component reads. The rules vote is unchanged. |
| `afd35ec` (d) pypdfium2 | Replaces pdftoppm for page and OCR-crop rendering. | `render.py` | No change needed: the port already does this. |
| `3d39aae` level tilted crops | `crop` measures each crop's tilt from the pixels (no model call) and levels it to the nearest of level, sideways or upside down; stores `level` in `items.json`. SKILL.md: cut text that runs in several directions with `boxes`. | `layout.py` (`cut`/`crop`), `images.py` (tilt measurement), `orient.py` (works with the level), `prompts/agent.md` | No. Commit message: 0 of 440 Bottom Line crops change. LD has no crops. |
| `a1a8c06` read-only copy of the skill | Each job gets a read-only copy of the skill, `--disallowedTools "Edit(.claude/**)"`, `--setting-sources project,local`, and `skill_changes()` after the run. | None. The port has no Bash or Edit tool for the agent (`isolated_options`: `tools=[]`, `setting_sources=[]`, only the app tools). Nothing to port. | No. |

Notes on the table:

- LD is 6 A4 rulebook pages with no component sheet. The stored `01_components.json` says "0 unique designs", every item comes from `rules_items`, and the reads cost $0.0535 (reader calls on the rules regions only). So every component-side change leaves LD output unchanged.
- I did not run the port or the skill on LD (no API access in this research). The "no" for LD follows from the stored output and the commit scopes. The rules path is the same code on both sides after `4816cec`.

## Changes in Luc's branch that are not extraction behaviour

| Commit | What it does | Port module | Affects LD |
|---|---|---|---|
| `3f7a0a2` | Tells the orchestrator not to read SKILL.md (the prompt already holds it). Saved about 250k cached-read tokens in one Bottom Line run. | None. The port has no SKILL.md; the agent prompt is `prompts/agent.md`. | No |
| `e86aa33` | Skill output moves to `results/rules.txt` and a merged `results/components.json` (`export.schema.json`). | Port already writes the merged format; see the file names below. | No |
| `c6f9a78`, `5134a21`, `e0e06ae`, `3fe09da`, `c1f5556` | Extraction plus simulation as one pipeline (`backend/app/pipeline.py`, v5 simulation start). Copies `rules.txt` and `components.json` to `01_rules.txt` and `01_components.json`. | Not extraction. The pipeline must read `rules.md` when joined to the port. | No |
| `d4d4e51` to `0d96b8c`, `d345039` | First skill, FastAPI endpoint, `nix-shell -p`, ruff. | Replaced by the port. | No |

## Result file names

| File | Luc's branch (skill) | Agent SDK port |
|---|---|---|
| Rules | `results/rules.txt` (`e86aa33`; `ff8b9b6` first wrote `rules.md`) | `results/rules.md` (`assemble.py`) |
| Components | `results/components.json`, `export.schema.json` format | `results/components.json`, same merged format. Also `work/components.json` (every item with its paper trail) and `work/review.html`. |
| Game model | none | `results/game_model_v1.json` (`propose_model`, Pydantic validation; written by `__main__.py` and the backend step) |
| Simulation input | `pipeline.py` `UPSTREAM`: `rules.txt` to `01_rules.txt`, `components.json` to `01_components.json` | Not wired. `UPSTREAM` needs `rules.md` when the pipeline joins the port. |

## Open issues

- #123 (alternating front and back pages mix up): not fixed. `afd35ec` is closest: its SKILL.md line says to take the side with the card's name or number as the front. It does not add a `check` for many designs with differing backs, and it is not in the port. Luc's script also failed 1 of 2 runs, per the issue.
- #124 (agent cost 4 to 5 times Luc's): not fixed by any commit. `3f7a0a2` cuts Luc's own prompt cost only. `2f620c9` cuts time (group 282 s to 30 s), not cost.
- #125 (NO MAJORITY in the table of contents): not fixed. No Luc commit mentions a table of contents or dot leaders. The `●(colour)` rule of `4816cec` is for coloured score dots, and is already in the port; it is unrelated to the `.....` leaders.

## What to port, in value order for the open work

1. `afd35ec` own backs: the only change that may help #123 (backs that carry card text).
2. `afd35ec` tiles and uncertain flag: boards and big components, not LD.
3. `3d39aae` tilt: ring boards, not LD.
