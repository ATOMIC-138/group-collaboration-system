"""Collaboration Event Format Contract implementation (03_event_format_contract.md)."""

import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import PROTOCOL_VERSION
from .config import GroupPaths, read_json, utc_now_compact, utc_now_iso, write_json


class EventValidationError(Exception):
    """Raised when an event violates 03_event_format_contract.md."""


COMMON_REQUIRED_FIELDS = [
    "protocol_version",
    "event_id",
    "event_type",
    "group_id",
    "person_id",
    "created_at",
    "related_events",
]

SUPPORTED_EVENT_TYPES = {
    "change_published",
    "finding",
    "question",
    "answer",
    "review",
    "test_result",
    "integration_result",
    "blocker",
    "final_candidate",
    "final_result",
}

EVENT_TYPE_REQUIRED_FIELDS: Dict[str, List[str]] = {
    "change_published": [
        "change_id",
        "branch",
        "commit",
        "summary",
        "files_changed",
        "interface_changes",
        "tests_run",
        "known_issues",
        "proposed_for_integration",
    ],
    "finding": [
        "summary",
        "evidence",
    ],
    "question": [
        "question_id",
        "text",
        "blocking",
    ],
    "answer": [
        "question_id",
        "text",
    ],
    "review": [
        "change_id",
        "verdict",
        "summary",
        "issues",
        "tests_run",
    ],
    "test_result": [
        "scope",
        "commit",
        "commands",
        "automated_result",
        "passed",
        "failed",
        "skipped",
        "human_checks_required",
        "summary",
    ],
    "integration_result": [
        "change_id",
        "target_branch",
        "result",
        "merge_commit",
        "conflicts",
        "conflict_resolution_summary",
        "verification",
        "summary",
    ],
    "blocker": [
        "summary",
        "blocking_change_id",
        "requested_action",
    ],
    "final_candidate": [
        "canonical_commit",
        "candidate_report_path",
        "tests_considered",
        "known_issues",
    ],
    "final_result": [
        "canonical_commit",
        "final_report_path",
        "test_evidence",
        "known_limitations",
        "initiated_by",
    ],
}

ALLOWED_REVIEW_VERDICTS = {
    "accept",
    "accept_with_changes",
    "reject",
    "needs_more_evidence",
}

ALLOWED_AUTOMATED_RESULTS = {
    "pass",
    "fail",
    "partial",
    "not_available",
}

ALLOWED_INTEGRATION_RESULTS = {
    "success",
    "failed",
    "needs_human",
}


def generate_event_id(person_id: str, timestamp_compact: Optional[str] = None) -> str:
    """Generate E-<UTC timestamp>-<person_id>-<short unique suffix> per 02_repository_contract.md §8."""
    ts = timestamp_compact or utc_now_compact()
    suffix = uuid.uuid4().hex[:4]
    return f"E-{ts}-{person_id}-{suffix}"


def validate_event(event: Dict[str, Any]) -> None:
    """Validate event dictionary against 03_event_format_contract.md."""
    if not isinstance(event, dict):
        raise EventValidationError("Event must be a JSON object.")

    missing_common = [f for f in COMMON_REQUIRED_FIELDS if f not in event]
    if missing_common:
        raise EventValidationError(f"Missing required common fields: {missing_common}")

    if not isinstance(event["related_events"], list):
        raise EventValidationError("'related_events' must be a list of event IDs.")

    event_type = event["event_type"]
    if event_type not in SUPPORTED_EVENT_TYPES:
        raise EventValidationError(
            f"Unsupported event_type '{event_type}'. Allowed: {sorted(SUPPORTED_EVENT_TYPES)}"
        )

    type_required = EVENT_TYPE_REQUIRED_FIELDS.get(event_type, [])
    missing_type = [f for f in type_required if f not in event]
    if missing_type:
        raise EventValidationError(
            f"Event type '{event_type}' missing required fields: {missing_type}"
        )

    if event_type == "review":
        verdict = event["verdict"]
        if verdict not in ALLOWED_REVIEW_VERDICTS:
            raise EventValidationError(
                f"Invalid review verdict '{verdict}'. Allowed: {sorted(ALLOWED_REVIEW_VERDICTS)}"
            )

    elif event_type == "test_result":
        res = event["automated_result"]
        if res not in ALLOWED_AUTOMATED_RESULTS:
            raise EventValidationError(
                f"Invalid automated_result '{res}'. Allowed: {sorted(ALLOWED_AUTOMATED_RESULTS)}"
            )

    elif event_type == "integration_result":
        res = event["result"]
        if res not in ALLOWED_INTEGRATION_RESULTS:
            raise EventValidationError(
                f"Invalid integration result '{res}'. Allowed: {sorted(ALLOWED_INTEGRATION_RESULTS)}"
            )
        ver = event["verification"]
        if not isinstance(ver, dict):
            raise EventValidationError("'verification' in integration_result must be an object.")
        for req_k in ("build", "tests", "semantic_review"):
            if req_k not in ver:
                raise EventValidationError(
                    f"'verification' in integration_result missing required key '{req_k}'."
                )


def build_event(
    event_type: str,
    group_id: str,
    person_id: str,
    payload: Dict[str, Any],
    related_events: Optional[List[str]] = None,
    event_id: Optional[str] = None,
    created_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Construct and validate a complete event object."""
    now_iso = created_at or utc_now_iso()
    ev_id = event_id or generate_event_id(person_id)
    event: Dict[str, Any] = {
        "protocol_version": PROTOCOL_VERSION,
        "event_id": ev_id,
        "event_type": event_type,
        "group_id": group_id,
        "person_id": person_id,
        "created_at": now_iso,
        "related_events": list(related_events or []),
    }
    event.update(payload)
    validate_event(event)
    return event


def write_immutable_event(paths: GroupPaths, event: Dict[str, Any]) -> Path:
    """Write an immutable event file under .group/events/<event_id>.json."""
    validate_event(event)
    paths.ensure_directories()
    event_id = event["event_id"]
    target = paths.events_dir / f"{event_id}.json"
    if target.exists():
        raise EventValidationError(
            f"Event file {target} already exists. Events are immutable per 02_repository_contract.md §8."
        )
    write_json(target, event)
    return target


def load_all_events(paths: GroupPaths) -> List[Dict[str, Any]]:
    """Load all valid events from .group/events/*.json sorted chronologically."""
    if not paths.events_dir.exists():
        return []
    events: List[Dict[str, Any]] = []
    for path in sorted(paths.events_dir.glob("*.json")):
        try:
            data = read_json(path)
            validate_event(data)
            events.append(data)
        except Exception:
            continue
    events.sort(key=lambda e: (e.get("created_at", ""), e.get("event_id", "")))
    return events


def find_change_event(events: List[Dict[str, Any]], change_id: str) -> Optional[Dict[str, Any]]:
    """Locate the latest change_published event matching change_id (or event_id)."""
    matches = [
        e
        for e in events
        if e.get("event_type") == "change_published"
        and (e.get("change_id") == change_id or e.get("event_id") == change_id)
    ]
    return matches[-1] if matches else None


def next_change_id(events: List[Dict[str, Any]], person_id: str) -> str:
    """Generate a concise human-friendly change_id (e.g. C-17, C-17-2) for a person."""
    suffix = person_id.lstrip("Pp") or person_id
    base = f"C-{suffix}"
    existing = {
        e.get("change_id")
        for e in events
        if e.get("event_type") == "change_published" and e.get("change_id")
    }
    if base not in existing:
        return base
    idx = 2
    while f"{base}-{idx}" in existing:
        idx += 1
    return f"{base}-{idx}"
