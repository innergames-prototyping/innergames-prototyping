# 0001. Record decisions as ADRs

**Status:** proposed (2026-10-26)

## Context

The team made decisions in meetings, in documents and in issues. An agent or a new student cannot find them. Issue #108 asks for ADRs in the repository.

Agents miss what people learn in conversation: why the system looks the way it does and which trade-offs the team made (Cane, 2026). Davidson (2026) reports two problems with ADRs and agents. Agents apply an old ADR too strictly, and they make ADRs long with discussion.

## Decision

Each decision has two files with the same name:

- `context/decisions/`: a short version for agents. It has the status, the decision, the rules and the consequences. It is the source for the rule.
- `docs/decisions/`: this version, for people. It tells the context, the options and the reasons.

The status decides how much weight an agent gives an ADR. When a task conflicts with an accepted ADR, the agent stops and proposes a change.

## Options

| Option | For | Against |
| --- | --- | --- |
| One ADR file for agents and people | One file to keep current | The discussion makes the agent version long; agents then over-apply it |
| Two versions (chosen) | Short context for agents, full story for people | Two files can drift apart; change both in one pull request |

## Consequences

- Each new decision needs two files.
- A reviewer checks that both files changed together.

## Sources

- Issue #108.
- Benjamin Cane, *Your coding agent is missing one thing: architectural context*, 28 May 2026.
- Duncan Davidson, *Coding agents love decision records*, 1 September 2026.

The short version for agents is [`context/decisions/0001-record-decisions-as-adrs.md`](../../context/decisions/0001-record-decisions-as-adrs.md).
