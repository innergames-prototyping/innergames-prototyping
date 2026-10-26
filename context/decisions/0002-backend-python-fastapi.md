# 0002. Backend: Python with FastAPI

Status: accepted (2026-10-12)
Human version: `docs/decisions/0002-backend-python-fastapi.md`

## Decision

The local backend uses Python with FastAPI.

## Why

- The simulation is Python (#96), so one language serves the backend and the simulation.
- Pydantic gives the model, the validation and the JSON Schema from one class.
- The same models describe what the LLM must return.

## Rules

- Write backend code in Python.
- Use Pydantic models for request and response bodies (see ADR 0010).

## Consequences

- The project has two languages: Python and TypeScript.
- A Windows build must package Python.
