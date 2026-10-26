# 0005. Simulation runs locally, not through the LLM

**Status:** accepted (2026-10-01)

## Context

The client wants a cheap tool, mainly in AI tokens (client meeting, 17 September 2026). An early pipeline used the LLM for most steps. Luc said that the LLM was used too much.

## Decision

After the group meeting of 1 October 2026, Amilie and Luc agreed to take the simulation out of the LLM workload. The simulation runs as a local script. Its results go into local widgets.

## Consequences

- Hundreds of runs cost no tokens.
- The LLM still writes the game model and the simulation code; see ADR 0007 for how that code runs.

## Sources

- Meeting notes, follow-up discussion after the group meeting of 1 October 2026.
- Meeting notes, client meeting 17 September 2026 (budget for AI tokens).

The short version for agents is [`context/decisions/0005-simulation-runs-locally.md`](../../context/decisions/0005-simulation-runs-locally.md).
