# Development Workflow

This is the route every task takes, from issue to merged pull request. It is the same for every team member. Code written with an AI coding agent takes the same route.

## The route

1. Issue
2. Spec
3. Spec review
4. Branch
5. Build, task by task
6. Run the checks
7. Pull request
8. Review
9. Merge

## 1. Issue

Every change starts from a GitHub issue. Assign yourself before you start, so the team knows who works on it. Work on one story at a time (see the [Collaboration Agreement](CollaborationAgreement.md)).

If the issue is unclear, ask in the issue before you write a spec.

## 2. Spec

Write the spec in `context/specs/<story>/spec.md`. Copy [`context/specs/template.md`](../context/specs/template.md) to start. Use a short name for the folder, e.g. `context/specs/pdf-upload/`.

The spec has four parts:

- **Spec**: what the feature does for the user and how you check it. No technology.
- **Plan**: the modules and files you change, the constraints and the ADRs in `context/decisions/` that apply.
- **Tasks**: small steps in build order. Each task has its own test or check.
- **Done**: the checks that close the story.

Size the spec to the change. A small fix gets a few lines. Only a large feature needs every part.

You can write the spec with the agent. You are responsible for what it says.

## 3. Spec review

Ask one other team member to read the spec before you build. They check that the behaviour is right, that the tasks are small enough and that each task has a check.

Set `Status: ready` when you both agree. For a small fix, a short message in the issue is enough.

## 4. Branch

Create a branch from `main`:

```
<type>/<short-name>
```

`<type>` is the commit type of the main change, e.g. `feat/pdf-upload`, `fix/empty-results-file`, `docs/development-workflow`. Use lowercase and hyphens.

Commit messages follow Conventional Commits. The types, scopes and rules are in [`AGENTS.md`](../AGENTS.md). Commit after each task, one logical change per commit.

## 5. Build, task by task

Work through the Tasks in the spec, in order:

1. Give the agent the spec and the task.
2. Build the task.
3. Run the check of that task.
4. When it passes, tick the task in the spec and commit.
5. Go to the next task.

Do not start the next task while a check fails. If a task turns out too big, split it in the spec first.

If the plan changes while you build, update the spec in the same branch. The spec in the pull request must match the code.

## 6. Run the checks

Before you open a pull request:

- Every task in the spec is ticked and its check passes.
- The formatter, linter, type checker and full test suite pass. The command comes after #111.
- Every item under Done in the spec is met.

## 7. Pull request

Open a pull request into `main`. Use `staging` only to test work together, as the Collaboration Agreement says.

- Title: a Conventional Commit line, e.g. `feat: add pdf upload`.
- Body: what changed and why, the link to the spec, and anything the reviewer should look at.
- Link the issue with `Closes #NNN`, or `Part of #NNN` if the issue stays open.

The checks run on every pull request after #112.

## 8. Review

- At least one other team member reviews every pull request.
- Nobody merges their own pull request without an approved review.
- Ask the person who knows the area best. For a change to an ADR, ask the people the decision affects.

A review looks at:

- **Spec**: the code does what the spec says, and nothing more.
- **Design**: the code follows the ADRs and stays inside its module.
- **Readability**: someone else on the team can follow and change it.
- **Tests**: new behaviour and fixed bugs have a test.
- **Decisions**: a new decision has its own ADR, in both `context/decisions/` and `docs/decisions/`.
- **Size**: the diff contains only this change.

Style is for the formatter and linter (after #111), not for the reviewer.

The author answers every comment, with a change or a reason.

## 9. Merge

Merge when the review is approved and every check passes. Set `Status: done` in the spec. Delete the branch.

## Ask the team first

Stop and ask the team before you build when the task needs:

- **An architecture decision.** Write a new ADR with status `proposed` and agree on it before you build. See [`docs/decisions/`](decisions/README.md).
- **A change to an accepted ADR.** Propose the change. Do not work around the ADR.
- **A new dependency.** Say which package, why, and what else you looked at.
- **A schema change.** A data format is shared by more than one part of the pipeline.
- **A change to a module boundary.**
- **An unclear requirement.** Ask in the issue, or ask the client through Luc.

## Code written with an AI agent

Code written with an AI agent takes the same route as any other code. There is no shorter route.

- The agent reads [`AGENTS.md`](../AGENTS.md), the ADRs and the spec of the task.
- The person who opens the pull request has read every line of the code and is responsible for it. "The agent wrote it" is not an answer in a review.
- Check what the agent reports. Run the checks yourself.
- When the agent wants a new dependency or a new decision, the rules above apply.
