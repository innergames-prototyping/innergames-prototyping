# START HERE: task brief
Brief v4. This file is your complete instruction. There is no other message: everything you need
is in the attached files.

## How to use the attached files
Two kinds of file are attached.

**Instruction files.** Their names start with `00`. There are always exactly these eight:

| File | What it is |
|---|---|
| `00a_START_HERE.md` | this brief: the task, the deliverables and the rules |
| `00b_output_contract.md` | exactly which files you write, their names, formats and fixed vocabulary. Where any other instruction file disagrees with it, this file wins |
| `00c_reporting_standard.md` | how results are recorded: statuses, units, clocks, event logs |
| `00d_stat_definitions.md` | the statistic families to fill in |
| `00e_template_headline.json` | template for `headline.json` |
| `00f_template_summary.json` | template for `summary.json` |
| `00g_template_run_manifest.json` | template for `run_manifest.json` |
| `00h_template_per_game.json` | template for one per-game record |

**Game material.** This is every other attached file, whatever it is called and however many
there are: the rulebook, plus any photographs or other material from the designer. It is what you
analyse.
- Read every game-material file before starting D1.
- In D1, list each one by its exact file name, with what it contains.
- Record the names in `run_manifest.json → run.game_material_files`.

**Reading order:** this file first, then all game material, then `00b` to `00h` in order.

The `00` prefix belongs to the instruction files only. Your output files keep the names given in
`00b_output_contract.md`.

## How to work
Complete the task end to end in one turn. Do not ask questions and do not stop for confirmation:
nobody will reply until you have finished. Where the rules are ambiguous, choose the most
reasonable reading, mark it [G] or [L], and record it in the interpretation list. Work through all
deliverables in order and finish with the final report.

## CONTEXT
You are analysing a tabletop game for a games studio that needs to know how long their games take
to play, so that sessions can be designed to fit a target length.
This analysis is run once. Nobody will correct it or run it again, so it must be complete and
correct as delivered.
Material: the attached game material (see above): the rulebook, plus any photographs or
other material of the physical prototype.
Target playtime, play only: 30 minutes at 2 players, 45 minutes at 3 players, 60 minutes at 4
players, tolerance ±20%.
Player counts to cover: 2-4.

## TASK
Produce a quantitative analysis of this game by building and running a simulation of it.

## REQUIRED DELIVERABLES (all of them, in this order)
- **D1.** A rules dossier: components with counts, setup, turn structure, every subsystem, every
  card or event type with its count, and the map/board layout if the photos show one. List
  separately, numbered I1..In, every point where the rules are ambiguous and you had to choose a
  reading to make them executable. Do not critique the game in D1.
- **D2.** A Python rules engine implementing the dossier, with a seeded random number generator,
  per-player and per-game statistics, and an event log.
- **D3.** A playtime model: an explicit table of per-action durations in seconds (low / typical /
  high), applied as events occur. State the table's assumptions.
- **D4.** One fully logged game at 4 players, and 1,000 further simulated games at 4 players for
  context. Report the single game next to the 10th percentile, median and 90th percentile of the
  batch, and say whether the single game is representative.
- **D5.** Playtime results per supported player count, from 1,000 simulated games at each player
  count: total minutes, minutes per round, minutes per turn, and the probability that a game
  exceeds the target.
- **D6.** Game statistics: resources gained, player eliminations or deaths, combat or hazard
  events, use of each player ability or role, and the share of games each player position or role
  wins. Cover every statistic family in the attached definitions that applies to this game.
- **D7.** Self-audit: list every ability, role and card type, and state for each whether it
  occurred in the simulation and how often. Report anything that never fired as a gap in your
  code. Fix what is fixable, re-run the 1,000 games from D4, and say which numbers changed.
- **D8.** Exploits, loopholes and balance problems. Test every suspected exploit, and every
  alternative reading of an ambiguous rule that could change scores, win rates or playtime, by
  running 400 games with one player using it against baseline players on identical seeds, and
  report the paired difference in score and win rate. Also audit the rulebook text itself for
  ambiguous wording, missing restrictions and contradictions.
- **D9.** Limitations: what in the analysis is an assumption, what could not be verified, and what
  would change the numbers most.
- **D10.** Open questions for the designer, at most five, ordered by how much the answer changes.
  For each question, state the measured difference between the readings, from D5 or D8.

## RULES FOR THE WORK
- **R1.** Tag every load-bearing number and claim: [C] verified from the rules or measured in the
  simulation, [L] inference, [G] guess.
- **R2.** Before reporting any result, check that each ability, role and card type can actually
  occur in the simulation. Report anything that is never exercised as a gap in your code, not as a
  property of the game.
- **R3.** Use exactly the sample sizes given in D4, D5, D7 and D8. Additional simulations (tests,
  checks, debugging) are allowed, but every batch must be listed in the ledger (R6).
- **R4.** Verify the component counts in the dossier against the rulebook's component list and
  report any mismatch.
- **R5.** Keep the final report under 1,200 words. Put detail in the files you write.
- **R6.** Write every output file exactly as specified in `00b_output_contract.md`: the file names,
  formats, vocabulary and simulation ledger. Follow `00c_reporting_standard.md` and
  `00d_stat_definitions.md` for the contents, and the templates for the structure. List every
  batch of simulated games in the ledger, including tests and debugging runs.
- **R7.** Do not leave a suspected exploit or a score- or playtime-relevant rule ambiguity
  untested. Anything raised anywhere (interpretations, rulebook audit, limitations, designer
  questions) must be simulated under each reading. If something truly cannot be simulated, list
  it in D9 as untested, with the reason.

## OUTPUT
Write exactly the files listed in `00b_output_contract.md`, and no others. Send them once, at the
end, in the contract's order. End your final message with:
```
RUNLOG: phases=<n> interpretations=<n> games_simulated=<n> files_written=<list>
```
`games_simulated` must equal `totals.games_executed` in `run_manifest.json`.
