# 0009. Choose the model per workload

Status: proposed (2026-10-15)
Human version: `docs/decisions/0009-model-per-workload.md`

## Decision

The orchestrator maps each workload tier to a model: heavy steps to Opus, light steps to GLM 5.3 Flash.

## Rules

- Each pipeline step names its tier, not a model.
- The tier-to-model map lives in one configuration.

## Consequences

- Depends on ADR 0008.
