# Statistics definitions v0.1

**Purpose.** A deliberately over-inclusive list of statistic *families* that a simulation run
should fill in. Every family has a slot in the results dashboard, so whatever a game does has
somewhere to go. Families that don't apply stay empty, with a status that says why (§0.3).
The examples come from made-up games.

Companion file: `reporting_standard_v0.5.md` (file layout and global rules).

---

## 0. Conventions (apply to every family)

### 0.1 Label grammar
`family:param1:param2`, all lowercase snake_case.
- A **family** is fixed by this file.
- **Parameters** are names the run takes from its own rules dossier, e.g. `life_lost:lava_pit`
  or `ability_use:wizard:blink`.
- Every parameter value must be declared once in `run_manifest.json → vocabulary`, with a one-line
  description. This lets the dashboard label it.

### 0.2 Levels and denominators
| Level | Meaning | Example |
|---|---|---|
| `G` | per game, all players combined | 14.2 resource points created per game |
| `P` | per player per game (= G ÷ player count when it is a plain sum) | 3.55 per player per game |
| `R` | per round (round 1…n), reported as a list | |
| `T` | per turn, aggregated to min / mean / median / max per game | |
| `E` | per event, aggregated the same way | |
| `agg` | across games only (shares, probabilities, win rates) | |

In `summary.json`, every G or P statistic is reported per player count as `mean`, `median`, `p10`
and `p90`. When the level is G or P, **both** `per_game` and `per_player_game` are given.

### 0.3 Status of a value
Every statistic has a `status`:
| Status | Meaning | `value` |
|---|---|---|
| `ok` | measured | the number (0 is a real zero) |
| `na` | not applicable: the game has no such mechanic | null |
| `nm` | the mechanic exists, but this run did not measure it | null |
| `ni` | the mechanic exists, but this run's engine does not implement it | null |

`nm` and `ni` are findings in their own right: they show what the simulation left out. Never write
0 for something that wasn't measured.

### 0.4 Units
Fixed by the family; listed in each table. Time is in minutes, on four clocks:
- `low`, `typical` and `high`: every action takes its low, typical or high duration.
- `sampled`: durations drawn at random.

The typical clock is the headline. Shares are 0–1, percentage points are `pp`, distances are grid
`steps`, and positions are written as `[row, col]` with `[1,1]` at the top left.

### 0.5 Voluntary vs involuntary
- **Voluntary:** the player chose it on their own turn.
- **Involuntary:** caused by the game, another player, or a card. This split is required wherever
  a family has a `<cause>` parameter.

### 0.6 Unmatched statistics
If a statistic fits no family, report it in `unmatched` with `label`, `value`, `unit`, `level`
and a one-sentence `definition`. **The dashboard shows `unmatched` as a generic table,** so nothing
the run measures is lost. Prefer a family wherever one fits. `unmatched` is for genuinely new
things.

---

## 1. Frame and setup
| Family | Unit | Lvl | Definition and counting rule |
|---|---|---|---|
| `player_count` | count | G | players in the game |
| `seat_role:<seat>` | name | G | role, character or faction dealt to each seat. `na` if the game has none |
| `turn_order` | list | G | seats in the order they act. Seat 1 acts first |
| `rounds_played` | count | G | a round = every active player has had one turn |
| `turns_played` | count | G | each player turn, including skipped ones |
| `end_trigger` | name | G | what ended the game (e.g. `deck_empty`, `score_reached`, `round_limit`) |
| `setup_mode` | name | G | `designed`, `random`, `photo` or `other`. How the starting position was made |
| `setup_hash` | string | G | hash of the full starting state, so identical setups can be found |
| `setup_reachable_positions` | positions | G | positions a player can reach from their start by legal movement only |
| `setup_goal_reachable:<goal>` | bool | G | whether each scoring or exit location can be reached at setup |
| `setup_goal_distance:<goal>` | steps | G | shortest legal path from start to that location; null with status `ok` if unreachable |

## 2. Time
| Family | Unit | Lvl | Definition and counting rule |
|---|---|---|---|
| `play_min` | min | G | first turn through final scoring |
| `session_min` | min | G | play + setup + teardown. Teaching is excluded unless stated |
| `setup_min`, `scoring_min` | min | G | |
| `round_min` | min | R | each round, including end-of-round effects |
| `round_end_min` | min | R | end-of-round effects only |
| `turn_min` | min | T | one player turn |
| `turn_min_by_state:<state>` | min | T | e.g. active, skipped, outside play area |
| `phase_min:<phase>` | min | G | total time per turn phase, summed over the game |
| `wait_between_turns_min` | min | P | mean time a player waits between their own turns |
| `time_by_event:<event>` | min | G | total time attributed to each event type in the duration table |
| `p_play_exceeds_target` | share | agg | share of games over the manifest target; also at the upper and lower tolerance |
| `p_session_exceeds_target` | share | agg | the same, for the whole session |

## 3. Actions and turns
**Action:** *any act a player makes, no matter how simple.*

**Counting rules:**
- Each separate player-initiated act counts as 1. Examples: a move, drawing a card,
  using an ability, picking something up, putting something down, rotating a piece, declining an
  optional choice.
- Things that happen *to* a player (damage, being moved, card effects) are events, not actions.
- **Movement counts per move:** one move = 1 action, whatever its length.
  Its length is recorded separately in `move_steps` (§4), so both counts exist.

| Family | Unit | Lvl | Definition and counting rule |
|---|---|---|---|
| `actions_total` | actions | G, P | all actions |
| `actions:<type>` | actions | G, P | by type, e.g. `move`, `draw`, `ability`, `pickup`, `drop`, `rotate`, `decline` |
| `actions_per_turn` | actions | T | min / mean / median / max |
| `actions_per_round` | actions | R | |
| `turns:<kind>` | turns | P | kind ∈ `normal`, `zero_move` (could move, chose not to), `idle` (did nothing at all), `skipped:<cause>` (a game effect removed the turn), `no_legal_move`, `outside_play` |

## 4. Movement of any entity
Entity classes are declared in the vocabulary: `player` plus any others (creature, piece, token,
vehicle…). Each physical component that can move needs a stable id.
| Family | Unit | Lvl | Definition and counting rule |
|---|---|---|---|
| `move_steps:<class>` | steps | G, P | voluntary steps, one per position change along a legal path |
| `move_steps_per_turn:<class>:<n>` | turns | P | how many turns had exactly n steps |
| `displaced:<class>:<cause>` | count | G, P | involuntary moves, by cause (e.g. `board_shift`, `swap`, `pushed_by_other`, `respawn`) |
| `displacement_distance:<class>:<cause>` | steps | E | grid distance of each involuntary move |
| `travel_distance:<class>:<id>` | steps | G | total distance each individual component moved |
| `distinct_positions:<class>` | positions | P | different grid positions occupied |
| `backtrack_steps:<class>` | steps | P | steps straight back to the previous position |
| `move_blocked:<class>:<reason>` | count | G, P | an attempted or wanted move that was impossible (wall, occupied, removed space, capacity) |
| `trapped:<class>` | count | G, P | entity left with no legal move by something it didn't choose |
| `distance_to:<goal>` | steps | T | shortest legal path to a goal at the start of each turn; mean per player |
| `no_path_to:<goal>` | turns | P | turns with no legal path to that goal |
| `position_heatmap:<class>` | visits | agg | end-of-turn positions summed over games, per position |
| `npc_move_steps:<npc>` | steps | E | steps a non-player entity took per activation |
| `npc_reached_target:<npc>` | count | G | activations that reached their target |
| `npc_no_path:<npc>` | count | G | activations with no legal path |

## 5. Board or map changes
| Family | Unit | Lvl | Definition and counting rule |
|---|---|---|---|
| `board_change:<kind>:<cause>` | count | G, P | kind ∈ `rotate`, `shift`, `swap`, `remove`, `add`, `flip`, `other`; cause = the card, ability or rule that did it |
| `pieces_affected:<kind>` | pieces | E | pieces moved or changed by one change |
| `change_affected_occupied:<kind>` | count | G | changes that moved or altered a piece someone stood on |
| `change_affected_location:<location>` | count | G | changes touching a special location (start, exit, goal…) |
| `rotation_degrees` | deg | E | |
| `reachable_after_change` | positions | E | positions reachable from the start after each change; min and mean per game |
| `goal_reachable_share:<goal>` | share | G | share of round ends where the goal is reachable |
| `connectivity_delta:<cause>` | positions | E | change in reachable positions caused by one change |
| `removed_spaces_end` | count | G | spaces destroyed or removed by game end |

## 6. Exploration and hidden information
| Family | Unit | Lvl | Definition and counting rule |
|---|---|---|---|
| `revealed` | positions | G, P | first reveals |
| `re_revealed` | positions | G, P | repeat reveals of the same position |
| `reveal_declined:<reason>` | count | P | an optional reveal not taken (e.g. `capacity`, `choice`) |
| `unrevealed_end` | positions | G | |
| `markers_peak:<marker>` | count | G | most markers in use at once |

## 7. Cards, decks and randomizers
| Family | Unit | Lvl | Definition and counting rule |
|---|---|---|---|
| `cards_drawn:<deck>` | cards | G, P | |
| `card:<deck>:<card>` | cards | G, P | per card type |
| `card_round:<deck>:<card>` | round | E | the round each copy was drawn |
| `card_outcome:<deck>:<card>:<outcome>` | count | G, P | each branch of a card with choices or random results |
| `deck_remaining_end:<deck>` | cards | G | |
| `deck_exhausted:<deck>` | bool | G | |
| `reshuffles:<deck>` | count | G | |
| `deck_order:<deck>` | list | G | for fixed-length decks (e.g. an event deck) |
| `random_draws:<device>` | count | G | coin flips, die rolls…, all reasons combined |
| `random_outcome:<device>:<reason>:<result>` | count | G | |

## 8. Resources and scoring material
Resources are declared in the vocabulary (e.g. `gold`, `crystal_small`). Points are reported
separately from tokens wherever they differ.
| Family | Unit | Lvl | Definition and counting rule |
|---|---|---|---|
| `resource_gained:<res>:<source>` | tokens, points | P | first acquisition from the game (cards, spaces, rewards) |
| `resource_picked_up:<res>:<origin>` | tokens, points | P | taken from the board: own drop, another player's drop, reward |
| `resource_dropped:<res>:<cause>` | tokens, points | P | `voluntary` or a forced cause |
| `resource_lost:<res>:<cause>` | tokens, points | P | gone for good (destroyed, discarded, overflow) |
| `resource_transferred:<res>:<from>:<to>` | tokens, points | G | between players |
| `resource_scored:<res>` | points | P | converted into score |
| `resource_held_end:<res>` | tokens, points | P | still held, unscored, at game end |
| `resource_on_board_end:<res>` | tokens, points | G | |
| `capacity_used` | slots | T | mean and peak per player |
| `capacity_full_turns` | turns | P | turns started at full capacity |
| `supply_peak:<component>` | count | G | most in use at once; compare with the component list |
| `supply_shortfall:<component>` | events | G | a moment when the rules needed more than the box contains |
| `points_per_trip` | points | E | points scored per scoring trip or delivery |

## 9. Health, lives, elimination
| Family | Unit | Lvl | Definition and counting rule |
|---|---|---|---|
| `life_lost:<source>` | lives | P | every point of health or lives lost, by source |
| `life_restored:<source>` | lives | P | |
| `low_health_turns` | turns | P | turns started at the lowest non-zero health |
| `players_reaching_zero_lives` | players | G | players whose health reached 0 at least once |
| `deaths:<source>` | count | P | by the source of the final point lost |
| `respawns` | count | P | |
| `eliminations:<source>` | count | P | permanent removal from play |
| `lives_end` | lives | P | |

## 10. Non-player entities and hazards
| Family | Unit | Lvl | Definition and counting rule |
|---|---|---|---|
| `npc_spawned:<npc>:<cause>` | count | G | |
| `npc_removed:<npc>:<cause>` | count | G, P | killed, dispelled, timed out… P = credited to the player who caused it |
| `npc_alive_peak:<npc>`, `npc_alive_end:<npc>` | count | G | |
| `npc_state:<npc>:<state>` | count | G | entries into named states (e.g. sleeping, chasing) |
| `hazard_triggered:<hazard>:<outcome>` | count | G, P | each outcome branch (hit, avoided, immune, declined…) |
| `hazard_placed:<hazard>` | count | G | |
| `hazard_persisting_end:<hazard>` | count | G | |

## 11. Roles, abilities, charges
| Family | Unit | Lvl | Definition and counting rule |
|---|---|---|---|
| `ability_use:<role>:<ability>` | uses | P | per holder per game, counting every sub-option separately |
| `ability_games_used:<role>:<ability>` | share | agg | share of games where the holder used it at least once |
| `ability_timing:<role>:<ability>:<when>` | uses | P | when = the turn phase name, `reactive` (in response to an event) or `out_of_turn` |
| `ability_used_action:<role>:<ability>` | uses | P | uses that took up the turn's action slot |
| `ability_no_effect:<role>:<ability>` | uses | P | used, but changed nothing |
| `ability_target:<role>:<ability>:<self\|other\|board>` | uses | P | |
| `charges_spent:<role>:<ability>` | charges | P | |
| `charges_restored:<source>` | charges | P | |
| `zero_charge_turns` | turns | P | turns started with no charges |

## 12. Zones (inside/outside play, areas, rooms)
| Family | Unit | Lvl | Definition and counting rule |
|---|---|---|---|
| `zone_enter:<zone>:<via>` | count | P | via = the entry point used |
| `zone_leave:<zone>:<via>` | count | P | |
| `turns_in_zone:<zone>` | turns | P | |
| `trips:<zone>` | count | P | complete enter → leave cycles |
| `first_leave_round:<zone>`, `last_leave_round:<zone>` | round | P | null with status `ok` if never |
| `in_zone_at_end:<zone>` | bool | P | |

## 13. Player interaction
| Family | Unit | Lvl | Definition and counting rule |
|---|---|---|---|
| `harm_to_others:<cause>` | events | P | an action that worsened an opponent's position: health, resources, distance to a goal, or trapped |
| `help_to_others:<cause>` | events | P | an action that improved an opponent's position |
| `life_caused_to_others:<cause>` | lives | P | traced back to the acting player |
| `resource_caused_lost_to_others:<cause>` | points | P | |

## 14. Outcome and scoring
| Family | Unit | Lvl | Definition and counting rule |
|---|---|---|---|
| `score` | points | P | final score |
| `rank` | rank | P | 1 = best; tied players share the better rank |
| `score_breakdown:<component>` | points | P | every scoring source separately |
| `score_by_round` | points | R | score after each round |
| `winner_seats` | list | G | 1-based |
| `tie`, `tied_count` | bool, count | G | |
| `winning_score`, `margin` | points | G | margin = winner minus runner-up; 0 on ties |
| `lead_changes` | count | G | times the leader changed between rounds |
| `players_with_zero_score` | players | G | |
| `win_share:<seat>`, `win_share:<role>` | share | agg | wins split equally on ties; report the 95% CI and the fair share (1 ÷ players) |
| `mean_score:<seat>`, `mean_score:<role>` | points | agg | |

## 15. Strategy tests
| Family | Unit | Lvl | Definition and counting rule |
|---|---|---|---|
| `strategy_score_diff:<id>` | points | agg | paired mean, strategy minus baseline on the same seeds, ± 95% CI |
| `strategy_win_diff:<id>` | pp | agg | |
| `strategy_opponent_diff:<id>` | points | agg | change in the opponents' mean score |
| `strategy_playtime_diff:<id>` | min | agg | |
| `strategy_rule_variant:<id>` | name | — | `as_dossier` or the interpretation id that was changed |
| `strategy_fired:<id>` | count | agg | times the strategy's distinctive move actually happened |

## 16. Audit and coverage
| Family | Unit | Lvl | Definition and counting rule |
|---|---|---|---|
| `illegal_actions` | count | G | must be 0 |
| `invariant_violations:<invariant>` | count | G | any state outside the rules (negative resources, over capacity…) |
| `readings_used` | list | G | interpretation ids active in this game |
| `engine_version` | name | G | |
| `never_fired:<path>` | — | run | rule path never reached in simulation |
| `rare:<path>` | share | run | reached in < 1% of games |
