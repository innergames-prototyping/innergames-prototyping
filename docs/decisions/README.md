# Decisions

This folder explains each architecture decision for people: the context, the options and the reasons. The short versions for agents are in `context/decisions/`, with the same file names.

| ADR | Decision | Status |
| --- | --- | --- |
| [0001](0001-record-decisions-as-adrs.md) | Record decisions as ADRs | proposed |
| [0002](0002-backend-python-fastapi.md) | Backend: Python with FastAPI | accepted |
| [0003](0003-frontend-react-typescript.md) | Frontend: React with TypeScript | accepted |
| [0004](0004-web-ui-instead-of-cli.md) | Web UI instead of a CLI UI | accepted |
| [0005](0005-simulation-runs-locally.md) | Simulation runs locally, not through the LLM | accepted |
| [0006](0006-analysis-on-request.md) | Analysis only on request | accepted |
| [0007](0007-simulation-in-separate-process.md) | Simulation in a separate process with a time limit | proposed |
| [0008](0008-llm-orchestrator-with-adapters.md) | One LLM orchestrator with an adapter per provider | proposed |
| [0009](0009-model-per-workload.md) | Choose the model per workload | proposed |
| [0010](0010-one-model-per-data-format.md) | One Pydantic model per data format | proposed |
| [0012](0012-tests-use-recorded-llm-responses.md) | Tests use recorded LLM responses | proposed |

ADR 0011 (module boundaries) waits for the C4 component diagram (#105).

## Template

Copy [`template.md`](template.md) for a new decision. Also add the short version in `context/decisions/`.
