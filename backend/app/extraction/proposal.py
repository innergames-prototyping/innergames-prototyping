"""The first game model: action kinds and game variables, proposed from the extracted rules.

After the agent session, one tool-less reader call (no images) reads `results/rules.md` and lists
what a later step needs:

- action kinds: the things a player does on a turn (each gets a time later), and
- game variables: the numbers or switches the rules set, with the default the rules print.

The answer is validated with Pydantic. When it is invalid, the reader gets the error and one more
try. The result is saved as `results/game_model_v1.json`.
"""

from pydantic import ValidationError

from .models import ComponentsFile, GameModel, ModelProposal
from .reader import Reader
from .workspace import ExtractionError, Workspace, save_json

PROMPT = """\
Below are the rules of a board game, as extracted from its rulebook. List two things.

1. Action kinds: the things a player does on a turn (for example "play a card", "move a pawn",
   "draw cards"). They are used later to give each kind a time. Group the same sort of action
   under one kind.
2. Game variables: the numbers or switches the rules set (for example the starting hand size or
   the number of rounds). Give each the default value the rules print.

Rules for your answer:
- Use only what the rules say. Do not guess, and do not use what you know about the game.
- Give every action kind and every variable the rules sentence it comes from, copied word for
  word.
- A variable the rules do not print a value for gets the default null.
- Ids and names are lowercase with letters, digits and underscores, e.g. "starting_hand_size".

RULES:
{rules}
"""

RETRY_PROMPT = """\
{prompt}
Your previous answer was not valid:
{error}
Answer again and fix this.
"""


async def propose_model(ws: Workspace, reader: Reader) -> GameModel:
    """Reads the rules, saves `results/game_model_v1.json` and `work/proposal.json`."""
    rules_path = ws.results / "rules.md"
    components_path = ws.results / "components.json"
    if not rules_path.exists() or not components_path.exists():
        raise ExtractionError("results/rules.md and results/components.json are needed first")
    rules = rules_path.read_text()
    components = ComponentsFile.model_validate_json(components_path.read_text())

    proposal, cost = await _ask_for_proposal(reader, rules)
    model = GameModel(
        game=components.game,
        rules=rules,
        components=components,
        action_kinds=proposal.action_kinds,
        variables=proposal.variables,
    )
    save_json(ws.results / "game_model_v1.json", model.model_dump(mode="json"))
    save_json(ws.work / "proposal.json", {"cost_usd": cost, "model": reader.model})
    return model


async def _ask_for_proposal(reader: Reader, rules: str) -> tuple[ModelProposal, float]:
    """The validated proposal and the cost of all calls; asks twice at most."""
    schema = ModelProposal.model_json_schema()
    prompt = PROMPT.format(rules=rules)
    cost = 0.0
    error = ""
    for _ in range(2):
        asked = prompt if not error else RETRY_PROMPT.format(prompt=prompt, error=error)
        answer = await reader.ask([], asked, schema)
        cost += answer.cost_usd
        try:
            return ModelProposal.model_validate(answer.output), cost
        except ValidationError as e:
            error = str(e)
    raise ExtractionError(f"the model proposal is not valid after two tries:\n{error}")
