# 0003. Frontend: React with TypeScript

Status: accepted (2026-10-15)
Human version: `docs/decisions/0003-frontend-react-typescript.md`

## Decision

The frontend uses React with TypeScript.

## Why

- Each dashboard widget is one component (#98, #99).
- React has much documentation, so a future student learns it quickly.
- More reasons: #117 [nog invullen].

## Rules

- Write frontend code in TypeScript with `strict` on.
- Build each dashboard widget as one component.

## Consequences

- The build tool and the component library are not chosen yet (#117).
