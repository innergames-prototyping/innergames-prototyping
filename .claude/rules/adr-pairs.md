---
paths:
  - "context/decisions/**"
  - "docs/decisions/**"
---

# ADRs come in pairs

Each ADR has two files with the same name: the agent version in `context/decisions/` and the version for people in `docs/decisions/`. The same holds for `README.md` (the ADR table) and `template.md`.

- When you add, change, rename or delete a file in one folder, do the same to its counterpart in the same pull request.
- `context/decisions/` is the source for the rule. If the two versions differ, update `docs/decisions/` to match.
- Keep the decision, status and date the same in both. The `docs/` version may add context, options and reasons for people.
- Before you finish, compare the file lists: `diff <(ls context/decisions) <(ls docs/decisions)` must print nothing.
