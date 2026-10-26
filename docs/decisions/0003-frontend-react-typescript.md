# 0003. Frontend: React with TypeScript

**Status:** accepted (2026-10-15)

## Context

The application has an upload page, review screens and a dashboard. The dashboard is built from a widget specification (#98, #99).

## Decision

The team chose React with TypeScript.

Known reasons:

- React makes each dashboard widget one component.
- React has much documentation and many examples, so a future student learns it quickly.

## Options

| Option | For | Against |
| --- | --- | --- |
| React with TypeScript (chosen) | Fits widgets; much documentation | Two languages in the project |
| Streamlit or Gradio | One language; fast first version | Custom review screens and widgets are hard |
| Server-rendered pages | No second language | The review screens need much interaction (#19) |
| Vue or Svelte | Small to learn | No team knowledge yet |

## Consequences

- The team must choose a build tool and a component library (#117).

## Sources

- Tech Stack draft (#106), 15 October 2026.
- Issue #117.

The short version for agents is [`context/decisions/0003-frontend-react-typescript.md`](../../context/decisions/0003-frontend-react-typescript.md).
