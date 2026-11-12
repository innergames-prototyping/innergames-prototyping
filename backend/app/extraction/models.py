"""Pydantic models for the files of an extraction run.

- `ExtractionConfig` is `work/config.json`: what the agent decides (layouts, kinds, regions,
  overrides). The agent changes it only through the `update_config` tool, which validates it here.
- `ComponentRecord` is `work/components.json`: every item and where it came from.
- `ComponentsFile` is `results/components.json`: the same without the paper trail, identical items
  merged with a count. The steps after extraction read this file.
- `GameModel` is `results/game_model_v1.json`: rules, components, action kinds and game variables.
"""

from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

Id = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_.-]*$")]

Box = Annotated[list[float], Field(min_length=4, max_length=4)]
"""[x0, y0, x1, y1]: fractions of the page when every value is <= 1, else page-render pixels."""


class Strict(BaseModel):
    """Refuses unknown keys, so a typo in the agent's config is an error instead of ignored."""

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- work/config.json


class Game(Strict):
    title: str
    credits: list[str] = []


class Source(Strict):
    file: str
    pages: int | None = None
    content: str
    layout: str | None = None


class Layout(Strict):
    """Where the items of one component page are, and how to cut them out.

    Methods: `segment` finds every separate object, `grid` cuts along lines (`xs`/`ys`, or `box`
    with `rows` and `cols`), `boxes` takes one box per item, `files` takes one image file per item
    from the uploaded files (`fronts` and `backs` are glob patterns with one `*`).
    """

    method: Literal["segment", "grid", "boxes", "files"] = "segment"
    file: str | None = None
    page: int | None = None
    back_page: int | None = None
    back_mirror: Literal["horizontal", "vertical", "none"] = "horizontal"
    # segment
    scale: int = 4
    merge: int = 4
    line_width: int = 8
    min_area: float = 0.0005
    # grid
    xs: list[float] | None = None
    ys: list[float] | None = None
    box: Box | None = None
    rows: int | None = None
    cols: int | None = None
    inset: int = 4
    # boxes
    boxes: list[Box] | None = None
    # files
    fronts: str | None = None
    backs: str | None = None
    # every method
    rotate: int = 0
    rotate_items: dict[str, int] = {}
    skip: list[str] = []

    @model_validator(mode="after")
    def _method_has_its_values(self) -> "Layout":
        if self.method == "files":
            if not self.fronts or self.fronts.count("*") != 1:
                raise ValueError("method files needs `fronts`, a pattern with one `*`")
            return self
        if self.file is None or self.page is None:
            raise ValueError(f"method {self.method} needs `file` and `page`")
        if self.method == "grid":
            has_lines = self.xs is not None and self.ys is not None
            has_box = self.box is not None and self.rows and self.cols
            if not (has_lines or has_box):
                raise ValueError("method grid needs `xs` and `ys`, or `box`, `rows` and `cols`")
        if self.method == "boxes" and not self.boxes:
            raise ValueError("method boxes needs `boxes`")
        return self


class KindField(Strict):
    name: Id
    type: Literal["integer", "string", "enum", "list"]
    enum_values: list[str] | None = None
    description: str

    @model_validator(mode="after")
    def _enum_has_values(self) -> "KindField":
        if self.type == "enum" and not self.enum_values:
            raise ValueError(f"field {self.name}: type enum needs `enum_values`")
        return self


class Kind(Strict):
    id: Id
    name: str
    description: str = ""
    fields: list[KindField] = []
    count_in_rules: int | None = None
    back: str | None = None
    notes: str = ""


class PageRef(Strict):
    file: str
    page: int


class RulesItem(Strict):
    """A group of components the rules name that no file shows."""

    kind: str
    count: int = Field(ge=1)
    source: PageRef
    title: str | None = None
    text: str | None = None
    fields: dict[str, Any] = {}


class Expect(Strict):
    """A count from the rules to check, e.g. 20 gold cards: 8 with value 1 and 12 with value 2."""

    kind: str
    where: dict[str, Any] = {}
    count: int | None = None
    distribution: dict[str, dict[str, int]] = {}


OVERRIDE_KEYS = ("kind", "title", "text", "orientation")


class Override(Strict):
    """A value the agent read from the image itself, for a design (dNNN) or one item key."""

    set: dict[str, Any]
    reason: str

    @field_validator("set")
    @classmethod
    def _known_keys(cls, values: dict[str, Any]) -> dict[str, Any]:
        bad = [k for k in values if k not in OVERRIDE_KEYS and not k.startswith("fields.")]
        if bad:
            raise ValueError(f"unknown override keys {bad}; use {OVERRIDE_KEYS} or fields.<name>")
        return values


class RulesRegion(Strict):
    file: str
    page: int
    box: Box
    rotate: int = 0
    note: str | None = None


class RulesFix(Strict):
    find: str
    replace: str


class RulesExcluded(Strict):
    """Leave out `box` to exclude a whole page, such as a cover."""

    file: str
    page: int
    box: Box | None = None
    reason: str


class ExtractionConfig(Strict):
    game: Game | None = None
    sources: list[Source] = []
    layouts: list[Layout] = []
    kinds: list[Kind] = []
    rules_items: list[RulesItem] = []
    back_kinds: dict[str, list[str]] = {}
    expect: list[Expect] = []
    separate: list[str] = []
    overrides: dict[str, Override] = {}
    rules_regions: list[RulesRegion] = []
    rules_fixes: list[RulesFix] = []
    rules_excluded: list[RulesExcluded] = []
    extraction_notes: list[str] = []

    @model_validator(mode="after")
    def _references_exist(self) -> "ExtractionConfig":
        kinds = {k.id: k for k in self.kinds}
        for item in self.rules_items:
            if item.kind not in kinds:
                raise ValueError(f"rules_items: kind {item.kind!r} is not in kinds")
            declared = {f.name for f in kinds[item.kind].fields}
            if bad := sorted(set(item.fields) - declared):
                raise ValueError(f"rules_items {item.kind}: fields {bad} are not declared")
        return self


# ---------------------------------------------------------------- work/components.json


class ItemSource(Strict):
    file: str
    page: int
    row: int | None = None
    col: int | None = None
    back_page: int | None = None
    back_row: int | None = None
    back_col: int | None = None


class Item(Strict):
    id: str
    kind: str
    source: ItemSource
    title: str | None = None
    fields: dict[str, Any] = {}
    text: str | None = None
    back: str | None = None
    from_rules: bool
    confidence: Literal["high", "medium", "low"]
    notes: str = ""


class KindSummary(Strict):
    id: Id
    name: str
    fields: list[KindField]
    count_found: int = Field(ge=0)
    count_in_rules: int | None = None
    back: str | None = None
    notes: str = ""


class ComponentRecord(Strict):
    spec_version: Literal["extraction-1.0"] = "extraction-1.0"
    game: Game
    sources: list[Source] = Field(min_length=1)
    component_kinds: list[KindSummary] = Field(min_length=1)
    items: list[Item]
    extraction_notes: list[str] = []

    @model_validator(mode="after")
    def _unique_item_ids(self) -> "ComponentRecord":
        ids = [i.id for i in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate item ids")
        return self


# ---------------------------------------------------------------- results/components.json


class ExportedKind(Strict):
    id: Id
    name: str
    fields: list[KindField] | None = None
    back: str | None = None


class Component(Strict):
    """One different piece, with how many the game has."""

    kind: str
    count: int = Field(ge=1)
    title: str | None = None
    fields: dict[str, Any] | None = None
    text: str | None = None
    back: str | None = None


class ComponentsFile(Strict):
    game: Game
    component_kinds: list[ExportedKind] = Field(min_length=1)
    components: list[Component]


# ---------------------------------------------------------------- results/game_model_v1.json


class ActionKind(Strict):
    """Something a player does on a turn, for the time model of the simulation."""

    id: Id
    name: str
    description: str
    rules_quote: str = Field(
        description="The rules sentence this action kind comes from, verbatim."
    )


class GameVariable(Strict):
    """A number or switch the rules set, which the user can change before a simulation."""

    name: Id
    description: str
    type: Literal["integer", "number", "boolean", "string"]
    default: int | float | bool | str | None
    rules_quote: str | None = Field(description="The rules sentence that sets the default.")


class ModelProposal(Strict):
    """What the `propose_model` call returns."""

    action_kinds: list[ActionKind]
    variables: list[GameVariable]


class GameModel(Strict):
    version: int = 1
    source: Literal["extraction", "user"] = "extraction"
    game: Game
    rules: str
    components: ComponentsFile
    action_kinds: list[ActionKind]
    variables: list[GameVariable]
