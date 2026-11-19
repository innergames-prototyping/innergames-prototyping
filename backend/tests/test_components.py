import asyncio
from typing import Any

import pytest
from PIL import Image

from app.extraction.components import (
    DesignTarget,
    apply_override,
    build_resolved,
    design_targets,
    expand_rules_items,
    image_id,
    kind_hashes,
    mismatched_kinds,
    noted,
    read_index,
    reader_prompt,
    reader_schema,
    resolve,
)
from app.extraction.models import ExtractionConfig
from app.extraction.queue import ReadLimits, run_reads
from app.extraction.reader import RecordedReader
from app.extraction.workspace import Workspace, save_json

CONFIG = {
    "game": {"title": "Test"},
    "kinds": [
        {
            "id": "card",
            "name": "Card",
            "description": "A card with gold.",
            "fields": [{"name": "gold", "type": "integer", "description": "Coins."}],
        },
        {
            "id": "mode",
            "name": "Mode",
            "description": "A mode.",
            "fields": [
                {"name": "side", "type": "enum", "enum_values": ["a", "b"], "description": "x"}
            ],
        },
    ],
}


def output(gold=2, title="Axe", direction="upright", text=None, kind="card", mismatch="none"):
    fields: dict[str, Any] = {"card": None, "mode": None}
    if kind == "card":
        fields["card"] = {"gold": gold}
    return {
        "observations": "",
        "text_direction": direction,
        "kind": kind,
        "title": title,
        "fields": fields,
        "mismatch": mismatch,
        "text": text,
        "misspelled": [],
        "unreadable": "",
    }


def read(out, key="k1"):
    return {"output": out, "item": key}


@pytest.fixture
def cfg() -> ExtractionConfig:
    return ExtractionConfig.model_validate(CONFIG)


@pytest.fixture
def tiny(ws: Workspace, cfg: ExtractionConfig) -> Workspace:
    """One design d001 with two copies, k1 and k2."""
    save_json(ws.config_path, CONFIG)
    save_json(ws.work / "groups.json", {"designs": {"d001": ["k1", "k2"]}, "backs": {}})
    save_json(
        ws.work / "items.json",
        [
            {"key": k, "file": "c.pdf", "page": 1, "row": 0, "col": i}
            for i, k in enumerate(["k1", "k2"])
        ],
    )
    for key in ("k1", "k2"):
        (ws.work / "items" / key).mkdir(parents=True)
        Image.new("RGB", (20, 20), "white").save(ws.work / "items" / key / "front.png")
    return ws


def run_target(ws, cfg, reader, limits=None, designs=None):
    limits = limits or ReadLimits()
    targets = design_targets(ws, cfg, reader, limits, designs)
    asyncio.run(run_reads(list(targets), limits.parallel))
    return targets


# ---------------------------------------------------------------- schema and prompt


def test_reader_schema_has_an_object_per_kind(cfg):
    schema = reader_schema(cfg)
    assert schema["properties"]["kind"]["enum"] == ["card", "mode", "other"]
    assert schema["properties"]["fields"]["required"] == ["card", "mode"]
    side = schema["properties"]["fields"]["properties"]["mode"]["properties"]["side"]
    assert side == {"enum": ["a", "b", None]}


def test_reader_prompt_mentions_the_back_only_when_there_is_one(cfg):
    assert "image 2 is its back" in reader_prompt(cfg, True)
    assert "image 2" not in reader_prompt(cfg, False)
    assert "Allowed values: a, b." in reader_prompt(cfg, False)


# ---------------------------------------------------------------- resolve


def test_resolve_takes_the_majority_of_every_value(cfg):
    reads = [read(output(2)), read(output(2)), read(output(3, title="Axe "))]
    values, unsettled, text_ok = resolve(cfg, reads)
    assert values["kind"] == "card"
    assert values["title"] == "Axe"
    assert values["fields"] == {"gold": 2}
    assert unsettled == []
    assert text_ok


def test_resolve_leaves_a_value_without_majority_unsettled(cfg):
    reads = [read(output(1)), read(output(2)), read(output(3))]
    values, unsettled, _ = resolve(cfg, reads)
    assert values["fields"] == {"gold": None}
    assert unsettled == ["fields.gold"]
    assert values["votes"]["fields.gold"] == [1, 2, 3]


def test_resolve_without_a_kind_majority(cfg):
    reads = [read(output(kind="card")), read(output(kind="mode"))]
    values, unsettled, text_ok = resolve(cfg, reads)
    assert unsettled == ["kind"]
    assert values["votes"]["kind"] == ["card", "mode"]
    assert not text_ok


def test_resolve_uses_the_kind_of_an_override(cfg):
    reads = [read(output(kind="card")), read(output(kind="mode"))]
    values, _, _ = resolve(cfg, reads, kind="card")
    assert values["kind"] == "card"


def test_resolve_merges_text_and_reports_conflicts(cfg):
    agree = [read(output(text="Pay 3 gold.")) for _ in range(2)]
    assert resolve(cfg, agree)[0]["text"] == "Pay 3 gold."
    split = [read(output(text="Pay 3 gold.")), read(output(text="Pay 5 gold."))]
    values, _, text_ok = resolve(cfg, split)
    assert not text_ok
    assert values["votes"]["text"]


def test_apply_override_sets_fields_and_plain_values():
    values = {"title": "A", "fields": {"gold": 1}}
    apply_override(values, {"fields.gold": 3, "title": "B"})
    assert values == {"title": "B", "fields": {"gold": 3}}


def test_noted_and_mismatched_kinds():
    assert not noted("None.") and not noted("") and noted("strip is on top")
    bad = {"d1": [read(output(mismatch="wrong")) for _ in range(3)] + [read(output())]}
    assert mismatched_kinds(bad) == {"card"}
    assert mismatched_kinds({"d1": bad["d1"][:3]}) == set()


# ---------------------------------------------------------------- read files


def write_read(ws, design, n, key, out, **extra):
    cfg = ExtractionConfig.model_validate(CONFIG)
    record = {
        "item": key,
        "image": image_id(ws, key),
        "kind_def": kind_hashes(cfg)[out["kind"]],
        "output": out,
        "cost_usd": 0.01,
    } | extra
    save_json(ws.work / "reads" / design / f"{n:02d}.json", record)


def test_kind_hashes_change_with_the_description(cfg):
    changed = ExtractionConfig.model_validate(
        CONFIG | {"kinds": [{**CONFIG["kinds"][0], "description": "Other."}, CONFIG["kinds"][1]]}
    )
    before, after = kind_hashes(cfg), kind_hashes(changed)
    assert before["mode"] == after["mode"]
    assert before["card"] != after["card"]
    assert before["other"] != after["other"]


def test_read_index_keeps_only_reads_of_the_current_crop_and_kind(tiny, cfg):
    write_read(tiny, "d001", 0, "k1", output())
    write_read(tiny, "d001", 1, "k1", output(), image="stale")
    write_read(tiny, "d001", 2, "k1", output(), kind_def="old description")
    index = read_index(tiny, cfg)
    assert len(index["k1"]) == 1


def test_build_resolved_from_handwritten_reads(tiny, cfg):
    write_read(tiny, "d001", 0, "k1", output(2, text="Hi"))
    write_read(tiny, "d001", 1, "k2", output(2, text="Hi"))
    groups, designs = build_resolved(tiny, cfg)
    d = designs["d001"]
    assert groups["designs"] == {"d001": ["k1", "k2"]}
    assert d["kind"] == "card" and d["read_kind"] == "card"
    assert d["fields"] == {"gold": 2}
    assert d["text"] == "Hi"
    assert d["reads"] == 2
    assert d["unsettled"] == [] and d["unanimous"] and not d["overridden"]
    assert d["orientation"] is None


def test_build_resolved_applies_overrides_and_reports_unread(tiny):
    config = CONFIG | {
        "overrides": {"d001": {"set": {"fields.gold": 7}, "reason": "counted"}},
    }
    cfg = ExtractionConfig.model_validate(config)
    assert build_resolved(tiny, cfg)[1]["d001"] == {
        "members": ["k1", "k2"],
        "reads": 0,
        "unsettled": ["unread"],
    }
    write_read(tiny, "d001", 0, "k1", output(1))
    write_read(tiny, "d001", 1, "k2", output(2))
    d = build_resolved(tiny, cfg)[1]["d001"]
    assert d["fields"] == {"gold": 7}
    assert d["unsettled"] == []
    assert d["overridden"]


def test_expand_rules_items(cfg):
    config = CONFIG | {
        "rules_items": [
            {
                "kind": "card",
                "count": 2,
                "source": {"file": "rules.pdf", "page": 3},
                "title": "Coin",
                "fields": {"gold": 1},
            }
        ]
    }
    items = expand_rules_items(ExtractionConfig.model_validate(config))
    assert [i.id for i in items] == ["rules#p3_card_01", "rules#p3_card_02"]
    assert items[0].fields == {"gold": 1}
    assert items[0].from_rules and items[0].confidence == "high"


# ---------------------------------------------------------------- DesignTarget


def test_design_reads_stop_at_two_identical_reads(tiny, cfg):
    reader = RecordedReader(lambda *_: output())
    targets = run_target(tiny, cfg, reader)
    assert len(reader.calls) == 2
    assert len(targets[0].reads) == 2
    saved = sorted((tiny.work / "reads" / "d001").glob("*.json"))
    assert [p.name for p in saved] == ["00.json", "01.json"]
    first = read_index(tiny, cfg)
    assert len(first["k1"]) + len(first["k2"]) == 2
    record = first["k1"][0]
    assert record["model"] == "recorded" and record["cost_usd"] == 0.001


def test_design_reads_go_on_up_to_max_reads_when_values_differ(tiny, cfg):
    calls = iter(range(1, 100))
    reader = RecordedReader(lambda *_: output(gold=next(calls)))
    run_target(tiny, cfg, reader)
    assert len(reader.calls) == 5


def test_design_reads_respect_a_lower_max_reads(tiny, cfg):
    calls = iter(range(1, 100))
    reader = RecordedReader(lambda *_: output(gold=next(calls)))
    run_target(tiny, cfg, reader, ReadLimits(min_reads=2, max_reads=3))
    assert len(reader.calls) == 3


def test_a_sideways_first_read_stops_further_reads(tiny, cfg):
    reader = RecordedReader(lambda *_: output(direction="bottom to top"))
    run_target(tiny, cfg, reader)
    assert len(reader.calls) == 1


def test_an_upright_override_lets_reading_go_on(tiny):
    config = CONFIG | {
        "overrides": {"d001": {"set": {"orientation": "upright"}, "reason": "checked"}}
    }
    cfg = ExtractionConfig.model_validate(config)
    reader = RecordedReader(lambda *_: output(direction="bottom to top"))
    run_target(tiny, cfg, reader)
    assert len(reader.calls) == 2


def test_reading_stops_when_the_kind_description_does_not_fit(tiny, cfg):
    reader = RecordedReader(lambda *_: output(gold=None, mismatch="strip is on top"))
    # Four earlier reads that all say so: nothing more is asked.
    for n in range(4):
        write_read(tiny, "d001", n, "k1", output(mismatch="strip is on top"))
    run_target(tiny, cfg, reader)
    assert reader.calls == []


def test_existing_reads_are_kept_and_numbering_goes_on(tiny, cfg):
    write_read(tiny, "d001", 0, "k1", output())
    reader = RecordedReader(lambda *_: output())
    run_target(tiny, cfg, reader)
    assert len(reader.calls) == 1
    assert (tiny.work / "reads" / "d001" / "01.json").exists()


def test_the_designs_filter_limits_the_targets(tiny, cfg):
    targets = design_targets(tiny, cfg, RecordedReader(lambda *_: output()), ReadLimits(), ["d009"])
    assert targets == []
    assert isinstance(
        design_targets(tiny, cfg, RecordedReader(lambda *_: output()), ReadLimits(), ["d001"])[0],
        DesignTarget,
    )
