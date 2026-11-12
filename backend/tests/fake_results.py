"""Shared helpers for the tests of the agent, proposal, runs and API: fake results and answers."""

import json
from pathlib import Path

from app.extraction.workspace import Workspace

COMPONENTS = {
    "game": {"title": "Test Game", "credits": []},
    "component_kinds": [{"id": "card", "name": "Card"}],
    "components": [{"kind": "card", "count": 3, "title": "Ace"}],
}

PROPOSAL = {
    "action_kinds": [
        {
            "id": "play_card",
            "name": "Play a card",
            "description": "The player puts a card from the hand on the table.",
            "rules_quote": "On your turn, play one card.",
        }
    ],
    "variables": [
        {
            "name": "starting_hand_size",
            "description": "Cards each player holds at the start.",
            "type": "integer",
            "default": 5,
            "rules_quote": "Each player starts with 5 cards.",
        }
    ],
}


def write_results(ws: Workspace) -> None:
    """What a finished agent session leaves in `results/`."""
    (ws.results / "rules.md").write_text("On your turn, play one card.\n")
    (ws.results / "components.json").write_text(json.dumps(COMPONENTS))


def png(path: Path, size: tuple[int, int] = (20, 10)) -> Path:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, "white").save(path)
    return path
