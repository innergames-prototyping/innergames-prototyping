# 0012. Tests use recorded LLM responses

Status: proposed (2026-10-15)

## Decision

Tests do not use the network or a real LLM. They use recorded LLM responses.

## Why

- Real LLM calls cost tokens, are slow and give a different answer each time.
- Tests must be cheap and repeatable.

## Rules

- Never call a real LLM or the network in a test.
- Store recorded responses next to the tests that use them.

## Consequences

- A test suite run costs no tokens and gives the same result each time.
