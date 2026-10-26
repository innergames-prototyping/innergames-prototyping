# 0002. Backend: Python with FastAPI

Status: accepted (2026-10-12)
Human version: `docs/decisions/0002-backend-python-fastapi.md`

## Decision

The local backend uses Python with FastAPI.

## Rules

- Write backend code in Python.
- Use Pydantic models for request and response bodies (see ADR 0010).

## Consequences

- The project has two languages: Python and TypeScript.
- A Windows build must package Python.
