from pathlib import Path

import pytest

from app.extraction.workspace import Workspace


@pytest.fixture
def ws(tmp_path: Path) -> Workspace:
    """An empty run folder."""
    return Workspace(tmp_path / "run").create()
