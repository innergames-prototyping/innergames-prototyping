# Tech Stack

Date: 12 Oct 2026

## Preamble

The purpose of this document is to record which technology the application is built with and why. It is the one place to look up what is used for each part of the system.

## Status

Nothing is chosen yet. The options are being researched in [#106](https://github.com/innergames-prototyping/innergames-prototyping/issues/106) and the choice is made in [#64](https://github.com/innergames-prototyping/innergames-prototyping/issues/64). Until then every choice below reads "To be decided".

## What the stack has to support

These follow from the [Technical Requirements](./TechnicalRequirements.md) and the backlog. A choice that doesn't meet them is out.

- Runs as a web application or Windows application on the user's own machine.
- Calls a third-party LLM through an API, with a locally hosted LLM as a later option.
- Reads PDFs, images and plain text.
- Runs a Python simulation of the game many times, with the same result on the same seed.
- Writes a results file, a dashboard and an exportable report.
- Stays within the cost limit for a run.
- Well documented and cheap to run, so that future students can take it over.

## How a choice is made

Each option is weighed on the same points:

- Fit with the requirements above.
- What the team already knows and how much there is to learn.
- Maturity, documentation and how actively it is maintained.
- Licence and cost.
- How well it can be checked automatically (types, linting, tests).

## Choices per layer

| Layer | What it covers | Options considered | Choice | Decision record |
| --- | --- | --- | --- | --- |
| Frontend | Upload page, review screens, dashboard | To be researched | To be decided | - |
| Backend | Local server between the frontend, the pipeline and the files | To be researched | To be decided | - |
| Simulation runtime | Running the generated simulation code and collecting the results | To be researched | To be decided | - |
| LLM client | Calls to the LLM providers, model routing, usage and cost | To be researched | To be decided | - |
| File processing | Reading PDFs and images, rendering pages | To be researched | To be decided | - |
| Storage | Component files, game models, simulation code, results and runs | To be researched | To be decided | - |
| Schemas and validation | Shared data formats between the pipeline steps | To be researched | To be decided | - |
| Report export | Generating the report from the results file | To be researched | To be decided | - |
| Testing | Test runner and test tools | To be researched | To be decided | - |
| Formatting and linting | Formatter, linter and type checker | To be researched | To be decided | - |
| Static code analysis | Quality gate on pull requests | To be researched | To be decided | - |
| Continuous integration | Running the checks on every pull request | To be researched | To be decided | - |
| Packaging and installation | How a user installs and starts the application | To be researched | To be decided | - |

## Details per choice

One section per layer is added here once it is decided, in this form:

### Layer name

- **Choice:** the tool or framework, with its version.
- **Why:** the reasons, in a few sentences.
- **Alternatives:** what else was considered and why it lost.
- **Consequences:** what this choice fixes for the rest of the stack.
- **Decision record:** link to the ADR.

## Already in the repository

These exist today and are not part of the choice above.

- The documentation site in `docs-site/` is built with Fumadocs on Next.js and renders every Markdown file in `docs/`.
- The development shell in `flake.nix` provides Node.js and Python 3.

## Versions

The pinned versions of the languages, runtimes and main dependencies are listed here once the stack is chosen.

| Component | Version |
| --- | --- |
| To be decided | - |

## Open questions

- Web application, Windows application, or both?
- One language for the whole application, or a separate one for the frontend next to Python?
- Which LLM providers have to be supported from the start?
