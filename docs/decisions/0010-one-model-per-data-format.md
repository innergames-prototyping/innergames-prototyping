# 0010. One Pydantic model per data format

**Status:** proposed (2026-10-15)

## Context

The same data moves between the LLM, the backend, the simulation and the frontend. If each part defines its own shape, the shapes drift apart.

## Decision

Each data format is one Pydantic model in the backend. FastAPI makes the OpenAPI description from it. The frontend types and the JSON Schema files are generated, not written. Each LLM answer passes the schema check before the code uses it.

## Consequences

- A schema change is a team decision (see Development Workflow).
- CI must check that the generated files are current.

## Sources

- Tech Stack draft (#106), 15 October 2026.
- Code Guidelines draft (#107), rules E4, E5, T4 and T5.

The short version for agents is [`context/decisions/0010-one-model-per-data-format.md`](../../context/decisions/0010-one-model-per-data-format.md).
