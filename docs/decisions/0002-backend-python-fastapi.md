# 0002. Backend: Python with FastAPI

**Status:** accepted (2026-10-12)

## Context

The simulation code is Python (#96). The application runs on one local computer and must be cheap and easy to learn for a future student (Technical Requirements, #86).

## Decision

The team chose Python with FastAPI for the local backend on 12 October 2026.

Reasons:

- The simulation is Python, so one language serves the backend and the simulation.
- FastAPI uses Pydantic. One class gives the model, the validation and the JSON Schema.
- The same models describe what the LLM must return.
- Python has libraries for statistics, PDF rendering and LLM clients.

## Options

| Option | For | Against |
| --- | --- | --- |
| Python with FastAPI (chosen) | One language with the simulation; validation and schemas built in | Two languages in the project |
| Node.js (Express or NestJS) | One language with the frontend | The backend must start Python for each run; schemas exist twice |
| Flask | Simple | No built-in validation or schema generation |
| Django | Complete | Too large for a local tool with one user |

## Consequences

- The frontend types are generated from the OpenAPI description (ADR 0010).
- A Windows application needs Python packaged with it.

## Sources

- Tech Stack draft (#106), 15 October 2026.
- Technical Requirements, 24 September 2026.

The short version for agents is [`context/decisions/0002-backend-python-fastapi.md`](../../context/decisions/0002-backend-python-fastapi.md).
