"""Reader calls: one tool-less model call that sees a few images and one prompt.

The steps read every component and rules region with many independent reader calls and vote over
the answers. `ClaudeReader` makes the calls through the Claude Agent SDK, isolated as ADR 0013
says. Tests use `RecordedReader` instead (ADR 0012).
"""

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from claude_agent_sdk import ClaudeSDKError, ResultMessage, query
from PIL import Image

from ..claude import isolated_options
from .images import png_base64

SYSTEM_PROMPT = (
    "You transcribe printed tabletop-game material exactly as printed. You report only what you "
    "can see in the images. You never use knowledge of the game, never guess, never correct "
    "spelling and never fill in what would make sense."
)


class ReaderError(Exception):
    """A reader call failed after its retries."""


@dataclass(frozen=True)
class Answer:
    output: Any
    """The JSON object when the call had a schema, else the text."""
    cost_usd: float


class Reader(Protocol):
    model: str

    async def ask(
        self, images: list[Image.Image], prompt: str, schema: dict[str, Any] | None = None
    ) -> Answer: ...


CALL_TIMEOUT_SECONDS = 600


class ClaudeReader:
    def __init__(self, model: str, cwd: Path, tries: int = 3):
        self.model = model
        self.cwd = cwd
        self.tries = tries

    async def ask(
        self, images: list[Image.Image], prompt: str, schema: dict[str, Any] | None = None
    ) -> Answer:
        options = isolated_options(
            system_prompt=SYSTEM_PROMPT,
            model=self.model,
            cwd=self.cwd,
            output_schema=schema,
            max_turns=3,
        )
        cost, failures, error = 0.0, 0, ""
        rate_limit_pause = 30
        while failures < self.tries:
            try:
                result = await asyncio.wait_for(
                    _single_call(images, prompt, options), CALL_TIMEOUT_SECONDS
                )
            except TimeoutError:
                failures, error = failures + 1, f"no answer after {CALL_TIMEOUT_SECONDS} s"
                continue
            except ClaudeSDKError as e:
                failures, error = failures + 1, str(e)
                continue
            cost += result.total_cost_usd or 0
            output = result.structured_output if schema else result.result
            if not result.is_error and output is not None:
                return Answer(output, cost)
            error = result.result or result.subtype
            if result.api_error_status == 429 and rate_limit_pause <= 480:
                # Rate limited even after Claude Code's own retries: wait without using up a try.
                await asyncio.sleep(rate_limit_pause)
                rate_limit_pause *= 2
                continue
            failures += 1
        raise ReaderError(f"reader call failed: {error}")


async def _single_call(images, prompt, options) -> ResultMessage:
    async def message() -> AsyncIterator[dict[str, Any]]:
        content: list[dict[str, Any]] = [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": png_base64(img)},
            }
            for img in images
        ]
        content.append({"type": "text", "text": prompt})
        yield {"type": "user", "message": {"role": "user", "content": content}}

    result = None
    async for msg in query(prompt=message(), options=options):
        if isinstance(msg, ResultMessage):
            result = msg
    if result is None:
        raise ClaudeSDKError("no result message")
    return result


class RecordedReader:
    """Answers from a function instead of a model, for tests.

    `respond(images, prompt, schema)` returns the output; raise ReaderError to fail a call.
    `calls` keeps every prompt, so a test can check what was asked.
    """

    def __init__(
        self,
        respond: Callable[[list[Image.Image], str, dict[str, Any] | None], Any],
        cost_usd: float = 0.001,
        model: str = "recorded",
    ):
        self.respond = respond
        self.cost_usd = cost_usd
        self.model = model
        self.calls: list[str] = []

    async def ask(
        self, images: list[Image.Image], prompt: str, schema: dict[str, Any] | None = None
    ) -> Answer:
        self.calls.append(prompt)
        output = self.respond(images, prompt, schema)
        return Answer(json.loads(json.dumps(output)), self.cost_usd)
