# 0009. Choose the model per workload

**Status:** proposed (2026-10-15)

## Context

Some pipeline steps need a strong model; others are simple. A strong model for every step costs too many tokens. Issue #102 (priority: should) asks to divide the steps over models by workload.

## Decision

One configuration maps each tier to a model. Heavy steps use Opus. Light steps use GLM 5.3 Flash.

## Consequences

- The team must decide which step is heavy and which is light. [nog invullen]

## Sources

- Issue #102.
- Tech Stack draft (#106), 15 October 2026.

The short version for agents is [`context/decisions/0009-model-per-workload.md`](../../context/decisions/0009-model-per-workload.md).
