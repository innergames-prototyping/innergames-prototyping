import asyncio
from typing import Any

import pytest
from extraction_workspace import CONFIG as ASSEMBLE_CONFIG
from extraction_workspace import build, read_output, write_rules
from PIL import Image

from app.extraction.assemble import assemble
from app.extraction.check import run_check
from app.extraction.components import (
    build_resolved,
    design_targets,
    image_id,
    kind_hashes,
    own_backs,
    read_index,
    reader_prompt,
    reader_schema,
    resolve,
)
from app.extraction.images import MAX_SIDE, TILE_SIDE, tiles
from app.extraction.models import ExtractionConfig, Override
from app.extraction.queue import ReadLimits, run_reads
from app.extraction.reader import RecordedReader
from app.extraction.voting import clean, placed_elsewhere
from app.extraction.workspace import Workspace, load_json, save_json

CONFIG = {
    "game": {"title": "Test"},
    "kinds": [
        {
            "id": "card",
            "name": "Card",
            "description": "A card with gold.",
            "fields": [{"name": "gold", "type": "integer", "description": "Coins."}],
        }
    ],
}


def output(text=None, **extra) -> dict[str, Any]:
    return {
        "observations": "",
        "text_direction": "upright",
        "kind": "card",
        "title": "Axe",
        "fields": {"card": {"gold": 2}},
        "mismatch": "none",
        "text": text,
        "misspelled": [],
        "unreadable": "",
    } | extra


@pytest.fixture
def cfg() -> ExtractionConfig:
    return ExtractionConfig.model_validate(CONFIG)


def make_items(ws: Workspace, groups: dict, with_back: set[str], size=(20, 20)) -> None:
    save_json(ws.config_path, CONFIG)
    save_json(ws.work / "groups.json", groups)
    keys = [key for members in groups["designs"].values() for key in members]
    for key in keys:
        folder = ws.item_dir(key)
        folder.mkdir(parents=True)
        Image.new("RGB", size, "white").save(folder / "front.png")
        if key in with_back:
            Image.new("RGB", (20, 20), "gray").save(folder / "back.png")


def run_targets(ws, cfg, reader):
    limits = ReadLimits()
    asyncio.run(run_reads(list(design_targets(ws, cfg, reader, limits)), limits.parallel))


def save_read(ws, cfg, design, n, key, out):
    record = {
        "item": key,
        "image": image_id(ws, key),
        "kind_def": kind_hashes(cfg)[out["kind"]],
        "output": out,
        "cost_usd": 0.01,
    }
    save_json(ws.work / "reads" / design / f"{n:02d}.json", record)


OWN = {"designs": {"d001": ["k1"], "d002": ["k2"]}, "backs": {"b01": ["k1"], "b02": ["k2"]}}
SHARED = {"designs": {"d001": ["k1"], "d002": ["k2"]}, "backs": {"b01": ["k1", "k2"]}}


# ---------------------------------------------------------------- which backs are a card's own


def test_own_backs_are_those_no_other_design_shares():
    groups = {
        "designs": {"d001": ["k1", "k2"], "d002": ["k3"], "d003": ["k4"], "d004": ["k5"]},
        "backs": {"b01": ["k1", "k2"], "b02": ["k3", "k4"]},
    }
    assert own_backs(groups) == {"d001"}


def test_a_design_with_one_shared_back_is_not_own():
    groups = {
        "designs": {"d001": ["k1", "k2"], "d002": ["k3"]},
        "backs": {"b01": ["k1"], "b02": ["k2", "k3"]},
    }
    assert own_backs(groups) == set()


def test_own_backs_without_back_groups():
    assert own_backs({"designs": {"d001": ["k1"]}}) == set()


# ---------------------------------------------------------------- what readers are asked


def test_schema_and_prompt_ask_for_the_back_only_when_it_is_own(cfg):
    assert "back_text" not in reader_schema(cfg)["properties"]
    schema = reader_schema(cfg, own_back=True)
    assert "back_text" in schema["required"]
    assert "back_text" in schema["properties"]

    own = reader_prompt(cfg, True, own_back=True)
    assert "- back_text:" in own
    assert "take no title or text from the back" not in own
    shared = reader_prompt(cfg, True)
    assert "back_text" not in shared
    assert "take no title or text from the back" in shared


@pytest.mark.parametrize(("has_back", "numbers"), [(False, "2 to 7"), (True, "3 to 8")])
def test_prompt_numbers_the_tiles_after_the_front_and_back(cfg, has_back, numbers):
    prompt = reader_prompt(cfg, has_back, grid=(2, 3))
    assert f"Images {numbers} are the same front cut into 2 rows of 3 tiles" in prompt


def test_prompt_without_tiles_does_not_mention_them(cfg):
    assert "tiles" not in reader_prompt(cfg, False)


def test_own_back_is_read_voted_and_kept(ws, cfg):
    make_items(ws, OWN, {"k1", "k2"})
    schemas = []

    def respond(images, prompt, schema):
        schemas.append(schema)
        return output(back_text="Gain &amp; keep")

    run_targets(ws, cfg, RecordedReader(respond))

    assert all("back_text" in s["properties"] for s in schemas)
    _, designs = build_resolved(ws, cfg)
    assert designs["d001"]["back"] == "Gain & keep"
    assert designs["d001"]["text_settled"]


def test_shared_back_is_not_read(ws, cfg):
    make_items(ws, SHARED, {"k1", "k2"})
    schemas = []

    def respond(images, prompt, schema):
        schemas.append(schema)
        return output()

    run_targets(ws, cfg, RecordedReader(respond))

    assert schemas and all("back_text" not in s["properties"] for s in schemas)
    _, designs = build_resolved(ws, cfg)
    assert designs["d001"]["back"] is None


def test_a_copy_without_a_back_image_keeps_its_reads(ws, cfg):
    groups = {"designs": {"d001": ["k1", "k2"]}, "backs": {"b01": ["k1"]}}
    make_items(ws, groups, {"k1"})
    save_read(ws, cfg, "d001", 0, "k1", output(back_text="Back"))
    save_read(ws, cfg, "d001", 1, "k2", output())

    index = read_index(ws, cfg)

    assert len(index["k1"]) == 1
    assert len(index["k2"]) == 1


def test_reads_from_before_the_back_counted_are_not_reused(ws, cfg):
    make_items(ws, OWN, {"k1", "k2"})
    save_read(ws, cfg, "d001", 0, "k1", output())
    save_read(ws, cfg, "d001", 1, "k1", output(back_text="Back"))
    assert [r["output"]["back_text"] for r in read_index(ws, cfg)["k1"]] == ["Back"]


def test_reads_of_a_back_that_became_shared_are_not_reused(ws, cfg):
    make_items(ws, SHARED, {"k1", "k2"})
    save_read(ws, cfg, "d001", 0, "k1", output(back_text="Back"))
    assert read_index(ws, cfg)["k1"] == []


def test_clean_undoes_reader_quirks_in_the_back_text():
    assert clean({"back_text": "null"})["back_text"] is None
    assert clean({"back_text": " A &amp; B "})["back_text"] == "A & B"


def test_disputed_back_text_leaves_the_text_unsettled(cfg):
    reads = [
        {"output": output(back_text="Pay 3 gold.")},
        {"output": output(back_text="Pay 5 gold.")},
    ]
    values, _, text_settled = resolve(cfg, reads)
    assert not text_settled
    assert values["votes"]["back"]


def test_override_accepts_the_back():
    assert Override(set={"back": "Printed"}, reason="read at full size").set["back"] == "Printed"


# ---------------------------------------------------------------- check and assemble


def with_own_back_on_k3(ws: Workspace, back_texts: tuple[str, str]) -> None:
    """Design d002 (item k3) gets a back of its own, with these two reads of its text."""
    groups = load_json(ws.work / "groups.json")
    groups["backs"]["b02"] = ["k3"]
    save_json(ws.work / "groups.json", groups)
    (ws.work / "items" / "k3" / "back.png").write_bytes(b"back")
    for n, text in enumerate(back_texts):
        out = read_output("card", "Gold", 2) | {"back_text": text}
        record = {"item": "k3", "image": image_id(ws, "k3"), "output": out, "cost_usd": 0.01}
        save_json(ws.work / "reads" / "d002" / f"{n:02d}.json", record)


def test_check_reports_a_disputed_back_as_uncertain_text(ws: Workspace):
    build(ws, ASSEMBLE_CONFIG, d002_values=(2, 2))
    with_own_back_on_k3(ws, ("Pay 3 gold.", "Pay 5 gold."))

    out = run_check(ws)

    assert "TEXT UNCERTAIN d002" in out
    assert "Pay 5 gold." in out
    assert "`back` for text on a component's own back" in out


def test_assemble_exports_the_back(ws: Workspace):
    build(ws, ASSEMBLE_CONFIG, d002_values=(2, 2))
    write_rules(ws)
    with_own_back_on_k3(ws, ("Draw one.", "Draw one."))

    assert "VALID" in assemble(ws)

    exported = load_json(ws.results / "components.json")["components"]
    assert [c["back"] for c in exported if "back" in c] == ["Draw one."]


# ---------------------------------------------------------------- uncertain text


def test_labels_in_another_order_are_not_a_disagreement():
    spans = [{"kept": "Forest / Lake", "alternatives": ["Lake / Forest"]}]
    assert placed_elsewhere(spans, "Forest / Lake / Hill\n") == []


def test_a_word_the_text_lacks_stays_flagged():
    spans = [{"kept": "Pay 3 gold", "alternatives": ["Pay 5 gold"]}]
    assert placed_elsewhere(spans, "Pay 3 gold\n") == spans


# ---------------------------------------------------------------- tiles


def test_an_image_up_to_twice_the_read_size_is_not_tiled():
    assert tiles(Image.new("RGB", (2 * MAX_SIDE, 100))) == (0, 0, [])


def test_a_large_image_is_cut_into_overlapping_tiles():
    img = Image.new("RGB", (2 * TILE_SIDE + 1, TILE_SIDE))

    rows, cols, parts = tiles(img)

    assert (rows, cols) == (1, 3)
    assert len(parts) == 3
    assert all(part.height == TILE_SIDE for part in parts)
    third = img.width / 3
    assert parts[0].width > third
    assert parts[1].width > parts[0].width


def test_tiles_cover_the_whole_image_in_reading_order():
    img = Image.effect_noise((4000, 4000), 50).convert("RGB")

    rows, cols, parts = tiles(img)

    assert (rows, cols) == (2, 2)
    assert parts[0].getpixel((0, 0)) == img.getpixel((0, 0))
    last = parts[-1]
    assert last.getpixel((last.width - 1, last.height - 1)) == img.getpixel((3999, 3999))


def test_a_large_front_is_sent_with_its_tiles(ws, cfg):
    groups = {"designs": {"d001": ["k1"]}, "backs": {}}
    make_items(ws, groups, set(), size=(2 * TILE_SIDE, 100))
    sent = []

    def respond(images, prompt, schema):
        sent.append(len(images))
        return output()

    reader = RecordedReader(respond)
    run_targets(ws, cfg, reader)

    assert sent and set(sent) == {3}
    assert "Images 2 to 3 are the same front" in reader.calls[0]
