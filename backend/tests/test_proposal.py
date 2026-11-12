import asyncio
import json

import pytest
from fake_results import PROPOSAL, write_results

from app.extraction.models import GameModel
from app.extraction.proposal import propose_model
from app.extraction.reader import RecordedReader
from app.extraction.workspace import ExtractionError, load_json


def test_proposal_is_validated_and_saved(ws):
    write_results(ws)
    reader = RecordedReader(lambda images, prompt, schema: PROPOSAL, cost_usd=0.01, model="m")

    model = asyncio.run(propose_model(ws, reader))

    saved = GameModel.model_validate(load_json(ws.results / "game_model_v1.json"))
    assert saved == model
    assert saved.game.title == "Test Game"
    assert saved.rules.startswith("On your turn")
    assert saved.action_kinds[0].id == "play_card"
    assert saved.variables[0].default == 5
    assert load_json(ws.work / "proposal.json") == {"cost_usd": 0.01, "model": "m"}


def test_reader_gets_no_images_and_the_schema(ws):
    write_results(ws)
    seen = []

    def respond(images, prompt, schema):
        seen.append((images, schema))
        return PROPOSAL

    asyncio.run(propose_model(ws, RecordedReader(respond)))

    assert seen[0][0] == []
    assert "action_kinds" in seen[0][1]["properties"]


def test_invalid_answer_is_asked_again_once(ws):
    write_results(ws)
    answers = [{"action_kinds": "nope", "variables": []}, PROPOSAL]
    reader = RecordedReader(lambda images, prompt, schema: answers.pop(0), cost_usd=0.01)

    asyncio.run(propose_model(ws, reader))

    assert len(reader.calls) == 2
    assert "Your previous answer was not valid" in reader.calls[1]
    assert load_json(ws.work / "proposal.json")["cost_usd"] == pytest.approx(0.02)


def test_two_invalid_answers_raise(ws):
    write_results(ws)
    reader = RecordedReader(lambda images, prompt, schema: json.loads('{"variables": []}'))

    with pytest.raises(ExtractionError, match="not valid after two tries"):
        asyncio.run(propose_model(ws, reader))

    assert len(reader.calls) == 2
    assert not (ws.results / "game_model_v1.json").exists()


def test_results_are_needed(ws):
    with pytest.raises(ExtractionError, match="needed first"):
        asyncio.run(propose_model(ws, RecordedReader(lambda *_: PROPOSAL)))
