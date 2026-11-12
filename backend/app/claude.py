"""Options for every Claude Agent SDK session the app starts.

ADR 0013: a session uses only what the app gives it. It loads nothing from the user's own Claude
Code setup: no CLAUDE.md, settings, skills, hooks, memory or MCP servers, and no built-in tools.
"""

from pathlib import Path
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions
from claude_agent_sdk.types import McpServerConfig

ISOLATED_ENV = {
    "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
    "ENABLE_CLAUDEAI_MCP_SERVERS": "false",
}

MAX_MESSAGE_BYTES = 2**26
"""Tool results with images are base64 and can be many megabytes; the SDK default is 1 MB."""


def isolated_options(
    *,
    system_prompt: str,
    model: str,
    cwd: Path,
    mcp_servers: dict[str, McpServerConfig] | None = None,
    allowed_tools: list[str] | None = None,
    output_schema: dict[str, Any] | None = None,
    max_turns: int | None = None,
) -> ClaudeAgentOptions:
    """Options for a session that sees only the app's system prompt and the app's own tools."""
    return ClaudeAgentOptions(
        system_prompt=system_prompt,
        model=model,
        cwd=cwd,
        setting_sources=[],
        strict_mcp_config=True,
        tools=[],
        mcp_servers=mcp_servers or {},
        allowed_tools=allowed_tools or [],
        permission_mode="dontAsk",
        env=dict(ISOLATED_ENV),
        output_format={"type": "json_schema", "schema": output_schema} if output_schema else None,
        max_turns=max_turns,
        max_buffer_size=MAX_MESSAGE_BYTES,
    )
