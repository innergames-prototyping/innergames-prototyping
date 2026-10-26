# 0008. One LLM orchestrator with an adapter per provider

**Status:** proposed (2026-10-15)

## Context

Issue #102 says that all LLM calls go through one orchestrator and that a model change needs no code change. The Beta release may use a local LLM.

## Decision

One orchestrator class with one small adapter for each provider. Each adapter uses the official SDK of that provider.

## Options

| Option | For | Against |
| --- | --- | --- |
| Orchestrator with own adapters (proposed) | Provider code in one place; a local LLM is one more adapter | The team writes and tests each adapter |
| LiteLLM | One interface for many providers | Extra dependency; cost records still custom |
| LangChain | Many ready parts | Large dependency; hard to learn for a student |
| OpenRouter | One API key for many models | Another party sees each prompt; no local model |

## Consequences

- The team must record usage and cost for each step (#78).
- Revisit LiteLLM if the team adds a third provider and an adapter takes more than one day.

## Sources

- Tech Stack draft (#106), 15 October 2026.
- Issue #102.

The short version for agents is [`context/decisions/0008-llm-orchestrator-with-adapters.md`](../../context/decisions/0008-llm-orchestrator-with-adapters.md).
