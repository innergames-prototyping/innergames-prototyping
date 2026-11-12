"""The extraction agent session: Claude Agent SDK with only the `extract` tools.

The agent does the judgment (layout, kinds, flags) and calls the steps through `tools.py`. Its
instructions are `prompts/agent.md`.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, ToolUseBlock, query

from ..claude import isolated_options
from ..settings import Settings
from .queue import ReadLimits
from .reader import Reader
from .tools import SERVER_NAME, allowed_tool_names, build_server
from .workspace import Workspace

PROMPT_FILE = Path(__file__).parent / "prompts" / "agent.md"
MAX_ARGS_CHARS = 300

EventSink = Callable[[str, str], None]
"""`on_event(kind, text)`: kind is `tool` (a tool call) or `text` (a text block of the agent)."""


@dataclass(frozen=True)
class AgentResult:
    reply: str
    cost_usd: float
    is_error: bool


async def run_agent(
    ws: Workspace,
    settings: Settings,
    reader: Reader,
    limits: ReadLimits,
    on_event: EventSink,
) -> AgentResult:
    """Runs the agent until it gives its final reply."""
    options = isolated_options(
        system_prompt=PROMPT_FILE.read_text(),
        model=settings.agent_model,
        cwd=ws.root,
        mcp_servers={SERVER_NAME: build_server(ws, reader, limits)},
        allowed_tools=allowed_tool_names(),
    )
    prompt = f"Extract the uploaded files: {', '.join(ws.uploaded_files())}"
    reply, result = "", None
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            reply = _report_blocks(message, on_event) or reply
        elif isinstance(message, ResultMessage):
            result = message
    if result is None:
        return AgentResult(reply, 0.0, is_error=True)
    return AgentResult(
        reply=result.result or reply,
        cost_usd=result.total_cost_usd or 0.0,
        is_error=result.is_error,
    )


def _report_blocks(message: AssistantMessage, on_event: EventSink) -> str:
    """Sends every tool call and text block to `on_event`; returns the last text block."""
    last_text = ""
    for block in message.content:
        if isinstance(block, ToolUseBlock):
            on_event("tool", f"{_short_name(block.name)} {_short_args(block.input)}".strip())
        elif isinstance(block, TextBlock) and block.text.strip():
            on_event("text", block.text.strip())
            last_text = block.text.strip()
    return last_text


def _short_name(tool_name: str) -> str:
    return tool_name.removeprefix(f"mcp__{SERVER_NAME}__")


def _short_args(args: dict) -> str:
    text = json.dumps(args, ensure_ascii=False) if args else ""
    return text if len(text) <= MAX_ARGS_CHARS else text[:MAX_ARGS_CHARS] + "..."
