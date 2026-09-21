---
name: game-analysis
description: Analyse a tabletop game from its rulebook, component sheets or photos - read the game into an executable model, simulate it to estimate play time and outcome spread, hunt exploits and audit balance. Use when asked how long a game takes, whether it fits a session, whether it is balanced or breakable, or whether a rulebook can be simulated at all.
---

# Game analysis

Read a game out of its documents, model it, simulate it, and report honestly on what the
numbers are worth.

**This is throwaway analysis, not a product.** One simulator file, stdlib only, one findings
file. No CLI, no package layout, no config files, no test directory, no report generator, no
abstraction for "games in general", no versioned engines, no persisted dossier set. If the
work outgrows that, say so and ask before expanding.

Do it in one session. Budget roughly that; if you're going to blow through it, say so early
and say what you'd cut.

---

## Confidence tags

Tag every load-bearing number: **[C]** verified against rule text or a component you read
directly · **[L]** inferred from something [C] · **[G]** guess.

**A [G] must say why**, because two kinds behave differently:
- *ambiguous* — the document says something, you picked a reading. Fixable by asking.
- *absent* — the component or rule **is not in the files**. Not fixable by asking; someone has
  to send the missing thing.

---

## 1. Ingest and verify the ground

**Verify the premises; don't trust the brief's description of them.** File names, page
structure, tooling and runtime claims may be stale or wrong. Check, and **report corrections
back** — a corrected premise is a useful result, not a nitpick.

- docx → `pandoc -t plain`; pdf → render pages to PNG at 150–300 dpi and **actually look**;
  `unzip -l` on container formats to find embedded media, comments, tracked changes.
- **Assume the text layer is unreliable until proven otherwise.** Image-exported and scanned
  PDFs routinely drop word spaces and silently delete `ti`/`tt`/`fi` ligatures, producing
  plausible-looking words that are wrong. **Rendered images are authoritative; the text layer
  is a cross-check only.**
- Photos: read table state (grid, tiles, tokens, cards, pawn colours). Tag every visual read
  [L]/[G]. Duplicate photos → say so.
- **Extraction artefacts:** images pulled from a document can come back inverted, in a
  different colour space, or rotated relative to how the page renders. **Check one item
  against the page render before batch-processing.**
- **Validate bulk extraction against a manual read.** If you write a detector (counting pips,
  icons, symbols), verify it against several items you read with your own eyes and say how
  many you checked.
- **Use redundancy as evidence.** If the rules say "60 cards, 12 of each colour" and your
  extraction reproduces exactly that with a regular structure, that is strong evidence you
  read it right. If it doesn't reconcile, chase it or report it.
- **Check the documents agree with each other.** Different versions, dates or authoring tools
  usually means pages are out of sync. Cross-document contradictions are findings.

### Completeness gate — before modelling anything
Build the component list from the rules; check what is actually present; checksum counts.

Two failures, and the second is the one that kills the work:
1. A component is present but illegible → flag, continue.
2. **A whole category is absent** — the deck that sets prices, the cards that trigger scoring,
   the thing every turn depends on.

For (2): **say so before spending the budget.** State what modelling around it costs in
credibility, then make the call explicit — continue with the gap flagged, or stop. Never
quietly invent the missing category.

**Hunt for the document's own worked example** — a filled-in score sheet, a sample turn, a
diagram with numbers. It is the most valuable thing in the source: a free test fixture.

---

## 2. Write the game down before simulating it

**No critique in this step, even if flaws are obvious.** Describe only; judgment comes in §5.
Mixing them makes the description untrustworthy and the critique unfalsifiable.

In chat, briefly: components (+ checksums) · setup · player state · turn structure · each
subsystem (resources, elimination, scoring, abilities, every deck with counts) · map/topology
if there is one (per-cell read, [G]) · end conditions · every decision a player makes.

Then two numbered lists:

**INTERP (I1..In)** — every ambiguity where you picked a reading to make the rules executable.
Neutral wording ("reading chosen"), not "flaw". A **missing game-end condition** goes here
explicitly; it moves every total.

**Assumptions** — marked [C]/[L]/[G], flagging which ones the answer is actually sensitive to.

Also state separately:
- **What is unmodellable in principle**, as distinct from merely unmodelled. Bluffing,
  negotiation, table talk, reading opponents, kingmaking — a bot cannot do these. If they're
  central, that is a ceiling on the whole approach and it belongs here, not in the verdict.
- **Variants** — alternative scoring methods, difficulty levels, optional modules. Say which
  you're modelling and why. If you don't know which real players use, **ask**; it can change
  the answer more than anything else.
- **Reference player count** and the supported range.
- **The stated target play time, or explicitly that there isn't one.** If absent, say so and
  measure against whatever target the brief gives — don't silently adopt it as the designer's.

If the game is unreadable or far too under-specified to model, **say that and stop.** A clear
"not feasible from these documents, here's what's missing" is a good result — much better than
numbers from a game you guessed at.

---

## 3. One throwaway simulator

Single file, **stdlib only**, seeded RNG.

- `Game(seed, log)` owning its own `random.Random(seed)`; **all** randomness through it.
- Rules as methods; every extra rule reading tagged `SIMn` in a code comment.
- `Counter` for stats on game and per player; event log lines with timestamps.
- Config object with per-player strategy flags and game-level rule-variant flags, so levers
  and exploits are a flag flip rather than a fork.

**At least two behaviours:** uniform-random legal play, and greedy self-interested. Greedy
optimises **the game's own victory metric**, not a proxy you invented — simplest solid version
is enumerate every legal option, simulate-apply-undo, pick `max(gain − cost)`. If the two
behaviours diverge wildly, that is itself a finding.

*If the victory metric is exploitable, greedy will find the exploit. That is a headline result*
— check whether it's an artefact of your model or arithmetic a player could verify by hand.
The second kind is worth far more.

**Hard turn cap. Games hitting it are counted as non-terminating, never silently dropped** —
those are the ones that matter. Say what causes them.

Keep full event traces for a handful of runs plus every weird one.

### Time model — three things each easy to get wrong
1. **Per-action triangular `(lo, mode, hi)` seconds, sampled as events happen** → genuine
   within-game variance. Whole table is **[G]**. Assume rule-literate players; note first
   plays run slower.
2. **Also re-run everything with the whole table shifted low / default / high.** Sampling
   triangular captures variation *between games*; it does nothing about the risk that every
   estimate is biased the same direction. That second uncertainty usually dominates.
   **If the verdict flips across the shifted band, that is the headline.**
3. **Wall-clock, not person-seconds.** State which steps are serial (one player at a time) and
   which are simultaneous (everyone fills their own sheet at once). Getting end-of-game
   scoring wrong this way can move the total by tens of minutes.

Report **total session time and play-only time** (excluding setup, teardown, final scoring)
separately — "does it fit the lesson" and "how long is the game" are different questions.

---

## 4. Sanity checks — mandatory, before reporting anything

- Same seed ⇒ same result.
- One trivial known case through the same machinery (coin-flip-until-heads ⇒ mean 2).
- **Reproduce the document's own worked example exactly.** If it doesn't reproduce, find out
  why first — published examples sometimes round mid-calculation, which tells you how real
  players will compute it.
- **Smoke 10 seeds. If a core loop (scoring, a whole subsystem, winning) almost never happens,
  assume BUG or AI GAP first — not a game property.** Trace state per round, fix, rerun.
  Known killers: randomised setup producing unplayable configurations (model *deliberate* human
  setup instead); action-order bugs silently blocking a subsystem; agents with no fallback
  getting stuck.
- If the game has a board, measure connectivity/reachability before trusting generated maps.
- **Legality audit:** instrument actions over ~200 games, assert every constraint, report 0
  violations. Inline `assert`s are fine — no test suite.
- Read one full trace yourself and check it looks like a game a person could have played.

### Before quoting any usage statistic
**Any ability or option with no decision logic will read as "never used".** List every ability
and check each fires > 0 times. An unimplemented or unvalued ability is a **sim artifact** —
report it as one, never as a property of the game.

This is the most common way these reports mislead: "this role is never worth taking" and "my
bot cannot value information" look identical in a stats table and are opposite advice. If the
bot cannot value a mechanic in principle, **say that instead of quoting the number.**

Describe the AI honestly: heuristic, per-turn, how much lookahead and memory, self-interested;
list exactly which rules are spiteful vs cooperative.

---

## 5. Findings

Sample size: **let the confidence interval decide**, not habit. Report bootstrap CIs or
standard errors always. Thousands of runs for a median; more for a p90 or a paired effect you
want to call significant.

**Paired design for levers and exploits:** run the variant on the **same seeds** as baseline →
paired diff ± se. Rotate the exploiter across roles/seats when the strategy is generic. Far
more powerful than comparing independent batches.

Report:
- **Play time** — median, P10/P90, P(≤ target), each with a 95 % CI. No bare means.
- **Turn/round count** distribution, separately from minutes.
- **Outcome balance** — win / lose / stall / hit-cap, per behaviour.
- **Variation** between playthroughs and what drives it.
- **Degenerate and exploitable findings.** Menu to work through: degenerate scoring loops
  (scoring without engaging the core loop, especially under alternate readings) · unbounded
  accumulation (any term that only ever adds to score) · free-resource resets (death/respawn as
  heal or teleport) · RAW loophole abilities (missing restrictions vs sibling cards) · spite
  against the leader (zero-sum ranking often rewards it) · griefing and chokepoint blocking ·
  cooperative pairs · rule-reading variants (action timing) · gambling when downside is nil.
- **Balance** — role/item win share vs fair 1/N · zero-score rate · seat-order advantage ·
  lock/stall rates · deck usage and rare-card appearance % · dead cards · bonuses never worth
  chasing · dead turns with no real decision · whether outcomes are decided early (early-lead
  proxy vs final winner — beat chance by how much?) · resources that never bind or instantly
  collapse.
- **Rules-text audit** — no sim needed, often the highest-value output. Ambiguous quantifiers
  (once vs each) · OR/AND slips · missing target restrictions · text contradicting other text ·
  undefined timing · protected-object lists that omit things · division by zero or undefined
  terms in a scoring formula · enumerations with a gap · edge cases: empty deck, ties, can't
  pay, simultaneous end conditions. Quote the text, give the one-line fix.
- **Levers** — 3–5 single-parameter changes (dice, deck ratio, player count, a limit) with
  simulated effect: "median 74 → 61 min, P(≤60) 38 % → 54 %". The actionable part.

**Ranking and framing:**
- Rank by severity. Separate **exploit** (profitable) / **griefing** (legal, unprofitable) /
  **clarity issue**.
- "No effect" means *for this implementation only* — say so.
- **Separate findings that survive without the simulation from findings that rest on invented
  numbers.** Anything that is plain arithmetic or a direct reading of the documents is
  checkable by hand and true regardless of your model. Lead with that group.

---

## 6. Verdict

Straight answer, no salesmanship:
- Did reading the documents work? What could you not make out — and **separately**, what was
  simply **not there**?
- How much of the model is read versus guessed?
- **Are these numbers worth anything, or is the guesswork so dominant that the output is
  fiction dressed as statistics?** Answer **per output** — turn count, minutes and win rates
  rarely deserve the same confidence.
- Where would this break on a source with different demands — board geometry, spatial
  adjacency, dot positions, art that carries rules, heavy hidden information? **Be specific
  about which failures would be silent**; those are the dangerous ones.
- What would make it trustworthy, in priority order: cleaner sources, the missing components,
  board coordinates, one conversation with the designer, real playtest timings?
- **The 1–2 designer answers that would resolve the top findings.**

---

## Output style

- **Chat:** lead with the key finding or caveat. Compact tables. Conf tags. No padding.
  One closing question, maximum.
- One paste-able findings file in the repo root.
- Never give a number without saying what it rests on.
- Don't invent rules to fill gaps — flag the gap.
- Say what you skipped and why.
- Don't commit anything unless asked.
- **Finish with: what would you have wanted to know before you started?** If the brief sent you
  down a wrong path, misdescribed the inputs, or left a decision ambiguous that changed your
  output, say so.
