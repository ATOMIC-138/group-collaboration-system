"""Configuration and repository layout helpers for .group/ contract (02_repository_contract.md)."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import PROTOCOL_VERSION


class GroupConfigError(Exception):
    """Raised when .group/ configuration is missing or invalid."""


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format (e.g. 2026-10-16T02:15:30Z)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_now_compact() -> str:
    """Return current UTC timestamp in compact format for event IDs (e.g. 20261016T021530Z)."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def find_repo_root(start_path: Optional[Path] = None) -> Path:
    """Locate the repository root containing .group/ or .git/."""
    current = (start_path or Path.cwd()).resolve()
    for candidate in [current] + list(current.parents):
        if (candidate / ".group").is_dir() or (candidate / ".git").exists():
            return candidate
    return current


class GroupPaths:
    """Standard paths owned by the collaboration system under .group/."""

    def __init__(self, repo_root: Path):
        self.root = repo_root.resolve()
        self.group_dir = self.root / ".group"
        self.group_json = self.group_dir / "group.json"
        self.assignment_dir = self.group_dir / "assignment"
        self.default_assignment_md = self.assignment_dir / "assignment.md"
        self.members_dir = self.group_dir / "members"
        self.events_dir = self.group_dir / "events"
        self.final_dir = self.group_dir / "final"
        self.candidate_md = self.final_dir / "candidate.md"
        self.final_report_md = self.final_dir / "final_report.md"
        self.final_json = self.final_dir / "final.json"
        self.local_dir = self.group_dir / "local"
        self.local_gitkeep = self.local_dir / ".gitkeep"
        self.local_identity_json = self.local_dir / "identity.json"
        self.local_sync_state_json = self.local_dir / "sync_state.json"
        self.local_logs_dir = self.local_dir / "logs"

    def ensure_directories(self) -> None:
        for directory in [
            self.group_dir,
            self.assignment_dir,
            self.members_dir,
            self.events_dir,
            self.final_dir,
            self.local_dir,
            self.local_logs_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)
        if not self.local_gitkeep.exists():
            self.local_gitkeep.write_text("", encoding="utf-8")


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    path.write_text(content, encoding="utf-8")


def load_group_config(paths: GroupPaths) -> Dict[str, Any]:
    """Load and validate .group/group.json according to 02_repository_contract.md §3."""
    if not paths.group_json.exists():
        raise GroupConfigError(
            f"Missing {paths.group_json}. Run 'groupctl init' to initialize the repository."
        )
    data = read_json(paths.group_json)
    required = ["protocol_version", "group_id", "canonical_branch", "assignment_file"]
    missing = [k for k in required if k not in data]
    if missing:
        raise GroupConfigError(f"Invalid group.json; missing required fields: {missing}")
    return data


def load_local_identity(paths: GroupPaths) -> Optional[Dict[str, Any]]:
    """Load local person identity from .group/local/identity.json or environment."""
    env_person = os.environ.get("GROUPCTL_PERSON_ID")
    if paths.local_identity_json.exists():
        data = read_json(paths.local_identity_json)
        if env_person:
            data["person_id"] = env_person
        return data
    if env_person:
        member_file = paths.members_dir / f"{env_person}.json"
        if member_file.exists():
            return read_json(member_file)
        return {"person_id": env_person, "display_name": env_person}
    return None


def require_person_id(paths: GroupPaths, explicit_person_id: Optional[str] = None) -> str:
    if explicit_person_id:
        return explicit_person_id
    identity = load_local_identity(paths)
    if identity and identity.get("person_id"):
        return str(identity["person_id"])
    raise GroupConfigError(
        "Local person_id is not configured. Use 'groupctl member set-local <person_id>' "
        "or pass '--person-id <ID>'."
    )


def load_members(paths: GroupPaths) -> Dict[str, Dict[str, Any]]:
    """Return mapping of person_id -> member descriptor from .group/members/*.json."""
    members: Dict[str, Dict[str, Any]] = {}
    if not paths.members_dir.exists():
        return members
    for file_path in sorted(paths.members_dir.glob("*.json")):
        try:
            data = read_json(file_path)
            pid = data.get("person_id") or file_path.stem
            members[pid] = data
        except Exception:
            continue
    return members


def load_sync_state(paths: GroupPaths) -> Dict[str, Any]:
    """Load .group/local/sync_state.json tracking seen events and last synced commits."""
    if paths.local_sync_state_json.exists():
        try:
            return read_json(paths.local_sync_state_json)
        except Exception:
            pass
    return {
        "last_sync_at": None,
        "last_canonical_commit": None,
        "seen_event_ids": [],
    }


def save_sync_state(
    paths: GroupPaths,
    canonical_commit: Optional[str],
    seen_event_ids: List[str],
) -> Dict[str, Any]:
    state = {
        "last_sync_at": utc_now_iso(),
        "last_canonical_commit": canonical_commit,
        "seen_event_ids": sorted(set(seen_event_ids)),
    }
    write_json(paths.local_sync_state_json, state)
    return state
