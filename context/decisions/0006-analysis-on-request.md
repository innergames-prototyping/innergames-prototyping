# 0006. Analysis only on request

Status: accepted (2026-10-01)

## Decision

LLM analysis of results is optional. It runs only when the user asks for it.

## Why

- Analysis costs tokens. The user decides when it is worth it.

## Rules

- Do not start an LLM analysis step automatically after a simulation.
- Show the user one LLM step, even when it does several checks inside.

## Consequences

- The user decides when to spend tokens on analysis.
