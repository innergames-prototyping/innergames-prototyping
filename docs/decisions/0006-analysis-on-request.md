# 0006. Analysis only on request

**Status:** accepted (2026-10-01)

## Context

The pipeline went straight from simulation to analysis. Both steps used the LLM. This cost many tokens.

## Decision

After the group meeting of 1 October 2026, Amilie and Luc split the pipeline into optional parts. Analysis runs only when the user asks for it. The LLM part feels like one process to the user, but does several checks inside.

## Consequences

- The dashboard needs a control to start the analysis.
- The cost of one analysis must be visible (#75 to #78).

## Sources

- Meeting notes, follow-up discussion after the group meeting of 1 October 2026.

The short version for agents is [`context/decisions/0006-analysis-on-request.md`](../../context/decisions/0006-analysis-on-request.md).
