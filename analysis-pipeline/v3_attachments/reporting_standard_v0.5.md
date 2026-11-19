# Reporting standard v0.5
How simulation results must be written. The statistics themselves are defined in
`stat_definitions_v0.1.md`.

## 1. Files
| File | One per | Holds |
|---|---|---|
| `run_manifest.json` | run | the targets the operator fills in, engine versions, the vocabulary of parameter names, and the **simulation ledger** |
| `per_game.jsonl` | simulated game, one JSON object per line | that game's measured values |
| `summary.json` | player count × engine version, plus one entry per strategy | aggregates over many games. The dashboard reads this file |
| `events_<batch>.jsonl.gz` | batch of games | the event log (§5) |

## 2. Rules that apply to every field
1. **Every statistic has a `status`.** It is `ok` (measured; 0 is a real zero), `na` (the game
   has no such mechanic), `nm` (the mechanic exists but wasn't measured) or `ni` (the mechanic
   exists but isn't implemented). A `value` is null unless the status is `ok`.
2. **Units are fixed by the family** (see the definitions file). Time is in minutes, shares are
   0–1, percentage points are `pp`.
3. **G- and P-level statistics give both `per_game` and `per_player_game`.**
4. **There are four clocks:** `low`, `typical`, `high` and `sampled`. The headline is `typical`.
5. **Seats are 1-based** and in turn order.
6. **Every game carries its `engine_version`.** A summary group that mixes versions must say so in
   `flags`.
7. **Over-inclusive by design.** Fill every family the game has. Mark the rest `na`. A statistic
   that fits no family goes in `unmatched` with a definition, so the dashboard can still show it.
8. **Every parameter name** (roles, resources, sources, causes, cards, zones, entity classes) is
   declared once in `run_manifest.json → vocabulary`, with a one-line description.

## 3. Required core (status `ok`, or `na` with a reason)
- Definitions §1, frame: all fields.
- Definitions §2, time: `play_min` on all four clocks, `session_min`, `round_min`, `turn_min`,
  `p_play_exceeds_target`, `p_session_exceeds_target`.
- Definitions §3, actions and turns: all fields.
- Definitions §14, outcome: all fields.
- Definitions §16, audit: all fields.
- The simulation ledger, covering every batch of games, including tests and debugging runs:
  - `totals.games_executed` = the sum of the ledger.
  - `totals.games_new` = the sum of entries marked `new`.

All other families are filled where the game has the mechanic. Mark them `na` otherwise, `nm` if
skipped, and `ni` if the engine leaves the mechanic out.

## 4. Templates
- `run_manifest.json`
- `per_game.template.json`
- `summary.template.json`

The `stats` arrays in both templates take entries of the form
`{"label": "family:params", "status": "ok|na|nm|ni", "value": …}`.

## 5. Event log (required)
- **One record per state change**, in JSON Lines:
  - `game`, `seq`, `round`, `turn`, `seat`, `phase`
  - `type`, `actor`, `subject`
  - `action_id`: groups all events caused by one player action. A 2-step move = 1 action_id with 2
    step events
  - `from`, `to` (grid positions), `component` (stable id)
  - changes to health, charges and resources
  - `card`, `random` (device and result), `choice`
  - `reading` (the interpretation id applied)
  - `clock_s` on all four clocks
- **Every physical component that can move gets a stable id.**
- **A full state snapshot** is logged at setup and after every round.
- **Coverage:** every game in the main batches, and at least 100 games per strategy test. Store
  gzipped.
- **Why:** every statistic in `summary.json` must be derivable from the log, so the numbers can
  be recomputed independently.
