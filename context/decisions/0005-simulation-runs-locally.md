# 0005. Simulation runs locally, not through the LLM

Status: accepted (2026-10-01)

## Decision

The simulation runs as a local script. The LLM does not run the simulation.

## Why

- The client wants low token cost. The LLM was used too much.
- Hundreds of simulation runs must not cost tokens.

## Rules

- Do not call an LLM inside a simulation run.
- Send simulation results to the local dashboard widgets.

## Consequences

- Token cost does not grow with the number of simulation runs.
