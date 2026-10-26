# 0007. Simulation in a separate process with a time limit

**Status:** proposed (2026-10-15)

## Context

An LLM writes the simulation code (#96). That code can hang or crash.

## Decision

The backend starts each simulation run in a separate Python process with a time limit. A seeded random generator gives the same result for the same seed.

## Options

| Option | For | Against |
| --- | --- | --- |
| Separate process with a time limit (proposed) | A hang or crash does not stop the backend | Generated code can still do anything Python can do |
| Run in the backend process | No process start | A hang or crash stops the backend |
| One Docker container per run | Strong isolation | Each student computer needs Docker |

## Consequences

- Python is slower than a compiled language. Measure the speed on the first real run.
- The team must decide how far to isolate the generated code. [nog invullen]

## Sources

- Tech Stack draft (#106), 15 October 2026.

The short version for agents is [`context/decisions/0007-simulation-in-separate-process.md`](../../context/decisions/0007-simulation-in-separate-process.md).
