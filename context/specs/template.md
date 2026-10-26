# Story title

Story: #NNN

Status: draft | ready | done

Size this spec to the change. A small fix needs a few lines per section. Only a large feature needs every part. Delete what does not apply.

## Spec

What the feature does for the user. No technology here.

- Behaviour: what the user does and what the system does in return.
- Out of scope: what this story does not do.

Success criteria:

- [ ] A result that someone can check, one per line.

## Plan

How we build it.

- Stack and architecture: the modules and files this change touches.
- Constraints: limits that the code must respect.
- Decisions: the ADRs in `context/decisions/` that apply, e.g. [0002](../../decisions/0002-backend-python-fastapi.md).
- Open questions: mark them `[nog invullen]`.

## Tasks

Small steps in build order. Each task has its own test or check. Do one task, run its check, then go to the next.

1. [ ] Task: what to build, in one sentence.
   Check: the test or command that proves it works.
2. [ ] Task: the next step. It builds on task 1.
   Check: the test or command for this step.
3. [ ] Task: add more tasks as needed. Split a task when its check needs more than one test.
   Check: the test or command for this step.

## Done

The story is done when:

- [ ] Every task and its check passes.
- [ ] Every success criterion in Spec is met.
- [ ] The full test suite passes.
- [ ] A new decision has its own ADR in `context/decisions/` and `docs/decisions/`.
- [ ] Status at the top is `done`.
