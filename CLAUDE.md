# innergames-prototyping

## Repository

- GitHub: `innergames-prototyping/innergames-prototyping`, default branch `main`.
- Documentation lives in `docs/` as Markdown files.
- `docs-site/` is a Fumadocs static site that renders every Markdown file in `docs/`. See `docs-site/README.md` for development and deployment.

## Documentation

Fumadocs builds the site from the files in `docs/`, so the folder layout and the `meta.json` files decide what the site looks like.

- Every `.md` file becomes a page. The path is the URL: `docs/team/RetrospectiveBoard.md` is served at `/docs/team/RetrospectiveBoard/`.
- The first heading in a file is the page title. Do not add frontmatter for it, and start every file with a heading.
- `docs/index.md` is the start page at `/docs/`; the site root redirects to it. It links to every page, so update it when you add, move, rename or remove one.
- Each folder is a collapsible group in the sidebar. A folder needs a `meta.json` with `title`, `defaultOpen` and `pages`.
- `pages` sets the sidebar order and lists file names without `.md`. The `"..."` entry stands for every page that is not listed, so a new file shows up at the bottom of its group. Add it to `pages` when it belongs somewhere else in the order.
- `docs/meta.json` lists the start page and the folders, without `"..."`. Add a new folder or top-level page to it, otherwise it is left out of the sidebar.
- Link between pages with relative file paths that include `.md`, e.g. `[Meeting Notes](./team/INNERGAMES-Meeting-Notes.md)`.
- Moving or renaming a file changes its URL and breaks links people have shared. Do it only when asked, and fix the links in `docs/` and the entries in `meta.json` in the same change.
- After changing the structure, run `npm run build` in `docs-site/` and check that it succeeds.
- The site is a static export: a change is live only after the site is rebuilt and deployed.

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
