# Local AI Agent Collaboration Behavior
Version 0.1

## 1. Purpose

This specification describes expected behavior from each student's local AI coding agent.

The implementation should provide a portable skill/instruction file derived from this specification.

## 2. Two Contexts

The agent works in two contexts.

### Local/private

Includes:
- human conversation;
- unfinished reasoning;
- experimental edits;
- local notes.

This is not automatically broadcast.

### Group/public

Includes:
- accepted source code;
- published feature branches;
- structured events;
- tests;
- reviews;
- finalization records.

Only information useful to the group should be published.

## 3. Do Not Use Chat Copy/Paste as the Protocol

The human should not have to copy another agent's prose into this agent.

The agent should discover group information through Git, GitHub, `.group/events/`, and standardized commands.

The human may say:

> Susan finished her part. SYNC.

But SYNC must inspect the actual repository state.

## 4. Verify Claims

Never treat a teammate's prose summary as proof.

For a published change:
- inspect the referenced commit;
- inspect the actual diff;
- run relevant tests when needed.

For a claimed successful merge:
- verify history;
- build/test;
- perform semantic review.

## 5. Be Conservative With Destructive Operations

Do not casually force-push shared branches, discard another person's work, reset canonical state, overwrite tests merely to make the product pass, or resolve a conflict by arbitrarily choosing one side.

When uncertainty is significant, ask the human.

## 6. Publish Useful Engineering Information

Publish an event when the group would benefit from knowing:
- a coherent change is ready;
- an important finding was discovered;
- a blocking question exists;
- a review was performed;
- a test run produced useful evidence;
- integration succeeded or failed;
- finalization has begun or completed.

Do not publish every minor thought.

## 7. Interface Changes Matter

If a change modifies function signatures, file formats, shared data structures, APIs, or assumptions other code may rely on, explicitly record that in the change event.

## 8. Human Control

The human may interrupt at any time with:

```text
SYNC
PUB
INT <change_id>
REV <change_id>
TEST [scope]
STATUS
FINAL
```

Prioritize carrying out the requested collaboration procedure.

If the command would endanger unfinished local work, protect the work first and explain what was done.

## 9. Background Awareness

An implementation may periodically check for new remote events.

Version 0.1 does not require the AI to run continuously in the background.

The human can explicitly request `SYNC`.

## 10. Vendor Neutrality

Do not rely on one AI vendor's private conversation format.

Portable collaboration behavior should be expressible as a skill, custom instructions, repository instruction file, or equivalent configuration.

Deterministic operations should live in `groupctl` or normal development tools.

## 11. Tool vs. Intelligence Boundary

Use tools for mechanical facts:

```text
Which commit am I on?
Did Git merge?
What tests passed?
Which events are new?
Is commit X incorporated?
```

Use AI reasoning for judgment:

```text
Does this interface change invalidate my work?
What is the correct conflict resolution?
Do the merged behaviors make sense together?
Are the tests sufficient?
What human check is needed?
```

Do not ask the AI to remember facts that can be verified mechanically.
