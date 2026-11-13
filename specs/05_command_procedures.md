# Collaboration Command Procedures
Version 0.1

This file defines the required procedure behind each human-facing command.

## 1. SYNC

When the human says:

```text
SYNC
```

1. Record current branch, commit, and uncommitted state.
2. Fetch remote branches and tags.
3. Read newly published `.group/events/*.json`.
4. Determine which events are new since the last known sync.
5. Fetch the current canonical branch.
6. Compare current work against canonical state.
7. If safe, merge or rebase canonical state according to project policy without discarding local work.
8. Do not automatically integrate unrelated feature branches.
9. Inspect new change, integration, review, test, and blocker events relevant to current work.
10. Tell the human what changed, what was incorporated, what remains separate, and what may affect current assumptions.
11. If synchronization changed code, run at least quick validation.
12. If new group work invalidates current assumptions, say so explicitly.

A clean `git pull` is not by itself a complete SYNC.

## 2. PUB

When the human says:

```text
PUB
```

1. Inspect local changes.
2. Refuse to publish accidental secrets, generated junk, or obviously broken repository state.
3. Determine the coherent contribution being published.
4. Run appropriate quick tests/build checks.
5. Create meaningful commit(s).
6. Push the personal work branch.
7. Create a unique `change_id`.
8. Create a `change_published` event containing branch, commit, summary, files changed, interface/assumption changes, tests run, known issues, and whether integration is proposed.
9. Commit and push the event.
10. Report the change ID to the human.

If the work is not ready, explain why rather than pretending PUB succeeded.

## 3. INT

When the human says:

```text
INT <change_id>
```

1. Perform SYNC-level metadata discovery.
2. Locate the `change_published` event.
3. Confirm referenced branch and commit exist.
4. Read the summary.
5. Inspect the actual Git diff.
6. Identify interface/assumption changes.
7. Integrate into the current target branch using the configured Git strategy.
8. If conflicts occur:
   - identify each conflict;
   - inspect both sides;
   - reason about both intents;
   - resolve only when intended combined behavior is clear;
   - otherwise stop and raise/publish a blocker.
9. Confirm the referenced commit is actually incorporated.
10. Check for leftover conflict markers.
11. Build if applicable.
12. Run relevant automated tests.
13. Perform semantic review: did either side invalidate assumptions in the other?
14. Create and publish an `integration_result`.
15. Tell the human exactly what happened.

## 4. REV

When the human says:

```text
REV <change_id>
```

1. Locate the published change.
2. Read its declared purpose and known issues.
3. Inspect its real Git diff.
4. Inspect relevant surrounding code.
5. Check interface and assumption changes.
6. Run relevant tests when practical.
7. Look for incorrect behavior, regressions, missing cases, brittle assumptions, unnecessary complexity, and incompatibility with accepted group work.
8. Separate definite defects, plausible risks, and subjective preferences.
9. Produce one verdict:
   - `accept`
   - `accept_with_changes`
   - `reject`
   - `needs_more_evidence`
10. Publish a `review` event.
11. Do not merge merely because the review is positive.

## 5. TEST

When the human says:

```text
TEST [scope]
```

1. Resolve scope:
   - current branch by default;
   - canonical branch if `main`;
   - named change if a change ID is supplied.
2. Record exact commit tested.
3. Discover available validation mechanisms: build, unit tests, integration tests, static analysis, lint, scripted UI tests, test data, expected outputs.
4. Run applicable automated checks.
5. Investigate failures enough to distinguish product-code failure, outdated/broken test, missing environment, or inconclusive result.
6. Do not silently rewrite expected outputs merely to make tests pass.
7. Identify checks that cannot be automated.
8. For human-required checks, provide a concrete procedure.
9. Publish a `test_result`.
10. Summarize what is proven, what failed, and what remains unknown.

## 6. STATUS

When the human says:

```text
STATUS
```

1. Inspect current local Git state.
2. Fetch enough remote metadata to know whether the local picture is stale.
3. Report identity, group, branch, current commit, uncommitted changes, canonical commit, ahead/behind relationship, unprocessed relevant events, published local changes, last known tests, and blockers.
4. Recommend a concise next action.
5. Do not perform a large merge or code rewrite merely because STATUS was requested.

## 7. FINAL

When the human says:

```text
FINAL
```

1. Synchronize group metadata and canonical state.
2. Identify the canonical commit proposed as the group result.
3. List published changes not incorporated into canonical state.
4. Determine whether those are intentionally rejected/obsolete, still important, or unknown.
5. Review latest reviews, blockers, and test results.
6. Run final automated validation.
7. Identify human-required checks.
8. If important unresolved work or failures remain, do not silently finalize.
9. Generate `.group/final/candidate.md` describing what the group completed, canonical commit, validation, known limitations, and unresolved concerns.
10. Show the candidate to the initiating human.
11. After human confirmation, create `.group/final/final_report.md`, `.group/final/final.json`, and a `final_result` event.
12. Commit and push finalization records.
13. Report final canonical commit and report path.

FINAL is group finalization, not personal-branch submission.
