# Human-to-Agent Collaboration Command Reference
Version 0.1

These commands are concise prompt-engineering controls.

A student may type one of these commands to the local AI agent.

The agent must interpret them according to `05_command_procedures.md`.

## `SYNC`

**Meaning:** Bring my working context up to date with the group.

The agent should fetch current remote state, inspect new collaboration events, identify changes since the previous synchronization, update from the canonical branch when safe, and explain which new group changes affect the current work.

`SYNC` does not blindly merge every feature branch.

## `PUB`

**Meaning:** Publish the useful work I have completed so the group can see and use it.

The agent should review current local changes, run appropriate checks, commit and push the work branch, create a `change_published` event, and summarize interfaces, assumptions, tests, and known issues.

`PUB` does not automatically mean "merge into main."

## `INT <change_id>`

**Meaning:** Integrate a specific teammate's published change into my current working version and verify the result.

Example:

```text
INT C-17
```

The agent should inspect the event and actual diff, integrate it, resolve conflicts when safe, verify mechanically, perform semantic compatibility review, and publish an `integration_result`.

## `REV <change_id>`

**Meaning:** Review a teammate's published change without automatically accepting it.

Example:

```text
REV C-22
```

The agent should inspect the event, actual diff, surrounding code, tests, assumptions, regressions, and missing evidence, then publish a `review`.

## `TEST [scope]`

**Meaning:** Test the current software and publish evidence of what is known to work.

Examples:

```text
TEST
TEST current
TEST main
TEST C-17
```

The agent should run applicable build/tests/static checks/UI tests, investigate failures, identify human-required checks, and publish a `test_result`.

## `STATUS`

**Meaning:** Tell me where my work stands relative to the group.

The agent should report current branch/commit, uncommitted work, relationship to canonical state, new relevant events, current test state, blockers, and a recommended next action.

## `FINAL`

**Meaning:** Begin group finalization.

Any recognized group member may initiate it.

The agent must not simply submit the initiator's private branch.

It should synchronize, identify the canonical accepted state, verify pending work and evidence, run final tests, identify unresolved issues, produce a proposed final report, show it to the human, and only then publish finalization records.
