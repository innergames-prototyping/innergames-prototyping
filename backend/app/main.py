"""The backend app. Run it with `uv run uvicorn app.main:app --host 127.0.0.1`."""

from fastapi import FastAPI

from .extraction.api import router
from .extraction.reader import ClaudeReader
from .extraction.runs import RunManager
from .settings import Settings, load_settings


def create_app(settings: Settings | None = None, runs: RunManager | None = None) -> FastAPI:
    """`settings` and `runs` are for tests; the default is the real setup."""
    settings = settings or load_settings()
    app = FastAPI(title="innergames backend")
    app.state.runs = runs or RunManager(
        settings, ClaudeReader(settings.reader_model, cwd=settings.data_dir)
    )
    app.include_router(router)
    return app


app = create_app()
