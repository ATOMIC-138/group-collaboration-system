# Testing, Validation, and Group Finalization
Version 0.1

## 1. Testing Philosophy

A Git merge is not evidence that the combined program is correct.

Validation should use the strongest available evidence.

Possible layers:

```text
1. repository integrity
2. build/compile
3. unit tests
4. integration tests
5. static checks
6. scripted UI tests
7. semantic AI review
8. human interaction/visual judgment
```

Not every project has every layer.

## 2. Tests Are Shared Project Assets

Tests should normally be committed to GitHub.

Examples:

```text
tests/
test-data/
expected-results/
ui-tests/
```

A group member may improve or add tests.

Changes to tests should be reviewed like changes to production code.

Do not change expected results merely because the implementation disagrees with them.

## 3. Expected Outputs

When deterministic expected outputs exist, store them as versioned project artifacts.

Examples:

```text
JSON output
compiler output
serialized model
generated text
numeric results
```

When exact expected output is inappropriate, tests may instead check invariants.

## 4. GUI and Interactive Testing

Not all behavior is naturally represented as input/output files.

Where practical, automate GUI behavior through scripted UI tests, DOM/widget inspection, accessibility interfaces, screenshots or visual-difference tools, or recorded interaction sequences.

Where automation cannot determine quality, request a human check.

A good human check is concrete:

```text
1. Open model X.
2. Expand node Y.
3. Select Z.
4. Collapse Y.
5. Expand Y again.
6. Tell the agent whether you lost track of Z.
```

A bad human check is vague:

```text
Does it look good?
```

## 5. AI-Generated Tests

Agents may propose new tests.

Before relying on them, ask:
- Does this test actually represent the intended requirement?
- Is the expected result independently justified?
- Is the test merely encoding the current implementation?

Tests created solely from the implementation can reproduce the same mistake as the implementation.

## 6. Test Result Publication

Each meaningful test run should identify:

```text
commit tested
commands run
pass/fail counts
environment problems
human checks still required
summary
```

Publish this as a `test_result` event when useful.

## 7. Canonical Group Result

The final result must refer to a specific canonical commit.

The group does not submit one student's unpushed working directory, a vague statement that "everyone's code works", or several incompatible feature branches.

The group result is anchored to:

```text
canonical_branch + exact commit
```

## 8. Final Report

`.group/final/final_report.md` should contain at least:

```text
# Group Final Report

## Assignment
Short identification of the assignment.

## Result
What the group produced.

## Canonical Commit
Exact commit hash.

## Important Changes
Summary of major implemented work.

## Validation
Build/tests/reviews/human checks performed.

## Known Limitations
Anything known not to be complete or reliable.

## Contributors
People who materially contributed.
```

## 9. `final.json`

Example:

```json
{
  "protocol_version": "0.1",
  "group_id": "G-12",
  "canonical_branch": "main",
  "canonical_commit": "0123456789abcdef",
  "report_file": ".group/final/final_report.md",
  "initiated_by": "P17",
  "created_at": "2026-10-16T04:00:00Z",
  "status": "completed",
  "known_limitations": []
}
```

Allowed `status`:

```text
completed
completed_with_known_limitations
```

Finalization should normally not be used when the group has no usable result.

If work is blocked or failed, leave that fact in events and do not falsely generate a successful final result.

## 10. Who May Finalize

Any recognized group member may initiate `FINAL`.

No unanimous click is required.

However, FINAL must inspect group state, identify pending important work, run final validation, and show the human the proposed final report before publishing it.

This avoids making finalization depend on every member being present while still preventing accidental submission of stale personal work.

## 11. Finalization Is Not Proof of Perfection

`status = completed` means:

> The group is submitting this canonical result as its completed work.

It does not mean every possible bug is absent or every reviewer agreed.

Known limitations should be reported honestly.
