# 0001. Record decisions as ADRs

Status: proposed (2026-10-26)
Human version: `docs/decisions/0001-record-decisions-as-adrs.md`

## Decision

Record each architecture decision as an ADR in `context/decisions/`. Each ADR has a version for people in `docs/decisions/` with the same file name.

## Rules

- Status decides weight: `accepted` is binding, `proposed` is context only, `superseded` and `deprecated` are history.
- If a task conflicts with an `accepted` ADR, stop and propose a change. Do not work around it.
- Keep only the current text. Git is the changelog.
- State each rule once, in the ADR that owns it.
- Change the agent version and the human version in the same pull request.
