# 0012. Tests use recorded LLM responses

**Status:** proposed (2026-10-15)

## Context

LLM calls cost tokens, are slow and give a different answer each time. Tests must be cheap and repeatable.

## Decision

Tests use recorded LLM responses. The test strategy (#113) will fix the details. [nog invullen: details from #113]

## Consequences

- When a prompt changes, the team records new responses.

## Sources

- Code Guidelines draft (#107), rule X2.
- Issue #113.

The short version for agents is [`context/decisions/0012-tests-use-recorded-llm-responses.md`](../../context/decisions/0012-tests-use-recorded-llm-responses.md).
