# Architecture and Workflow
Version 0.1

## 1. Components

The system has four conceptual components.

### Human

The student:
- talks to other students;
- decides what to work on;
- steers the local AI;
- invokes collaboration commands;
- may judge whether a result is ready.

### Local AI Agent

Examples include Codex or Gemini.

The agent:
- edits code;
- uses Git;
- reads collaboration records;
- reasons about incoming changes;
- resolves conflicts when possible;
- runs tests;
- performs semantic review;
- creates structured collaboration events.

### `groupctl`

`groupctl` is the deterministic collaboration helper.

It should provide reliable operations for:
- identity/configuration;
- synchronization;
- publishing changes;
- reading/writing collaboration events;
- checking repository state;
- integration bookkeeping;
- test-result publication;
- finalization bookkeeping.

The AI supplies judgment. `groupctl` supplies repeatable mechanics.

### GitHub Repository

GitHub is the shared persistent substrate.

It stores source code, branches and commits, tests, the assignment, collaboration event files, and final group records.

## 2. Canonical State vs. Personal Work

The canonical group state is the configured shared branch, normally:

```text
main
```

Individual people work on separate branches:

```text
people/<person_id>/<topic>
```

Examples:

```text
people/P17/parser-fix
people/P22/renderer
people/P31/ui-tests
```

A personal branch may contain unfinished or experimental work.

`main` represents the group's currently accepted integrated state.

## 3. Parallel Work

Parallel work is expected.

```text
P17 + Agent A -> parser feature
P22 + Agent B -> renderer feature
P31 + Agent C -> tests
```

The humans may coordinate this division verbally.

The repository records what actually happens.

When one person finishes useful work, that work is published so the other agents can discover and reason about it.

## 4. Publish Before Integrate

A completed local contribution should be published as:

1. one or more Git commits;
2. a pushed branch;
3. a structured `change_published` event.

The event tells other agents who produced it, what branch/commit contains it, what it claims to change, what tests were run, what assumptions or interfaces changed, and whether it is proposed for integration.

Other agents must inspect the actual diff. The change description is context, not proof.

## 5. Integration Is More Than a Git Merge

A successful Git merge proves only that Git found no unresolved textual conflict.

After integration, distinguish:

```text
Level 1: Git integration
         Were the commits incorporated?

Level 2: Mechanical validation
         Does the project build?
         Do automated tests pass?
         Are conflict markers absent?
         Do configured static checks pass?

Level 3: Semantic review
         Do the combined changes make sense together?
         Did an incoming change invalidate assumptions?
         Are there behavioral incompatibilities that Git cannot detect?
```

The AI agent is especially important at Level 3.

## 6. Conflict Handling

If Git reports a conflict:

1. do not hide or overwrite it;
2. identify the conflicting files;
3. inspect the intent of both sides;
4. resolve the conflict deliberately;
5. build and test;
6. review semantic compatibility;
7. publish an integration event describing what was done.

If the agent cannot safely resolve the conflict, it must stop and tell the human rather than inventing a resolution.

## 7. Shared Awareness

Agents should not attempt to share their entire private conversation history.

Instead publish meaningful engineering events such as:

```text
change_published
finding
question
answer
review
test_result
integration_result
blocker
final_candidate
final_result
```

## 8. Human Shorthand Commands

The human-facing command vocabulary is:

```text
SYNC
PUB
INT <change_id>
REV <change_id>
TEST [scope]
STATUS
FINAL
```

These are defined in `04_command_reference.md` and `05_command_procedures.md`.

The commands are prompt-engineering shorthand.

They may be typed directly to the local AI agent.

## 9. No Mandatory Central Integrator

Version 0.1 does not require one permanent integration person.

Any group member may be asked to integrate a published change, review another member's change, run tests, or prepare finalization.

The humans may decide informally who does what.

The shared repository records the outcome.

## 10. Restartability

Important group state must be recoverable from Git/GitHub.

A local agent should not need a previous private chat session to understand the current canonical code, published changes, reviews, test results, and finalization state.

Local caches may improve convenience but must not be the only copy of important collaboration information.
