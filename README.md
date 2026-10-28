# InnerGames Prototyping

This project entails taking InnerGames boardgame project PDFs which contain assets and game rules, digitalising those on the fly and running simulated experiments to test whether there are dead ends and other smells before they're put on paper to be tested by humans.

## Run the extraction app

The app takes a game's PDFs and extracts its rules to `rules.txt` and its components to `components.json`, with the `extract-game-components` skill in `.claude/skills/`. It needs Nix and a logged-in [Claude Code](https://claude.com/claude-code) (`claude`) on the `PATH`. The extraction calls Claude Haiku and takes about 15 minutes for a 12-page rulebook.

The backend's Python packages are pinned in `backend/requirements.txt` and installed in a virtual environment in `.venv`. The development shell (`nix develop`, or `direnv allow` once) creates it, reinstalls it when `backend/requirements.txt` changes and activates it. Without Nix, create it yourself from the repository root:

```sh
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
source .venv/bin/activate
```

Point your editor's Python interpreter at `.venv` so it finds the packages.

Start the backend and the frontend in two terminals from the repository root, with the virtual environment active:

```sh
cd backend && uvicorn app.main:app
```

```sh
cd frontend && npm install && npm run dev
```

Open http://localhost:5173 and drop the PDFs on the page. Each extraction works in its own folder under `backend/jobs/`, with the session log in `claude.jsonl` and the results in `results/`.
