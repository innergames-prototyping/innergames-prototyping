import asyncio

from fake_results import png

from app.extraction.queue import ReadLimits
from app.extraction.reader import RecordedReader
from app.extraction.tools import (
    TOOL_NAMES,
    Context,
    allowed_tool_names,
    build_server,
    call_tool,
    run_tool,
)
from app.extraction.workspace import load_json

READER = RecordedReader(lambda *_: {})
LIMITS = ReadLimits()


def call(ws, name, args):
    return asyncio.run(call_tool(ws, READER, LIMITS, name, args))


def test_tool_names():
    assert "update_config" in TOOL_NAMES
    assert "mcp__extract__view_images" in allowed_tool_names()
    assert len(allowed_tool_names()) == len(TOOL_NAMES)


def test_server_has_the_name_extract(ws):
    server = build_server(ws, READER, LIMITS)
    assert server["type"] == "sdk"
    assert server["name"] == "extract"


def test_valid_config_change_is_saved(ws):
    text = call(ws, "update_config", {"changes": {"game": {"title": "Test"}}})

    assert "config saved" in text
    assert "game: Test" in text
    assert load_json(ws.config_path) == {"game": {"title": "Test"}}


def test_changes_replace_whole_keys(ws):
    call(ws, "update_config", {"changes": {"extraction_notes": ["a", "b"]}})
    text = call(ws, "update_config", {"changes": {"extraction_notes": ["c"]}})

    assert "extraction_notes: 1 entries" in text


def test_invalid_config_change_returns_the_error_and_saves_nothing(ws):
    text = call(ws, "update_config", {"changes": {"layouts": [{"method": "grid"}]}})

    assert text.startswith("ERROR: config not saved")
    assert not ws.config_path.exists()


def test_unknown_config_key_is_refused(ws):
    text = call(ws, "update_config", {"changes": {"colour": 1}})

    assert text.startswith("ERROR")
    assert not ws.config_path.exists()


def test_view_images_returns_image_blocks(ws):
    png(ws.work / "preview" / "a.png")

    result = asyncio.run(
        run_tool(Context(ws, READER, LIMITS), "view_images", {"paths": ["work/preview/a.png"]})
    )

    text_block, image_block = result["content"]
    assert text_block == {"type": "text", "text": "work/preview/a.png"}
    assert image_block["type"] == "image"
    assert image_block["mimeType"] == "image/png"
    assert image_block["data"]
    assert "is_error" not in result


def test_view_images_refuses_paths_outside_the_run(ws):
    png(ws.root.parent / "x.png")

    text = call(ws, "view_images", {"paths": ["../x.png"]})

    assert text.startswith("ERROR")
    assert "outside the run folder" in text


def test_view_images_refuses_other_files_and_too_many(ws):
    (ws.work / "notes.txt").write_text("hi")

    assert "not an image" in call(ws, "view_images", {"paths": ["work/notes.txt"]})
    assert "does not exist" in call(ws, "view_images", {"paths": ["work/missing.png"]})
    assert "at most 20" in call(ws, "view_images", {"paths": ["a.png"] * 21})


def test_unknown_tool_is_an_error(ws):
    assert call(ws, "nope", {}).startswith("ERROR: unknown tool")
