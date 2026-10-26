# 0006. Analysis only on request

Status: accepted (2026-10-01)
Human version: `docs/decisions/0006-analysis-on-request.md`

## Decision

LLM analysis of results is optional. It runs only when the user asks for it.

## Rules

- Do not start an LLM analysis step automatically after a simulation.
- Show the user one LLM step, even when it does several checks inside.

## Consequences

- The user decides when to spend tokens on analysis.
