# 0008. One LLM orchestrator with an adapter per provider

Status: proposed (2026-10-15)
Human version: `docs/decisions/0008-llm-orchestrator-with-adapters.md`

## Decision

All LLM calls go through one orchestrator. Each provider has one small adapter that uses the official SDK.

## Why

- Provider code stays in one place. A model change needs no code change (#102).
- A local LLM is one more adapter.
- LiteLLM, LangChain and OpenRouter add a large dependency or send prompts to another party.

## Rules

- Do not call a provider SDK outside its adapter.
- A model change is a configuration change, not a code change.
- Do not add LiteLLM, LangChain or OpenRouter.

## Consequences

- Revisit LiteLLM if the team adds a third provider and an adapter takes more than one day.
