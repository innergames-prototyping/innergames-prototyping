# 0010. One Pydantic model per data format

Status: proposed (2026-10-15)

## Decision

Each data format is defined one time, as a Pydantic model in the backend. JSON Schema files and frontend types are generated from it.

## Why

- The same data moves between the LLM, the backend, the simulation and the frontend.
- Shapes that are written twice drift apart.

## Rules

- Do not write the same data shape by hand a second time.
- Do not edit generated files: `schemas/` and the generated API types in the frontend.
- Validate each LLM answer with its Pydantic model before you use it.

## Consequences

- CI checks that generated files are current.
