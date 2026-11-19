"""The agent's tools: one thin wrapper per step, served as an in-process MCP server.

`TOOLS` is the one table of name -> (description, input schema, function). `build_server` turns it
into the MCP server `extract`; `call_tool` runs one tool by name without MCP (the CLI and the tests
use it). A tool that cannot go on raises `ExtractionError`; the agent sees the message as an error
result and the run goes on.
"""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from claude_agent_sdk import SdkMcpTool, create_sdk_mcp_server
from claude_agent_sdk.types import McpSdkServerConfig
from PIL import Image, UnidentifiedImageError

from . import assemble, check, cost, grouping, layout, orient, reading, regions, render, rules
from .images import png_base64
from .queue import ReadLimits
from .reader import Reader, ReaderError
from .workspace import ExtractionError, Workspace

log = logging.getLogger(__name__)

SERVER_NAME = "extract"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}
MAX_IMAGES_PER_CALL = 20

Content = list[dict[str, Any]]
"""MCP content blocks: text blocks and image blocks."""


@dataclass(frozen=True)
class Context:
    ws: Workspace
    reader: Reader
    limits: ReadLimits


ToolFunction = Callable[[Context, dict[str, Any]], Awaitable[str | Content]]


# ---------------------------------------------------------------- wrappers
# Each wrapper runs one step. CPU-heavy sync steps run in a thread, so the server stays responsive.


async def _render_pdfs(ctx: Context, args: dict[str, Any]) -> str:

    return await asyncio.to_thread(render.render_pdfs, ctx.ws)


async def _lines(ctx: Context, args: dict[str, Any]) -> str:

    return await asyncio.to_thread(render.page_lines, ctx.ws, _required(args, "page"))


async def _update_config(ctx: Context, args: dict[str, Any]) -> str:
    changes = _required(args, "changes")
    if isinstance(changes, str):
        changes = _parse_json_object(changes)
    if not isinstance(changes, dict):
        raise ExtractionError("`changes` must be a JSON object of top-level config keys")
    config = ctx.ws.update_config(changes)
    return config_summary(config.model_dump(mode="json", exclude_defaults=True))


def config_summary(config: dict[str, Any]) -> str:
    """What is in the config now: one line per key, with the number of entries of a list."""
    lines = ["config saved. It has now:"]
    for key, value in config.items():
        if key == "game":
            lines.append(f"  game: {value.get('title')}")
        else:
            lines.append(f"  {key}: {len(value)} entries")
    return "\n".join(lines)


async def _view_images(ctx: Context, args: dict[str, Any]) -> Content:
    paths = _required(args, "paths")
    if not isinstance(paths, list) or not all(isinstance(p, str) for p in paths):
        raise ExtractionError("`paths` must be a list of run-relative paths")
    if len(paths) > MAX_IMAGES_PER_CALL:
        raise ExtractionError(
            f"at most {MAX_IMAGES_PER_CALL} images per call; you gave {len(paths)}. "
            "Split them over two calls."
        )
    content: Content = []
    for relative in paths:
        content.append({"type": "text", "text": relative})
        content.append(await asyncio.to_thread(_image_block, ctx.ws, relative))
    return content


def _image_block(ws: Workspace, relative: str) -> dict[str, Any]:
    path = ws.resolve(relative)
    if path.suffix.lower() not in IMAGE_SUFFIXES:
        raise ExtractionError(f"{relative!r} is not an image (png, jpg or jpeg)")
    if not path.is_file():
        raise ExtractionError(f"{relative!r} does not exist")
    try:
        with Image.open(path) as img:
            data = png_base64(img)
    except UnidentifiedImageError as e:
        raise ExtractionError(f"{relative!r} is not a readable image") from e
    return {"type": "image", "data": data, "mimeType": "image/png"}


async def _crop(ctx: Context, args: dict[str, Any]) -> str:

    return await asyncio.to_thread(layout.crop_items, ctx.ws)


async def _group(ctx: Context, args: dict[str, Any]) -> str:

    return await asyncio.to_thread(grouping.group_designs, ctx.ws)


async def _orient(ctx: Context, args: dict[str, Any]) -> str:

    return await orient.orient_designs(ctx.ws, ctx.reader, ctx.limits)


async def _preview(ctx: Context, args: dict[str, Any]) -> str:

    return await asyncio.to_thread(regions.preview_regions, ctx.ws)


async def _read(ctx: Context, args: dict[str, Any]) -> str:

    return await reading.read_all(ctx.ws, ctx.reader, ctx.limits, args.get("designs"))


async def _read_rules(ctx: Context, args: dict[str, Any]) -> str:

    return await rules.read_rules(ctx.ws, ctx.reader, ctx.limits)


async def _check(ctx: Context, args: dict[str, Any]) -> str:

    return await asyncio.to_thread(check.run_check, ctx.ws)


async def _assemble(ctx: Context, args: dict[str, Any]) -> str:

    return await asyncio.to_thread(assemble.assemble, ctx.ws, bool(args.get("force", False)))


async def _cost(ctx: Context, args: dict[str, Any]) -> str:

    return await asyncio.to_thread(cost.cost_report, ctx.ws)


def _required(args: dict[str, Any], name: str) -> Any:
    if name not in args:
        raise ExtractionError(f"missing argument `{name}`")
    return args[name]


def _parse_json_object(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ExtractionError(f"`changes` is not valid JSON: {e}") from e


# ---------------------------------------------------------------- the table

NO_ARGS: dict[str, Any] = {"type": "object", "properties": {}}

TOOLS: dict[str, tuple[str, dict[str, Any], ToolFunction]] = {
    "render_pdfs": (
        "Render every uploaded PDF: page images, previews (work/preview/) and the text layer. "
        "Run it first, then open the previews with view_images.",
        NO_ARGS,
        _render_pdfs,
    ),
    "lines": (
        "Print the cut lines (xs, ys) found on one page render, for a grid layout. "
        "`page` is '<pdf stem>_p<page>', e.g. 'cards_p1'.",
        {
            "type": "object",
            "properties": {"page": {"type": "string", "description": "e.g. cards_p1"}},
            "required": ["page"],
        },
        _lines,
    ),
    "update_config": (
        "Replace top-level keys of the extraction config (game, sources, layouts, kinds, "
        "rules_items, back_kinds, expect, separate, overrides, rules_regions, rules_fixes, "
        "rules_excluded, extraction_notes). A key you give is replaced as a whole. Returns what "
        "the config holds now, or the validation error (then nothing is saved).",
        {
            "type": "object",
            "properties": {
                "changes": {
                    "type": "object",
                    "description": "Top-level config keys and their new values.",
                }
            },
            "required": ["changes"],
        },
        _update_config,
    ),
    "view_images": (
        f"Open images so you can see them. `paths` are run-relative paths such as "
        f"'work/preview/items_1.png'. Open all images of a round in one call (max "
        f"{MAX_IMAGES_PER_CALL}).",
        {
            "type": "object",
            "properties": {"paths": {"type": "array", "items": {"type": "string"}}},
            "required": ["paths"],
        },
        _view_images,
    ),
    "crop": (
        "Cut every item out of the component pages, following the layouts in the config.",
        NO_ARGS,
        _crop,
    ),
    "group": (
        "Group pixel-identical fronts into designs and match backs. Run after crop.",
        NO_ARGS,
        _group,
    ),
    "orient": (
        "Read cheaply which way each design's text runs and print ORIENTATION lines for items to "
        "turn. Run after group.",
        NO_ARGS,
        _orient,
    ),
    "preview": (
        "Draw the rules regions on work/preview/regions_*.png and flag printed text outside "
        "every region as UNCOVERED.",
        NO_ARGS,
        _preview,
    ),
    "read": (
        "Read every design and every rules region with reader calls, then run check. Takes "
        "minutes. Reads are cached, so after a config change only changed parts are read again.",
        {
            "type": "object",
            "properties": {
                "designs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Only read these designs (e.g. ['d003']). Default: all.",
                }
            },
        },
        _read,
    ),
    "read_rules": (
        "Read the rules regions again (only changed regions are read), then run preview.",
        NO_ARGS,
        _read_rules,
    ),
    "check": (
        "Run the consistency checks and print every flag with what to do about it.",
        NO_ARGS,
        _check,
    ),
    "assemble": (
        "Write work/components.json, results/rules.md, results/components.json and "
        "work/review.html, and validate them. Fix the config until it prints VALID.",
        {"type": "object", "properties": {"force": {"type": "boolean"}}},
        _assemble,
    ),
    "cost": (
        "Print what the reader calls cost so far.",
        NO_ARGS,
        _cost,
    ),
}

TOOL_NAMES = list(TOOLS)


def allowed_tool_names() -> list[str]:
    """The names the agent session may call: `mcp__extract__<name>`."""
    return [f"mcp__{SERVER_NAME}__{name}" for name in TOOLS]


# ---------------------------------------------------------------- running a tool


async def run_tool(ctx: Context, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Runs one tool and returns an MCP result: `content`, and `is_error` when the step failed."""
    if name not in TOOLS:
        return _error_result(f"unknown tool {name!r}; tools: {', '.join(TOOLS)}")
    function = TOOLS[name][2]
    try:
        output = await function(ctx, args or {})
    except (ExtractionError, ReaderError) as e:
        return _error_result(str(e))
    except Exception as e:
        # A bug in a step must not end the agent session; the agent reports it in its reply.
        log.exception("tool %s failed", name)
        return _error_result(f"{name} failed unexpectedly: {e!r}")
    content = [{"type": "text", "text": output}] if isinstance(output, str) else output
    return {"content": content}


def _error_result(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": message}], "is_error": True}


def build_server(ws: Workspace, reader: Reader, limits: ReadLimits) -> McpSdkServerConfig:
    ctx = Context(ws, reader, limits)

    def make_tool(name: str, description: str, schema: dict[str, Any]) -> SdkMcpTool[Any]:
        async def handler(args: dict[str, Any]) -> dict[str, Any]:
            return await run_tool(ctx, name, args)

        return SdkMcpTool(name=name, description=description, input_schema=schema, handler=handler)

    tools = [
        make_tool(name, description, schema) for name, (description, schema, _) in TOOLS.items()
    ]
    return create_sdk_mcp_server(SERVER_NAME, tools=tools)


async def call_tool(
    ws: Workspace, reader: Reader, limits: ReadLimits, name: str, args: dict[str, Any]
) -> str:
    """Runs one step by name, without MCP. Images show as `[image]`; an error as `ERROR: ...`."""
    result = await run_tool(Context(ws, reader, limits), name, args)
    parts = [block["text"] if block["type"] == "text" else "[image]" for block in result["content"]]
    text = "\n".join(parts)
    return f"ERROR: {text}" if result.get("is_error") else text
