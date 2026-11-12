# Backend

Python backend (FastAPI, Pydantic). It has one phase for now: **extraction**. From the PDFs and
images of a board game it makes the rules text (`rules.md`), the list of components
(`components.json`) and a first game model (`game_model_v1.json`: rules, components, action kinds
and game variables).

An agent session (Claude Agent SDK) makes the judgments and works only through app tools. The bulk
reading is done by many tool-less reader calls. Code: `app/extraction/`, the agent's instructions:
`app/extraction/prompts/agent.md`.

## Install

```
uv sync
```

Python 3.13 or newer. Tesseract is optional: when `tesseract` is on the PATH, rules regions are
also read with OCR; without it that check is skipped.

## Claude access

With `ANTHROPIC_API_KEY` set, Claude Code uses that key. Without it, Claude Code uses the login of
the local Claude Code installation.

## Settings

Environment variables:

| Variable                    | Default         | What it sets                                 |
| --------------------------- | --------------- | -------------------------------------------- |
| `INNERGAMES_DATA_DIR`       | `~/.innergames` | Folder with one subfolder per extraction run |
| `INNERGAMES_AGENT_MODEL`    | `haiku`         | Model of the extraction agent                |
| `INNERGAMES_READER_MODEL`   | `haiku`         | Model of the tool-less reader calls          |
| `INNERGAMES_PARALLEL_READS` | `12`            | Reader calls that run at the same time       |

## Run the server

```
uv run uvicorn app.main:app --host 127.0.0.1
```

## Test it

Three ways. Run all commands from `backend/`.

**1. Tests.** They never call a real model.

```
uv run pytest
```

**2. Command line**, without the server:

```
uv run python -m app.extraction run rules.pdf cards.pdf [--run-dir DIR]
uv run python -m app.extraction tool render_pdfs --run-dir DIR
uv run python -m app.extraction tool update_config --run-dir DIR '{"changes": {"game": {"title": "X"}}}'
uv run python -m app.extraction propose --run-dir DIR
```

`run` does the whole flow, prints every tool call live, then the agent's reply and the cost.
`tool` runs one step by hand and prints what the agent would see. `propose` makes the game model
from `results/` of a finished run.

**3. API**, with the server running:

```
curl -F files=@rules.pdf -F files=@cards.pdf http://127.0.0.1:8000/api/extractions
curl http://127.0.0.1:8000/api/extractions
curl http://127.0.0.1:8000/api/extractions/<id>
curl 'http://127.0.0.1:8000/api/extractions/<id>/events?after=0'
curl http://127.0.0.1:8000/api/extractions/<id>/files/results/rules.md
curl -X POST http://127.0.0.1:8000/api/extractions/<id>/cancel
```

Only `.pdf` (a real PDF), `.png`, `.jpg` and `.jpeg` are accepted; otherwise the answer is 400 and
names the refused files. A second upload while a run is running gives 409. The state of a run is
`running`, `done`, `failed`, `cancelled` or `interrupted` (the backend stopped during the run).

## Run folder

`<data dir>/runs/<id>/`:

```
run.json        status of the run
events.jsonl    every tool call and text block of the agent
input/          the uploaded files
work/           everything the steps make: config.json, page renders, previews, crops, reads,
                review.html (each rules region beside its text, for a person to check)
results/        rules.md, components.json, game_model_v1.json
```
