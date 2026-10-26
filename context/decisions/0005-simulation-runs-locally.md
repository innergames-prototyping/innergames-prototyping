# 0005. Simulation runs locally, not through the LLM

Status: accepted (2026-10-01)
Human version: `docs/decisions/0005-simulation-runs-locally.md`

## Decision

The simulation runs as a local script. The LLM does not run the simulation.

## Rules

- Do not call an LLM inside a simulation run.
- Send simulation results to the local dashboard widgets.

## Consequences

- Token cost does not grow with the number of simulation runs.
