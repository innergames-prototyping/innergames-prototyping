# innergames-prototyping

## Repository

- GitHub: `innergames-prototyping/innergames-prototyping`, default branch `main`.
- Documentation lives in `docs/` as Markdown files.
- `docs-site/` is a Fumadocs static site that renders every Markdown file in `docs/`. See `docs-site/README.md` for development and deployment.

## Project management

- GitHub Issues are the project management system for this repository. Always check them before starting work: `gh issue list` and `gh issue view <number>`.
- If the user names the issue or story, use that one. If they do not, work out yourself which one the task belongs to: match the task description against open issues (`gh issue list --search "<keywords>"`), and use the branch name and issues assigned to the user as extra hints.
- State which issue you matched before you start. Ask only when several issues fit equally well. If no issue covers the task, say so instead of working untracked.
- Keep the status of the issues you are working on up to date: assign the issue and mark it in progress when you start, comment on progress or blockers, and close it (or reference it with `Closes #<number>` in the pull request) when the work is done.

## Commits

- Use [Conventional Commits](https://www.conventionalcommits.org): `<type>(<optional scope>): <description>`.
- Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `build`, `ci`, `perf`, `style`.
- Write the description in the imperative mood, lowercase, without a trailing period, and keep the first line under 72 characters.
- Use `docs` for changes to the content in `docs/`, and the scope `docs-site` for changes to the site itself, e.g. `feat(docs-site): add search`.
- Mark breaking changes with `!` after the type or scope and explain them in a `BREAKING CHANGE:` footer.
- One logical change per commit.
- Do not add `Co-Authored-By` or other AI attribution lines to commits or pull requests.
