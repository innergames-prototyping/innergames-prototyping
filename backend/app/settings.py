"""Backend settings, read from environment variables.

| Variable                     | Default         | What it sets                                  |
| ---------------------------- | --------------- | --------------------------------------------- |
| `INNERGAMES_DATA_DIR`        | `~/.innergames` | Folder with one subfolder per extraction run  |
| `INNERGAMES_AGENT_MODEL`     | `haiku`         | Model of the extraction agent                 |
| `INNERGAMES_READER_MODEL`    | `haiku`         | Model of the tool-less reader calls           |
| `INNERGAMES_PARALLEL_READS`  | `12`            | Reader calls that run at the same time        |

How the app reaches Claude (ADR 0013): with `ANTHROPIC_API_KEY` set, Claude Code uses that key.
Without it, Claude Code uses the login of the local Claude Code installation.
"""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    agent_model: str
    reader_model: str
    parallel_reads: int

    @property
    def runs_dir(self) -> Path:
        return self.data_dir / "runs"


def load_settings() -> Settings:
    return Settings(
        data_dir=Path(os.environ.get("INNERGAMES_DATA_DIR", "~/.innergames")).expanduser(),
        agent_model=os.environ.get("INNERGAMES_AGENT_MODEL", "haiku"),
        reader_model=os.environ.get("INNERGAMES_READER_MODEL", "haiku"),
        parallel_reads=int(os.environ.get("INNERGAMES_PARALLEL_READS", "12")),
    )
