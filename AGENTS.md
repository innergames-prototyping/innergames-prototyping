# innergames-prototyping

## Repository

- GitHub: `innergames-prototyping/innergames-prototyping`, default branch `main`.
- Context for agents lives in `context/`. Documentation for people lives in `docs/` as Markdown files.
- `docs-site/` is a Fumadocs static site that renders every Markdown file in `docs/`. See `docs-site/README.md` for development and deployment.

## Context

- `context/decisions/`: decision records (ADRs). Read the ADR before you change the area it covers.
- Each ADR has a version for people in `docs/decisions/` with the same file name. Change both in the same pull request. The version in `context/` is the source for the rule.
- `context/specs/<story>/`: the spec, plan and tasks for one feature. Read only the spec of the task you work on.
- `docs/` is written for people. You may read it for background. When it differs from `context/`, `context/` wins.

## Commits

- Use [Conventional Commits](https://www.conventionalcommits.org): `<type>(<optional scope>): <description>`.
- Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `build`, `ci`, `perf`, `style`.
- Write the description in the imperative mood, lowercase, without a trailing period, and keep the first line under 72 characters.
- Use `docs` for changes to the content in `docs/`, the scope `context` for changes in `context/` or `AGENTS.md`, and the scope `docs-site` for changes to the site itself, e.g. `feat(docs-site): add search`.
- Mark breaking changes with `!` after the type or scope and explain them in a `BREAKING CHANGE:` footer.
- One logical change per commit.
- Do not add `Co-Authored-By` or other AI attribution lines to commits or pull requests.
