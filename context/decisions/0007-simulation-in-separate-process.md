# 0007. Simulation in a separate process with a time limit

Status: proposed (2026-10-15)
Human version: `docs/decisions/0007-simulation-in-separate-process.md`

## Decision

The backend starts each simulation run in a separate Python process with a time limit.

## Why

- An LLM writes the simulation code. It can hang or crash.
- A separate process keeps the backend running when that happens.
- Docker per run is too heavy for a student computer.

## Rules

- Never run generated simulation code inside the backend process.
- Give each run a time limit.
- Pass a seeded `random.Random` to the simulation.

## Consequences

- How far to isolate generated code is not decided yet.
