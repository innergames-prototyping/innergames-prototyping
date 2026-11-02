# Code Guidelines

Date: 2 Nov 2026

## Introduction

This document records the rules for code in this repository. The goal is that code from different team members reads the same, and that a review is about the design and not about style.

The backend and the simulation are Python. The frontend is TypeScript. Rules that are the same for both languages are written once.

## Status

Proposed. The team has not agreed to it yet (#107).

The formatter, the linter and the type checker are not chosen yet (#111). The tools named below are suggestions.

## How to read the rules

Each rule has a check:

- **tool (after #111)**: a tool will check it once #111 is done. Until then, the reviewer checks it.
- **review**: the reviewer checks it in the pull request.

Rules that an ADR already sets are not repeated here. Read the ADR for the area you change (`docs/decisions/`).

## Formatting

| Rule | Check |
| --- | --- |
| The formatter decides the layout and the line length. Do not format by hand against it. Suggestion: Ruff format for Python, Prettier for TypeScript. | tool (after #111) |
| A pull request changes only what its task needs. No reformatting, renames or refactors of other code. | review |

## Naming

| Rule | Check |
| --- | --- |
| Python: `snake_case` for functions, variables and modules. `PascalCase` for classes. `UPPER_SNAKE_CASE` for constants. Suggestion: Ruff `N` rules. | tool (after #111) |
| TypeScript: `camelCase` for functions and variables. `PascalCase` for types and components. `UPPER_SNAKE_CASE` for module constants. Suggestion: `@typescript-eslint/naming-convention`. | tool (after #111) |
| A React component file has the name of its component: `ResultsChart.tsx`. | review |
| Booleans start with `is`, `has`, `can` or `should`. | review |
| Names say what the value is in the domain. Use the words of the game model: `playthrough`, `component`, `seed`, not `data`, `item` or `obj`. | review |
| No abbreviations, except `id`, `url`, `api`, `llm`, `pdf`, `json` and loop indexes `i` and `j`. | review |

Wrong:

```python
def calc(d, n):
    ...
```

Right:

```python
def calculate_win_rate(results: SimulationResults, run_count: int) -> float:
    ...
```

## File and function size

| Rule | Check |
| --- | --- |
| A function has at most 40 lines. Suggestion: Ruff `PLR0915`, ESLint `max-lines-per-function`. | tool (after #111) |
| A function has at most 4 parameters. Pass more values as one Pydantic model or one object. Suggestion: Ruff `PLR0913`, ESLint `max-params`. | tool (after #111) |
| Nesting is at most 3 levels deep. Use an early return instead of a nested `if`. Suggestion: ESLint `max-depth`. | tool (after #111) |
| A file has at most 300 lines. Suggestion: ESLint `max-lines`. Python has no Ruff rule for this. | tool (after #111) for TypeScript, review for Python |
| A file has one responsibility. A React component file exports one component. | review |

Wrong:

```python
def load_game(path: Path) -> GameModel:
    if path.exists():
        if path.suffix == ".json":
            return GameModel.model_validate_json(path.read_text())
        else:
            raise UnsupportedFileError(path)
    else:
        raise FileNotFoundError(path)
```

Right:

```python
def load_game(path: Path) -> GameModel:
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix != ".json":
        raise UnsupportedFileError(path)

    return GameModel.model_validate_json(path.read_text())
```

## Error handling

| Rule | Check |
| --- | --- |
| Python: no bare `except:` and no `except Exception:` that does not raise again. Suggestion: Ruff `E722`, `BLE001`. | tool (after #111) |
| Python: raise a specific exception class, not `Exception`. Suggestion: Ruff `TRY002`. | tool (after #111) |
| TypeScript: no empty `catch` block. Suggestion: ESLint `no-empty`. | tool (after #111) |
| TypeScript: every promise is awaited or handled. Suggestion: `@typescript-eslint/no-floating-promises`. | tool (after #111) |
| An error is never hidden. A `catch` or `except` block raises again, or returns the error to the caller in a way the caller must handle. Logging alone is not handling. | review |
| Missing or invalid data is an error, not a default value. Unknown is not `0`, `""` or `[]`. | review |
| An API endpoint returns an error with a status code and a message the user can read. It does not send a stack trace to the frontend. | review |
| The frontend checks the status of every API response and shows the error to the user. | review |

Wrong:

```python
try:
    turns = int(answer.turn_count)
except ValueError:
    turns = 0
```

Right:

```python
try:
    turns = int(answer.turn_count)
except ValueError as error:
    raise InvalidLlmAnswerError("turn_count is not a number") from error
```

## Typing

| Rule | Check |
| --- | --- |
| Python: every function has types for its parameters and its return value. Suggestion: Ruff `ANN`. | tool (after #111) |
| Python: the type checker runs in strict mode. Suggestion: mypy `--strict` or Pyright `strict`. | tool (after #111) |
| TypeScript: `strict` is on (ADR 0003). | tool (after #111) |
| No `Any` in Python and no `any` in TypeScript. Use `unknown` and narrow it. Suggestion: Ruff `ANN401`, `@typescript-eslint/no-explicit-any`. | tool (after #111) |
| TypeScript: no non-null assertion (`value!`). Suggestion: `@typescript-eslint/no-non-null-assertion`. | tool (after #111) |
| A `# type: ignore` or `@ts-expect-error` has a reason on the same line. `@ts-ignore` is not used. Suggestion: Ruff `PGH003`, `@typescript-eslint/ban-ts-comment`. | tool (after #111) |
| TypeScript: no `as` cast to make a type error go away. | review |
| Python: data that crosses a boundary (API, LLM, file, simulation process) is a Pydantic model, not a `dict`. | review |

Wrong:

```python
def save_results(results: dict) -> None:
    ...
```

Right:

```python
def save_results(results: SimulationResults) -> None:
    ...
```

## Dependencies

| Rule | Check |
| --- | --- |
| Each new dependency has a reason in the pull request: what it does, and why the standard library or a current dependency is not enough. | review |
| A new dependency has a license that permits use in closed software, such as MIT, BSD or Apache-2.0. GPL and AGPL need team agreement first. | review |
| A new dependency had a release in the last 12 months. | review |
| Development tools are dev dependencies, not runtime dependencies. | review |
| The lock file is committed and matches the dependency list. | tool (after #111) |

## Comments

| Rule | Check |
| --- | --- |
| Comments and names are in English. | review |
| A comment says why, not what. Do not repeat the next line in words. | review |
| No commented-out code. Git keeps the old version. Suggestion: Ruff `ERA001`. | tool (after #111) for Python, review for TypeScript |
| A `TODO` has an issue number: `TODO(#123): ...`. Suggestion: Ruff `TD003`. | tool (after #111) for Python, review for TypeScript |
| A function that another module uses has a docstring (Python) or TSDoc comment (TypeScript). It says what the function returns and which errors it raises. | review |

Wrong:

```python
# increase the seed by one
seed += 1
```

Right:

```python
# Each run needs its own seed, else all runs play the same game.
seed += 1
```

## Tests

The kinds of test and how to run them are defined in #113.

| Rule | Check |
| --- | --- |
| Each new behaviour and each bug fix has a test that fails without the change. | review |
| A test name says the behaviour: `test_rejects_pdf_without_pages`, not `test_upload_2`. | review |
| A test does not call a real LLM or the network (ADR 0012). | review |
| A simulation test sets a fixed seed and checks the exact result (ADR 0007). | review |
| A test is not removed, skipped or made weaker to make a change pass. | review |
| All tests pass before a merge. | tool (after #111) |

## Open questions

- The limits (40 lines per function, 4 parameters, 3 levels of nesting, 300 lines per file) are a proposal. The team must agree to the numbers.
- The tools and their exact rules are chosen in #111.
- Where tests live in the repository waits for the repository layout (#103).
