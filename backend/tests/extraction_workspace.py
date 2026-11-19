"""A hand-made workspace with reads on disk, for the check and assemble tests (no model, no PDF)."""

import hashlib
from typing import Any

from app.extraction import rules
from app.extraction.workspace import Workspace, save_json

CONFIG: dict[str, Any] = {
    "game": {"title": "Test Game"},
    "sources": [{"file": "rules.pdf", "pages": 1, "content": "rules"}],
    "kinds": [
        {
            "id": "card",
            "name": "Card",
            "description": "A card with a value.",
            "fields": [{"name": "value", "type": "integer", "description": "The value."}],
            "count_in_rules": 3,
        },
        {"id": "tile", "name": "Tile", "description": "A square tile."},
    ],
    "rules_regions": [{"file": "rules.pdf", "page": 1, "box": [0, 0, 1, 1]}],
}

ITEMS = ["k1", "k2", "k3", "k4"]
GROUPS = {
    "designs": {"d001": ["k1", "k2"], "d002": ["k3"], "d003": ["k4"]},
    "backs": {"b01": ["k1", "k4"]},
}


def read_output(kind: str, title: str | None, value: int | None = None) -> dict[str, Any]:
    fields: dict[str, Any] = {"card": None, "tile": None}
    if kind == "card":
        fields["card"] = {"value": value}
    return {
        "observations": "",
        "text_direction": "upright",
        "kind": kind,
        "title": title,
        "fields": fields,
        "mismatch": "none",
        "text": None,
        "misspelled": [],
        "unreadable": "",
    }


def write_read(ws: Workspace, design: str, n: int, key: str, output: dict[str, Any]) -> None:
    front = (ws.work / "items" / key / "front.png").read_bytes()
    save_json(
        ws.work / "reads" / design / f"{n:02d}.json",
        {
            "item": key,
            "image": hashlib.sha1(front).hexdigest()[:12],
            "output": output,
            "cost_usd": 0.01,
        },
    )


def build(
    ws: Workspace,
    config: dict[str, Any] | None = None,
    d002_values=(1, 2),
    d002_titles=("Gold", "Gold"),
) -> None:
    """Designs d001 (two copies, value 1), d002 (value as given) and d003 (a tile)."""
    cfg = config or CONFIG
    save_json(ws.config_path, cfg)
    save_json(ws.work / "groups.json", GROUPS)
    save_json(
        ws.work / "items.json",
        [
            {"key": k, "file": "cards.pdf", "page": 1, "row": 1, "col": i + 1}
            for i, k in enumerate(ITEMS)
        ],
    )
    for key in ITEMS:
        (ws.work / "items" / key).mkdir(parents=True)
        (ws.work / "items" / key / "front.png").write_bytes(key.encode())
    write_read(ws, "d001", 0, "k1", read_output("card", "Gold", 1))
    write_read(ws, "d001", 1, "k2", read_output("card", "Gold", 1))
    write_read(ws, "d002", 0, "k3", read_output("card", d002_titles[0], d002_values[0]))
    write_read(ws, "d002", 1, "k3", read_output("card", d002_titles[1], d002_values[1]))
    write_read(ws, "d003", 0, "k4", read_output("tile", "Tile"))
    write_read(ws, "d003", 1, "k4", read_output("tile", "Tile"))


def write_rules(ws: Workspace, text: str = "# Rules\nPlay cards.") -> None:
    """The transcription of the one region, as `read_rules` leaves it."""
    cfg = ws.load_config()
    save_json(
        ws.work / "rules" / "regions.json", {str(i): k for i, k in rules.region_keys(cfg).items()}
    )
    (ws.work / "rules" / "region_00.txt").write_text(text)
