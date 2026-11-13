# Collaboration Event Format Contract
Version 0.1

## 1. Purpose

AI agents need more than raw Git history.

They need structured notices explaining what changed, what was tested, what needs review, what failed, what assumptions changed, and what should be integrated.

These notices are called **events**.

Every event is one immutable JSON file under:

```text
.group/events/
```

## 2. Common Envelope

Every event contains:

```json
{
  "protocol_version": "0.1",
  "event_id": "E-20261016T021530Z-P17-a91f",
  "event_type": "change_published",
  "group_id": "G-12",
  "person_id": "P17",
  "created_at": "2026-10-16T02:15:30Z",
  "related_events": []
}
```

Required fields:

```text
protocol_version
event_id
event_type
group_id
person_id
created_at
related_events
```

## 3. Supported Event Types

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

## 4. `change_published`

Example:

```json
{
  "protocol_version": "0.1",
  "event_id": "E-...",
  "event_type": "change_published",
  "group_id": "G-12",
  "person_id": "P17",
  "created_at": "2026-10-16T02:15:30Z",
  "related_events": [],
  "change_id": "C-17",
  "branch": "people/P17/parser",
  "commit": "abc1234",
  "summary": "Implemented nested parser support.",
  "files_changed": [
    "src/parser.py",
    "tests/test_parser.py"
  ],
  "interface_changes": [
    "Parser.parse now returns ParseResult instead of a raw node list."
  ],
  "tests_run": [
    "pytest tests/test_parser.py"
  ],
  "known_issues": [],
  "proposed_for_integration": true
}
```

The actual Git diff is authoritative for code changes.

The event is a structured explanation.

## 5. `finding`

```json
{
  "...common fields...": "...",
  "event_type": "finding",
  "summary": "The failure occurs only when nested blocks have an empty transition list.",
  "evidence": [
    "Reproduced in test_nested_empty_transition."
  ]
}
```

## 6. `question`

```json
{
  "...common fields...": "...",
  "event_type": "question",
  "question_id": "Q-31",
  "text": "Should ParseResult preserve source positions?",
  "blocking": false
}
```

## 7. `answer`

```json
{
  "...common fields...": "...",
  "event_type": "answer",
  "question_id": "Q-31",
  "text": "Yes. Renderer error messages require source positions."
}
```

`related_events` should include the question event ID.

## 8. `review`

```json
{
  "...common fields...": "...",
  "event_type": "review",
  "change_id": "C-17",
  "verdict": "accept_with_changes",
  "summary": "Core approach is sound, but source-position handling is incomplete.",
  "issues": [
    "ParseResult loses end-column information."
  ],
  "tests_run": [
    "pytest tests/test_parser.py"
  ]
}
```

Allowed `verdict` values:

```text
accept
accept_with_changes
reject
needs_more_evidence
```

A review is evidence. It does not itself merge code.

## 9. `test_result`

```json
{
  "...common fields...": "...",
  "event_type": "test_result",
  "scope": "current_branch",
  "commit": "def5678",
  "commands": [
    "pytest",
    "python -m build"
  ],
  "automated_result": "pass",
  "passed": 148,
  "failed": 0,
  "skipped": 2,
  "human_checks_required": [
    "Confirm drag-and-drop interaction feels responsive."
  ],
  "summary": "All automated checks passed."
}
```

Allowed `automated_result`:

```text
pass
fail
partial
not_available
```

## 10. `integration_result`

```json
{
  "...common fields...": "...",
  "event_type": "integration_result",
  "change_id": "C-17",
  "target_branch": "people/P22/renderer",
  "result": "success",
  "merge_commit": "fedcba9",
  "conflicts": [
    "src/model.py"
  ],
  "conflict_resolution_summary": "Preserved P17 ParseResult API and adapted renderer call site.",
  "verification": {
    "build": "pass",
    "tests": "pass",
    "semantic_review": "pass"
  },
  "summary": "Integrated C-17 successfully."
}
```

Allowed `result`:

```text
success
failed
needs_human
```

## 11. `blocker`

```json
{
  "...common fields...": "...",
  "event_type": "blocker",
  "summary": "Cannot safely resolve model.py conflict.",
  "blocking_change_id": "C-17",
  "requested_action": "Human decision on whether source positions are mandatory."
}
```

## 12. `final_candidate`

Created during `FINAL` before the result is declared final.

It should identify:

```text
canonical commit
candidate report path
tests/evidence considered
known issues
```

## 13. `final_result`

Created after finalization.

It should identify:

```text
canonical commit
final report path
test evidence
known limitations
person who initiated finalization
```

## 14. Extension Rule

Implementations may add optional fields.

They must not change the meaning of required fields, reuse an event type with incompatible semantics, or require other implementations to understand undocumented fields.

If a new required concept is needed, define a new protocol version.
