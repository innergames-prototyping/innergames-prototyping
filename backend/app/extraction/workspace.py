"""The folder of one extraction run.

    <run>/input/      the uploaded PDFs (and image files)
    <run>/work/       everything the steps make: page renders, crops, reads, config.json, ...
    <run>/results/    rules.md, components.json, game_model_v1.json, review.html

Paths in tool output are relative to the run folder, so the agent can pass them to `view_images`.
"""

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .models import ExtractionConfig


class ExtractionError(Exception):
    """A step cannot go on. The message tells the agent what to do; the run itself goes on."""


def load_json(path: Path, default: Any = None) -> Any:
    return json.loads(path.read_text()) if path.exists() else default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False))


class Workspace:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.input = self.root / "input"
        self.work = self.root / "work"
        self.results = self.root / "results"

    def create(self) -> "Workspace":
        for folder in (self.input, self.work, self.results):
            folder.mkdir(parents=True, exist_ok=True)
        return self

    # ------------------------------------------------------------ paths

    @property
    def config_path(self) -> Path:
        return self.work / "config.json"

    def input_file(self, name: str) -> Path:
        """An uploaded file, by the name the config uses for it."""
        path = self.input / Path(name).name
        if not path.exists():
            raise ExtractionError(f"no uploaded file {name!r}; uploaded: {self.uploaded_files()}")
        return path

    def uploaded_files(self) -> list[str]:
        return sorted(p.name for p in self.input.iterdir() if p.is_file())

    def pdfs(self) -> list[Path]:
        return sorted(p for p in self.input.iterdir() if p.suffix.lower() == ".pdf")

    def page_image(self, stem: str, page: int) -> Path:
        """The full-resolution render of one PDF page."""
        return self.work / "pages" / f"{stem}_p{page}.png"

    def item_dir(self, key: str) -> Path:
        return self.work / "items" / key

    def rel(self, path: Path) -> str:
        """A path as the agent sees it: relative to the run folder."""
        return str(path.resolve().relative_to(self.root))

    def resolve(self, relative: str) -> Path:
        """A path the agent gave, refused when it points outside the run folder."""
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root):
            raise ExtractionError(f"{relative!r} is outside the run folder")
        return path

    # ------------------------------------------------------------ config

    def load_config(self) -> ExtractionConfig:
        data = load_json(self.config_path)
        if data is None:
            raise ExtractionError("there is no config yet; write it with `update_config`")
        return ExtractionConfig.model_validate(data)

    def update_config(self, changes: dict[str, Any]) -> ExtractionConfig:
        """Replaces the top-level keys in `changes` and saves the config only when it is valid."""
        current = load_json(self.config_path, {})
        try:
            config = ExtractionConfig.model_validate(current | changes)
        except ValidationError as e:
            raise ExtractionError(f"config not saved:\n{e}") from e
        save_json(self.config_path, config.model_dump(mode="json", exclude_defaults=True))
        return config
