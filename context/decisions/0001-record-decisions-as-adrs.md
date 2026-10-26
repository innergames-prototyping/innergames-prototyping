# 0001. Record decisions as ADRs

Status: proposed (2026-10-26)
Human version: `docs/decisions/0001-record-decisions-as-adrs.md`

## Decision

Record each architecture decision as an ADR in `context/decisions/`. Each ADR has a version for people in `docs/decisions/` with the same file name.

## Why

- Decisions were spread over meetings, documents and issues. Agents and new students could not find them.
- Agents miss the reasons that people learn in conversation. An ADR writes them down.
- Agents over-apply long ADRs, so this version stays short and the discussion goes to `docs/`.

## Rules

- Status decides weight: `accepted` is binding, `proposed` is context only, `superseded` and `deprecated` are history.
- If a task conflicts with an `accepted` ADR, stop and propose a change. Do not work around it.
- Keep only the current text. Git is the changelog.
- State each rule once, in the ADR that owns it.
- Change the agent version and the human version in the same pull request.
