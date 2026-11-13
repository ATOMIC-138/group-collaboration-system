# Shared Repository Contract
Version 0.1

## 1. Purpose

This document defines repository locations and naming rules used by the collaboration system.

The project source tree itself is application-specific.

The collaboration system owns:

```text
.group/
```

## 2. Required Layout

```text
repository/
├── .group/
│   ├── group.json
│   ├── assignment/
│   │   └── assignment.md
│   ├── members/
│   │   └── <person_id>.json
│   ├── events/
│   │   └── <event_id>.json
│   ├── final/
│   │   ├── candidate.md
│   │   ├── final_report.md
│   │   └── final.json
│   └── local/
│       └── .gitkeep
│
├── src/                    # example only
├── tests/                  # project test files if applicable
└── ...
```

`.group/local/` is for local-only implementation support and should normally be ignored by Git except for `.gitkeep`.

## 3. `group.json`

Example:

```json
{
  "protocol_version": "0.1",
  "group_id": "G-12",
  "canonical_branch": "main",
  "assignment_file": ".group/assignment/assignment.md"
}
```

Required fields:

```text
protocol_version
group_id
canonical_branch
assignment_file
```

## 4. Members

Each person has one committed membership descriptor:

```text
.group/members/<person_id>.json
```

Example:

```json
{
  "protocol_version": "0.1",
  "person_id": "P17",
  "display_name": "Susan",
  "joined_at": "2026-10-16T10:30:00+08:00"
}
```

Version 0.1 does not define secure membership authorization. The group is assumed to have been formed outside this software.

The file exists so agents know the identities used in collaboration records.

## 5. Assignment

The group assignment is stored at the path declared by `group.json`.

Default:

```text
.group/assignment/assignment.md
```

Its internal format is outside this contract.

## 6. Personal Work Branches

Use:

```text
people/<person_id>/<topic>
```

Examples:

```text
people/P17/parser
people/P22/layout
people/P31/tests
```

Do not use the same branch for two independently working people.

## 7. Canonical Branch

The configured canonical branch is normally:

```text
main
```

It represents accepted group work.

Agents must not assume that every remote feature branch has been accepted merely because it exists.

## 8. Events

Durable collaboration messages are immutable event files:

```text
.group/events/<event_id>.json
```

Do not maintain one shared `conversation.txt`.

Recommended event ID:

```text
E-<UTC timestamp>-<person_id>-<short unique suffix>
```

Example:

```text
E-20261016T021530Z-P17-a91f.json
```

Once committed and pushed, an event file must not be edited.

If information changes, create a new event referring to the earlier event.

## 9. Event Publication

An event becomes public to the group only after:

```text
file written
git add
git commit
git push
```

Local uncommitted event files are not considered published.

## 10. Finalization Files

The final group result is stored under:

```text
.group/final/
```

`candidate.md` is a temporary proposed final summary.

`final_report.md` is the substantive final group report.

`final.json` is the machine-readable finalization envelope.

## 11. Tests

Normal project tests should live in ordinary test locations such as:

```text
tests/
ui-tests/
test-data/
expected-results/
```

The collaboration contract does not force one testing framework.

Test results are communicated through `test_result` events.

## 12. Concurrent Modification Rule

Prefer designs that avoid multiple writers to the same collaboration file.

Because events are immutable and uniquely named, normal event publication should not require file locking.

Source-code conflicts are handled by Git.

If the collaboration implementation needs mutable local state, keep it under `.group/local/` and do not make it authoritative group state.
