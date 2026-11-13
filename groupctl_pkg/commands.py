"""Implementation of groupctl subcommands and collaboration procedures (04 & 05 specs)."""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import PROTOCOL_VERSION
from .config import (
    GroupConfigError,
    GroupPaths,
    load_group_config,
    load_local_identity,
    load_members,
    load_sync_state,
    require_person_id,
    save_sync_state,
    utc_now_iso,
    write_json,
)
from .events import (
     build_event,
    find_change_event,
    load_all_events,
    next_change_id,
    write_immutable_event,
)
from .git_ops import (
    GitError,
    fetch_all,
    get_ahead_behind,
    get_commit_diff_and_files,
    get_current_branch,
    get_head_commit,
    get_uncommitted_files,
    get_unmerged_conflicts,
    has_remote,
    is_ancestor,
    is_git_repo,
    materialize_shared_group_files,
    resolve_ref_commit,
    run_git,
    scan_conflict_markers,
    scan_hygiene_issues,
)


def _commit_and_push_paths(
    paths: GroupPaths,
    rel_paths: List[str],
    commit_message: str,
    push: bool = True,
) -> Optional[str]:
    """Stage specific paths, commit if staged changes exist, and push current branch if remote exists."""
    repo_root = paths.root
    for rel in rel_paths:
        run_git(repo_root, ["add", "--", rel], check=True)

    diff_cached = run_git(repo_root, ["diff", "--cached", "--name-only"], check=False)
    if not diff_cached.stdout.strip():
        return get_head_commit(repo_root, short=True)

    run_git(repo_root, ["commit", "-m", commit_message], check=True)
    commit_sha = get_head_commit(repo_root, short=True)
    if push and has_remote(repo_root):
        branch = get_current_branch(repo_root)
        if branch and branch != "HEAD":
            run_git(repo_root, ["push", "-u", "origin", branch], check=False)
    return commit_sha


def run_project_tests(
    repo_root: Path,
    custom_command: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Discover and execute automated project tests (pytest or unittest), returning
    structured counts and output logs.
    """
    py_exe = sys.executable or "python"
    commands_run: List[str] = []

    if custom_command:
        cmd_list = custom_command
        shell_mode = True
        commands_run.append(custom_command)
    else:
        # Check if pytest is available in current Python environment
        chk = subprocess.run(
            [py_exe, "-m", "pytest", "--version"],
            cwd=str(repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if chk.returncode == 0:
            cmd_list = [py_exe, "-m", "pytest", "-v"]
            commands_run.append("python -m pytest -v")
        else:
            cmd_list = [py_exe, "-m", "unittest", "discover", "-s", "tests", "-v"]
            commands_run.append("python -m unittest discover -s tests -v")
        shell_mode = False

    if not (repo_root / "tests").exists() and not custom_command:
        return {
            "commands": [],
            "automated_result": "not_available",
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "output": "No tests/ directory found.",
            "returncode": 0,
        }

    proc = subprocess.run(
        cmd_list,
        cwd=str(repo_root),
        shell=shell_mode,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = proc.stdout or ""
    passed = 0
    failed = 0
    skipped = 0

    # Parse pytest summary if present
    m_pass = re.search(r"(\d+)\s+passed", out)
    m_fail = re.search(r"(\d+)\s+(?:failed|error)", out)
    m_skip = re.search(r"(\d+)\s+skipped", out)
    if m_pass or m_fail or m_skip:
        passed = int(m_pass.group(1)) if m_pass else 0
        failed = int(m_fail.group(1)) if m_fail else 0
        skipped = int(m_skip.group(1)) if m_skip else 0
    else:
        # Parse unittest output: "Ran X tests in ..."
        m_ran = re.search(r"Ran\s+(\d+)\s+test", out)
        if m_ran:
            total = int(m_ran.group(1))
            m_f = re.search(r"failures=(\d+)", out)
            m_e = re.search(r"errors=(\d+)", out)
            m_s = re.search(r"skipped=(\d+)", out)
            f_cnt = (int(m_f.group(1)) if m_f else 0) + (int(m_e.group(1)) if m_e else 0)
            s_cnt = int(m_s.group(1)) if m_s else 0
            failed = f_cnt
            skipped = s_cnt
            passed = max(0, total - failed - skipped)

    if proc.returncode == 0:
        automated_result = "pass"
    else:
        automated_result = "fail"
        if failed == 0:
            failed = 1

    return {
        "commands": commands_run,
        "automated_result": automated_result,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "output": out,
        "returncode": proc.returncode,
    }


def cmd_init(
    paths: GroupPaths,
    group_id: str,
    canonical_branch: str = "main",
    assignment_title: str = "Group Programming Assignment",
    assignment_body: Optional[str] = None,
) -> Dict[str, Any]:
    """Initialize .group/ directory structure and required files per 02_repository_contract.md."""
    paths.ensure_directories()
    group_cfg = {
        "protocol_version": PROTOCOL_VERSION,
        "group_id": group_id,
        "canonical_branch": canonical_branch,
        "assignment_file": ".group/assignment/assignment.md",
    }
    write_json(paths.group_json, group_cfg)

    if not paths.default_assignment_md.exists() or assignment_body:
        text = assignment_body or (
            f"# {assignment_title}\n\n"
            "Collaborate as a group of humans and AI agents using `groupctl` and the "
            "seven standard commands (`SYNC`, `PUB`, `INT`, `REV`, `TEST`, `STATUS`, `FINAL`).\n"
        )
        paths.default_assignment_md.write_text(text, encoding="utf-8")

    gitignore_path = paths.root / ".gitignore"
    required_ignores = [
        ".group/local/*",
        "!.group/local/.gitkeep",
        "__pycache__/",
        "*.py[cod]",
        ".pytest_cache/",
        ".env",
    ]
    existing_lines: List[str] = []
    if gitignore_path.exists():
        existing_lines = gitignore_path.read_text(encoding="utf-8").splitlines()
    updated = list(existing_lines)
    for rule in required_ignores:
        if rule not in updated:
            updated.append(rule)
    gitignore_path.write_text("\n".join(updated).strip() + "\n", encoding="utf-8")

    return {
        "status": "initialized",
        "group_config": group_cfg,
        "repo_root": str(paths.root),
    }


def cmd_member_register(
    paths: GroupPaths,
    person_id: str,
    display_name: str,
    set_local: bool = True,
    commit: bool = False,
) -> Dict[str, Any]:
    """Create .group/members/<person_id>.json per 02_repository_contract.md §4."""
    paths.ensure_directories()
    descriptor = {
        "protocol_version": PROTOCOL_VERSION,
        "person_id": person_id,
        "display_name": display_name,
        "joined_at": utc_now_iso(),
    }
    member_path = paths.members_dir / f"{person_id}.json"
    write_json(member_path, descriptor)
    if set_local:
        write_json(paths.local_identity_json, descriptor)
    if commit and is_git_repo(paths.root):
        _commit_and_push_paths(
            paths,
            [f".group/members/{person_id}.json"],
            f"chore(group): register member {person_id} ({display_name})",
        )
    return {
        "status": "registered",
        "member": descriptor,
        "local_identity_set": set_local,
    }


def cmd_member_set_local(paths: GroupPaths, person_id: str, display_name: Optional[str] = None) -> Dict[str, Any]:
    paths.ensure_directories()
    member_file = paths.members_dir / f"{person_id}.json"
    if member_file.exists():
        descriptor = json.loads(member_file.read_text(encoding="utf-8"))
    else:
        descriptor = {
            "protocol_version": PROTOCOL_VERSION,
            "person_id": person_id,
            "display_name": display_name or person_id,
            "joined_at": utc_now_iso(),
        }
    write_json(paths.local_identity_json, descriptor)
    return {"status": "local_identity_updated", "identity": descriptor}


def cmd_branch_start(
    paths: GroupPaths,
    topic: str,
    person_id: Optional[str] = None,
    base_branch: Optional[str] = None,
) -> Dict[str, Any]:
    """Create or switch to personal work branch people/<person_id>/<topic> (02 §6)."""
    pid = require_person_id(paths, person_id)
    clean_topic = topic.strip().strip("/").replace(" ", "-")
    branch_name = f"people/{pid}/{clean_topic}"

    existing = resolve_ref_commit(paths.root, branch_name)
    if existing:
        run_git(paths.root, ["checkout", branch_name], check=True)
    else:
        if base_branch:
            run_git(paths.root, ["checkout", "-b", branch_name, base_branch], check=True)
        else:
            run_git(paths.root, ["checkout", "-b", branch_name], check=True)

    return {
        "status": "switched",
        "person_id": pid,
        "branch": branch_name,
        "commit": get_head_commit(paths.root, short=True),
    }


def cmd_status(paths: GroupPaths, person_id: Optional[str] = None) -> Dict[str, Any]:
    """Execute STATUS procedure (05_command_procedures.md §6)."""
    group_cfg = load_group_config(paths)
    identity = load_local_identity(paths)
    pid = person_id or (identity.get("person_id") if identity else "UNSET")
    canonical_branch = group_cfg["canonical_branch"]

    fetched = fetch_all(paths.root)
    materialized = materialize_shared_group_files(paths)

    current_branch = get_current_branch(paths.root)
    current_commit = get_head_commit(paths.root, short=True)
    canonical_commit = resolve_ref_commit(paths.root, canonical_branch, short=True)
    ahead, behind = get_ahead_behind(paths.root, "HEAD", canonical_branch)
    uncommitted = get_uncommitted_files(paths.root)
    # Ignore materialized .group/events or .group/members when reporting user code dirtiness
    code_uncommitted = [
        u for u in uncommitted if not u["path"].replace("\\", "/").startswith(".group/")
    ]

    all_events = load_all_events(paths)
    sync_state = load_sync_state(paths)
    seen_ids = set(sync_state.get("seen_event_ids", []))
    new_events = [e for e in all_events if e["event_id"] not in seen_ids]

    published_changes = [e for e in all_events if e["event_type"] == "change_published"]
    my_published = [e for e in published_changes if e["person_id"] == pid]

    unincorporated_changes: List[Dict[str, Any]] = []
    for chg in published_changes:
        c_sha = chg.get("commit", "")
        in_head = is_ancestor(paths.root, c_sha, "HEAD")
        in_main = is_ancestor(paths.root, c_sha, canonical_branch)
        if not in_head:
            unincorporated_changes.append(
                {
                    "change_id": chg["change_id"],
                    "person_id": chg["person_id"],
                    "branch": chg["branch"],
                    "commit": c_sha,
                    "summary": chg["summary"],
                    "interface_changes": chg.get("interface_changes", []),
                    "in_canonical": in_main,
                }
            )

    test_events = [e for e in all_events if e["event_type"] == "test_result"]
    last_test = test_events[-1] if test_events else None

    blockers = [e for e in all_events if e["event_type"] == "blocker"]
    reviews = [e for e in all_events if e["event_type"] == "review"]

    # Determine concise next action recommendation (05 §6.4)
    if pid == "UNSET":
        recommendation = "Configure local identity with 'groupctl member set-local <PERSON_ID>'."
    elif get_unmerged_conflicts(paths.root):
        recommendation = "Resolve active Git merge conflicts, run tests, and finish integration."
    elif new_events or behind > 0:
        recommendation = (
            f"Run 'SYNC' ({len(new_events)} new event(s), {behind} commit(s) behind {canonical_branch})."
        )
    elif code_uncommitted:
        recommendation = (
            f"Complete and test your {len(code_uncommitted)} uncommitted file(s), then run 'PUB'."
        )
    elif unincorporated_changes:
        ids = ", ".join(c["change_id"] for c in unincorporated_changes[:3])
        recommendation = f"Review or integrate teammate change(s): REV/INT {ids}."
    else:
        recommendation = "Working tree is clean and up to date. Continue feature work or run 'FINAL' if group work is complete."

    return {
        "command": "STATUS",
        "group_id": group_cfg["group_id"],
        "person_id": pid,
        "display_name": identity.get("display_name") if identity else None,
        "current_branch": current_branch,
        "current_commit": current_commit,
        "canonical_branch": canonical_branch,
        "canonical_commit": canonical_commit,
        "ahead_of_canonical": ahead,
        "behind_canonical": behind,
        "remote_fetched": fetched,
        "uncommitted_files": code_uncommitted,
        "new_events_since_sync": [
            {
                "event_id": e["event_id"],
                "event_type": e["event_type"],
                "person_id": e["person_id"],
                "summary": e.get("summary") or e.get("text") or e.get("change_id", ""),
            }
            for e in new_events
        ],
        "my_published_changes": [c["change_id"] for c in my_published],
        "unincorporated_published_changes": unincorporated_changes,
        "latest_test_result": (
            {
                "event_id": last_test["event_id"],
                "scope": last_test["scope"],
                "commit": last_test["commit"],
                "automated_result": last_test["automated_result"],
                "passed": last_test["passed"],
                "failed": last_test["failed"],
                "summary": last_test["summary"],
            }
            if last_test
            else None
        ),
        "reviews_count": len(reviews),
        "active_blockers": [
            {
                "event_id": b["event_id"],
                "person_id": b["person_id"],
                "blocking_change_id": b["blocking_change_id"],
                "summary": b["summary"],
                "requested_action": b["requested_action"],
            }
            for b in blockers
        ],
        "materialized_from_remotes": materialized,
        "recommended_next_action": recommendation,
    }


def cmd_sync(
    paths: GroupPaths,
    merge_canonical: bool = True,
    run_validation: bool = True,
) -> Dict[str, Any]:
    """Execute SYNC procedure (05_command_procedures.md §1)."""
    group_cfg = load_group_config(paths)
    canonical_branch = group_cfg["canonical_branch"]

    # Step 1: Record current branch, commit, and uncommitted state
    pre_branch = get_current_branch(paths.root)
    pre_commit = get_head_commit(paths.root, short=True)
    pre_uncommitted = [
        u for u in get_uncommitted_files(paths.root)
        if not u["path"].replace("\\", "/").startswith(".group/")
    ]

    # Step 2 & 3: Fetch remote branches and tags, read newly published .group/events/*.json
    fetched = fetch_all(paths.root)
    materialized = materialize_shared_group_files(paths)

    # Step 4: Determine which events are new since last known sync
    sync_state = load_sync_state(paths)
    seen_ids = set(sync_state.get("seen_event_ids", []))
    all_events = load_all_events(paths)
    new_events = [e for e in all_events if e["event_id"] not in seen_ids]

    # Step 5 & 6: Fetch current canonical branch & compare against canonical state
    canonical_ref = (
        f"origin/{canonical_branch}"
        if resolve_ref_commit(paths.root, f"origin/{canonical_branch}")
        else canonical_branch
    )
    canonical_commit = resolve_ref_commit(paths.root, canonical_ref, short=True)
    ahead, behind = get_ahead_behind(paths.root, "HEAD", canonical_ref)

    # Step 7: If safe, merge canonical state without discarding local work
    canonical_incorporation = "already_up_to_date"
    code_changed_by_sync = False
    if behind > 0 and merge_canonical:
        if pre_uncommitted:
            canonical_incorporation = (
                "deferred_dirty_worktree (uncommitted local edits protected; commit or stash before merging canonical)"
            )
        else:
            merge_proc = run_git(
                paths.root,
                ["merge", "--no-edit", canonical_ref],
                check=False,
            )
            if merge_proc.returncode == 0:
                canonical_incorporation = f"merged_{canonical_ref}_cleanly"
                code_changed_by_sync = get_head_commit(paths.root, short=True) != pre_commit
            else:
                # Abort unsafe automatic canonical merge so local work is never corrupted silently
                run_git(paths.root, ["merge", "--abort"], check=False)
                canonical_incorporation = (
                    f"conflict_with_{canonical_ref} (auto-merge aborted to protect branch; manual resolution required)"
                )

    # Step 8 & 9: Do NOT automatically integrate unrelated feature branches; inspect relevant events
    separate_changes: List[Dict[str, Any]] = []
    assumption_warnings: List[str] = []

    for ev in all_events:
        if ev["event_type"] == "change_published":
            c_sha = ev.get("commit", "")
            incorporated = is_ancestor(paths.root, c_sha, "HEAD")
            entry = {
                "change_id": ev["change_id"],
                "person_id": ev["person_id"],
                "branch": ev["branch"],
                "commit": c_sha,
                "summary": ev["summary"],
                "interface_changes": ev.get("interface_changes", []),
                "known_issues": ev.get("known_issues", []),
                "incorporated_in_current_branch": incorporated,
                "is_new_since_last_sync": ev["event_id"] in {n["event_id"] for n in new_events},
            }
            if not incorporated:
                separate_changes.append(entry)
            if ev.get("interface_changes"):
                for ic in ev["interface_changes"]:
                    assumption_warnings.append(
                        f"[{ev['change_id']} by {ev['person_id']}] Interface/Assumption change: {ic}"
                    )

    # Step 11: If synchronization changed code, run at least quick validation
    validation_summary: Optional[Dict[str, Any]] = None
    if code_changed_by_sync and run_validation:
        test_res = run_project_tests(paths.root)
        validation_summary = {
            "automated_result": test_res["automated_result"],
            "passed": test_res["passed"],
            "failed": test_res["failed"],
            "commands": test_res["commands"],
        }

    # Save updated sync state
    save_sync_state(
        paths,
        canonical_commit=canonical_commit,
        seen_event_ids=[e["event_id"] for e in all_events],
    )

    return {
        "command": "SYNC",
        "pre_sync": {
            "branch": pre_branch,
            "commit": pre_commit,
            "uncommitted_count": len(pre_uncommitted),
        },
        "post_sync": {
            "branch": get_current_branch(paths.root),
            "commit": get_head_commit(paths.root, short=True),
            "canonical_branch": canonical_branch,
            "canonical_commit": canonical_commit,
            "canonical_incorporation": canonical_incorporation,
        },
        "remote_fetched": fetched,
        "materialized_files": materialized,
        "new_events": new_events,
        "separate_unintegrated_changes": separate_changes,
        "assumption_and_interface_warnings": assumption_warnings,
        "validation_after_sync": validation_summary,
    }


def cmd_pub(
    paths: GroupPaths,
    summary: str,
    interface_changes: Optional[List[str]] = None,
    known_issues: Optional[List[str]] = None,
    proposed_for_integration: bool = True,
    change_id: Optional[str] = None,
    person_id: Optional[str] = None,
    skip_tests: bool = False,
    allow_main: bool = False,
) -> Dict[str, Any]:
    """Execute PUB procedure (05_command_procedures.md §2)."""
    group_cfg = load_group_config(paths)
    pid = require_person_id(paths, person_id)
    branch = get_current_branch(paths.root)
    canonical_branch = group_cfg["canonical_branch"]

    if branch == canonical_branch and not allow_main:
        raise GroupConfigError(
            f"Cannot run PUB directly on canonical branch '{canonical_branch}'. "
            f"Develop and publish on a personal branch 'people/{pid}/<topic>' (02 §6, 04 §PUB)."
        )

    # Step 1 & 2: Inspect local changes and refuse secrets/junk/conflict markers
    uncommitted = get_uncommitted_files(paths.root)
    candidate_paths = [
        u["path"] for u in uncommitted if not u["path"].replace("\\", "/").startswith(".group/")
    ]
    hygiene_errors = scan_hygiene_issues(paths.root, candidate_paths)
    conflict_files = scan_conflict_markers(paths.root)
    for cf in conflict_files:
        msg = f"Leftover conflict markers in tracked file: {cf}"
        if msg not in hygiene_errors:
            hygiene_errors.append(msg)

    if hygiene_errors:
        raise GroupConfigError(
            "PUB refused due to repository hygiene/safety issues (05 §2.2):\n- "
            + "\n- ".join(hygiene_errors)
        )

    # Step 4: Run appropriate quick tests/build checks
    tests_run_list: List[str] = []
    if not skip_tests:
        test_res = run_project_tests(paths.root)
        tests_run_list = test_res["commands"]
        if test_res["automated_result"] == "fail":
            raise GroupConfigError(
                f"PUB aborted: automated tests failed ({test_res['failed']} failed). "
                "Fix failing tests before publishing or document known issues with --skip-tests."
            )

    # Step 5: Create meaningful commit(s) if there are uncommitted non-.group changes
    if candidate_paths:
        for p in candidate_paths:
            run_git(paths.root, ["add", "--", p], check=True)
        run_git(paths.root, ["commit", "-m", f"feat({pid}): {summary}"], check=True)

    commit_sha = get_head_commit(paths.root, short=True)
    if not commit_sha:
        raise GroupConfigError("No commit found on current branch to publish.")

    diff_info = get_commit_diff_and_files(paths.root, "HEAD", base_ref=canonical_branch)
    files_changed = diff_info["files_changed"] or candidate_paths

    # Step 6, 7, 8: Create change_id and change_published event
    materialize_shared_group_files(paths)
    all_events = load_all_events(paths)
    cid = change_id or next_change_id(all_events, pid)

    event_payload = {
        "change_id": cid,
        "branch": branch,
        "commit": commit_sha,
        "summary": summary,
        "files_changed": files_changed,
        "interface_changes": list(interface_changes or []),
        "tests_run": tests_run_list,
        "known_issues": list(known_issues or []),
        "proposed_for_integration": bool(proposed_for_integration),
    }
    event = build_event(
        event_type="change_published",
        group_id=group_cfg["group_id"],
        person_id=pid,
        payload=event_payload,
    )
    event_file = write_immutable_event(paths, event)

    # Step 9: Commit and push branch + event
    rel_event_path = str(event_file.relative_to(paths.root)).replace("\\", "/")
    # Also stage any newly registered member files if uncommitted
    to_stage = [rel_event_path]
    member_rel = f".group/members/{pid}.json"
    if (paths.root / member_rel).exists():
        to_stage.append(member_rel)

    _commit_and_push_paths(
        paths,
        to_stage,
        f"chore(event): publish {cid} ({event['event_id']})",
        push=True,
    )

    return {
        "command": "PUB",
        "change_id": cid,
        "event_id": event["event_id"],
        "event_file": rel_event_path,
        "branch": branch,
        "commit": commit_sha,
        "files_changed": files_changed,
        "interface_changes": event_payload["interface_changes"],
        "tests_run": tests_run_list,
        "known_issues": event_payload["known_issues"],
        "proposed_for_integration": proposed_for_integration,
        "summary": summary,
    }


def cmd_inspect(paths: GroupPaths, change_id: str) -> Dict[str, Any]:
    """Inspect a published change, its actual Git diff, and related events (for REV and INT)."""
    fetch_all(paths.root)
    materialize_shared_group_files(paths)
    all_events = load_all_events(paths)
    chg_event = find_change_event(all_events, change_id)
    if not chg_event:
        raise GroupConfigError(f"Could not locate published change '{change_id}' in .group/events/.")

    commit_ref = chg_event["commit"]
    branch_ref = chg_event["branch"]
    resolved_commit = resolve_ref_commit(paths.root, commit_ref) or resolve_ref_commit(
        paths.root, branch_ref
    )
    if not resolved_commit:
        raise GroupConfigError(
            f"Referenced commit '{commit_ref}' / branch '{branch_ref}' for {change_id} does not exist in Git."
        )

    group_cfg = load_group_config(paths)
    diff_info = get_commit_diff_and_files(
        paths.root,
        resolved_commit,
        base_ref=group_cfg["canonical_branch"],
    )

    related_reviews = [
        e for e in all_events if e["event_type"] == "review" and e.get("change_id") == chg_event["change_id"]
    ]
    related_integrations = [
        e for e in all_events if e["event_type"] == "integration_result" and e.get("change_id") == chg_event["change_id"]
    ]

    return {
        "change_id": chg_event["change_id"],
        "change_event": chg_event,
        "resolved_commit": resolved_commit,
        "already_incorporated_in_head": is_ancestor(paths.root, resolved_commit, "HEAD"),
        "actual_files_changed": diff_info["files_changed"],
        "actual_diff": diff_info["diff"],
        "reviews": related_reviews,
        "integration_results": related_integrations,
    }


def cmd_rev(
    paths: GroupPaths,
    change_id: str,
    verdict: str,
    summary: str,
    issues: Optional[List[str]] = None,
    tests_run: Optional[List[str]] = None,
    run_tests_now: bool = False,
    person_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute REV procedure (05_command_procedures.md §4) without merging the change."""
    group_cfg = load_group_config(paths)
    pid = require_person_id(paths, person_id)
    inspected = cmd_inspect(paths, change_id)
    chg_event = inspected["change_event"]

    executed_tests = list(tests_run or [])
    if run_tests_now:
        t_res = run_project_tests(paths.root)
        executed_tests.extend(t_res["commands"])

    review_event = build_event(
        event_type="review",
        group_id=group_cfg["group_id"],
        person_id=pid,
        related_events=[chg_event["event_id"]],
        payload={
            "change_id": chg_event["change_id"],
            "verdict": verdict,
            "summary": summary,
            "issues": list(issues or []),
            "tests_run": executed_tests,
        },
    )
    event_file = write_immutable_event(paths, review_event)
    rel_event_path = str(event_file.relative_to(paths.root)).replace("\\", "/")
    _commit_and_push_paths(
        paths,
        [rel_event_path],
        f"chore(event): review {chg_event['change_id']} ({verdict})",
        push=True,
    )

    return {
        "command": "REV",
        "change_id": chg_event["change_id"],
        "event_id": review_event["event_id"],
        "verdict": verdict,
        "summary": summary,
        "issues": review_event["issues"],
        "tests_run": executed_tests,
        "inspected_files": inspected["actual_files_changed"],
    }


def cmd_int_prepare(paths: GroupPaths, change_id: str) -> Dict[str, Any]:
    """
    Steps 1-8 of INT (05_command_procedures.md §3):
    Fetch metadata, locate change_published event, verify commit exists, inspect diff
    and interface changes, and initiate Git merge into the current branch.
    """
    inspected = cmd_inspect(paths, change_id)
    chg_event = inspected["change_event"]
    target_branch = get_current_branch(paths.root)
    target_commit = inspected["resolved_commit"]

    if inspected["already_incorporated_in_head"]:
        return {
            "status": "already_integrated",
            "change_id": chg_event["change_id"],
            "target_branch": target_branch,
            "commit": target_commit[:7],
            "interface_changes": chg_event.get("interface_changes", []),
            "conflicts": [],
            "actual_diff": inspected["actual_diff"],
        }

    # Stage any newly materialized immutable event files before merging so git merge won't complain
    uncommitted_events = [
        u["path"]
        for u in get_uncommitted_files(paths.root)
        if u["path"].replace("\\", "/").startswith(".group/events/")
        or u["path"].replace("\\", "/").startswith(".group/members/")
    ]
    if uncommitted_events:
        _commit_and_push_paths(
            paths,
            uncommitted_events,
            "chore(group): sync group events before integration",
            push=False,
        )

    merge_proc = run_git(
        paths.root,
        ["merge", "--no-commit", "--no-ff", target_commit],
        check=False,
    )
    conflicts = get_unmerged_conflicts(paths.root)
    if conflicts:
        return {
            "status": "conflicts_detected",
            "change_id": chg_event["change_id"],
            "target_branch": target_branch,
            "incoming_commit": target_commit[:7],
            "conflicts": conflicts,
            "interface_changes": chg_event.get("interface_changes", []),
            "summary": chg_event["summary"],
            "actual_diff": inspected["actual_diff"],
            "instructions": (
                "Inspect both sides of each conflicting file, resolve the conflict deliberately "
                "preserving intended combined behavior, then run 'groupctl int finish "
                f"{chg_event['change_id']}' or 'groupctl int abort {chg_event['change_id']}' if human decision is required."
            ),
        }

    # Commit the clean merge if --no-commit staged changes
    merge_head_exists = (paths.root / ".git" / "MERGE_HEAD").exists()
    if merge_head_exists:
        run_git(
            paths.root,
            ["commit", "-m", f"Merge change {chg_event['change_id']} ({target_commit[:7]}) into {target_branch}"],
            check=True,
        )

    return {
        "status": "merged_pending_verification",
        "change_id": chg_event["change_id"],
        "target_branch": target_branch,
        "merge_commit": get_head_commit(paths.root, short=True),
        "conflicts": [],
        "interface_changes": chg_event.get("interface_changes", []),
        "summary": chg_event["summary"],
        "actual_diff": inspected["actual_diff"],
    }


def cmd_int_finish(
    paths: GroupPaths,
    change_id: str,
    summary: str,
    conflicts_resolved: Optional[List[str]] = None,
    conflict_resolution_summary: str = "",
    semantic_review: str = "pass",
    person_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Steps 9-15 of INT (05_command_procedures.md §3):
    Verify commit ancestry, confirm no leftover conflict markers, run mechanical build/tests,
    record semantic review result, and publish integration_result.
    """
    group_cfg = load_group_config(paths)
    pid = require_person_id(paths, person_id)
    all_events = load_all_events(paths)
    chg_event = find_change_event(all_events, change_id)
    if not chg_event:
        raise GroupConfigError(f"Unknown change_id '{change_id}'.")

    # Step 10: Check for unmerged conflicts or leftover conflict markers first
    marker_files = scan_conflict_markers(paths.root)
    if marker_files:
        raise GroupConfigError(
            f"Cannot finish INT {change_id}: leftover conflict markers found in {marker_files}"
        )

    # If a merge was in progress and conflicts were edited in the working tree, stage & commit now
    merge_head = paths.root / ".git" / "MERGE_HEAD"
    if merge_head.exists():
        run_git(paths.root, ["add", "-A"], check=True)
        run_git(
            paths.root,
            [
                "commit",
                "-m",
                f"Merge change {chg_event['change_id']} with conflict resolution: {conflict_resolution_summary or summary}",
            ],
            check=True,
        )
    else:
        # Also commit any semantic adaptation edits made after merge before running verification
        dirty_code = [
            u["path"]
            for u in get_uncommitted_files(paths.root)
            if not u["path"].replace("\\", "/").startswith(".group/")
        ]
        if dirty_code:
            for p in dirty_code:
                run_git(paths.root, ["add", "--", p], check=True)
            run_git(
                paths.root,
                ["commit", "-m", f"fix(int): adapt call sites for {chg_event['change_id']}"],
                check=True,
            )

    # Step 9: Confirm referenced commit is actually incorporated
    if not is_ancestor(paths.root, chg_event["commit"], "HEAD"):
        raise GroupConfigError(
            f"Verification failed (05 §3.9): commit {chg_event['commit']} of {change_id} "
            "is NOT an ancestor of current HEAD."
        )

    # Step 11 & 12: Mechanical build & automated tests
    test_res = run_project_tests(paths.root)
    tests_status = "pass" if test_res["automated_result"] in ("pass", "not_available") else "fail"
    build_status = "pass" if test_res["returncode"] == 0 else "fail"

    overall_result = (
        "success"
        if (build_status == "pass" and tests_status == "pass" and semantic_review == "pass")
        else "failed"
    )

    merge_commit = get_head_commit(paths.root, short=True) or ""
    target_branch = get_current_branch(paths.root)

    int_event = build_event(
        event_type="integration_result",
        group_id=group_cfg["group_id"],
        person_id=pid,
        related_events=[chg_event["event_id"]],
        payload={
            "change_id": chg_event["change_id"],
            "target_branch": target_branch,
            "result": overall_result,
            "merge_commit": merge_commit,
            "conflicts": list(conflicts_resolved or []),
            "conflict_resolution_summary": conflict_resolution_summary,
            "verification": {
                "build": build_status,
                "tests": tests_status,
                "semantic_review": semantic_review,
            },
            "summary": summary,
        },
    )
    event_file = write_immutable_event(paths, int_event)
    rel_event_path = str(event_file.relative_to(paths.root)).replace("\\", "/")
    _commit_and_push_paths(
        paths,
        [rel_event_path],
        f"chore(event): integration_result for {chg_event['change_id']} ({overall_result})",
        push=True,
    )

    return {
        "command": "INT",
        "change_id": chg_event["change_id"],
        "event_id": int_event["event_id"],
        "target_branch": target_branch,
        "result": overall_result,
        "merge_commit": merge_commit,
        "conflicts": int_event["conflicts"],
        "conflict_resolution_summary": conflict_resolution_summary,
        "verification": int_event["verification"],
        "test_details": {
            "passed": test_res["passed"],
            "failed": test_res["failed"],
            "commands": test_res["commands"],
        },
        "summary": summary,
    }


def cmd_int_abort(
    paths: GroupPaths,
    change_id: str,
    reason: str,
    requested_action: str,
    conflicts: Optional[List[str]] = None,
    person_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Abort an unsafe integration, roll back the working tree, and publish a blocker + needs_human integration_result."""
    group_cfg = load_group_config(paths)
    pid = require_person_id(paths, person_id)
    all_events = load_all_events(paths)
    chg_event = find_change_event(all_events, change_id)
    rel_ids = [chg_event["event_id"]] if chg_event else []

    if (paths.root / ".git" / "MERGE_HEAD").exists():
        run_git(paths.root, ["merge", "--abort"], check=False)

    target_branch = get_current_branch(paths.root)
    head_sha = get_head_commit(paths.root, short=True) or ""

    blocker_event = build_event(
        event_type="blocker",
        group_id=group_cfg["group_id"],
        person_id=pid,
        related_events=rel_ids,
        payload={
            "summary": reason,
            "blocking_change_id": change_id,
            "requested_action": requested_action,
        },
    )
    b_file = write_immutable_event(paths, blocker_event)

    int_event = build_event(
        event_type="integration_result",
        group_id=group_cfg["group_id"],
        person_id=pid,
        related_events=rel_ids + [blocker_event["event_id"]],
        payload={
            "change_id": change_id,
            "target_branch": target_branch,
            "result": "needs_human",
            "merge_commit": head_sha,
            "conflicts": list(conflicts or []),
            "conflict_resolution_summary": "Aborted integration pending human decision.",
            "verification": {
                "build": "not_run",
                "tests": "not_run",
                "semantic_review": "needs_human",
            },
            "summary": reason,
        },
    )
    i_file = write_immutable_event(paths, int_event)

    rel_b = str(b_file.relative_to(paths.root)).replace("\\", "/")
    rel_i = str(i_file.relative_to(paths.root)).replace("\\", "/")
    _commit_and_push_paths(
        paths,
        [rel_b, rel_i],
        f"chore(event): raise blocker on {change_id} (needs_human)",
        push=True,
    )

    return {
        "command": "INT",
        "status": "aborted_needs_human",
        "change_id": change_id,
        "blocker_event_id": blocker_event["event_id"],
        "integration_event_id": int_event["event_id"],
        "reason": reason,
        "requested_action": requested_action,
    }


def cmd_test(
    paths: GroupPaths,
    scope: str = "current_branch",
    human_checks_required: Optional[List[str]] = None,
    summary: Optional[str] = None,
    custom_command: Optional[str] = None,
    publish_event: bool = True,
    person_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute TEST [scope] procedure (05_command_procedures.md §5)."""
    group_cfg = load_group_config(paths)
    pid = require_person_id(paths, person_id)

    norm_scope = "current_branch" if scope in ("", "current", "current_branch") else scope
    original_branch = get_current_branch(paths.root)
    switched_temp = False

    try:
        if norm_scope not in ("current_branch", original_branch):
            # Could be 'main' or a change_id like 'C-17'
            all_events = load_all_events(paths)
            chg = find_change_event(all_events, norm_scope)
            target_ref = chg["commit"] if chg else norm_scope
            resolved = resolve_ref_commit(paths.root, target_ref)
            if resolved and not get_uncommitted_files(paths.root):
                run_git(paths.root, ["checkout", "--detach", resolved], check=True)
                switched_temp = True

        tested_commit = get_head_commit(paths.root, short=True) or "unknown"
        test_res = run_project_tests(paths.root, custom_command=custom_command)
    finally:
        if switched_temp and original_branch and original_branch != "HEAD":
            run_git(paths.root, ["checkout", original_branch], check=False)

    # Save detailed test output log in .group/local/logs/
    paths.ensure_directories()
    log_file = paths.local_logs_dir / f"test_{tested_commit}.log"
    log_file.write_text(test_res["output"], encoding="utf-8")

    auto_summary = summary or (
        f"Automated checks {test_res['automated_result'].upper()}: "
        f"{test_res['passed']} passed, {test_res['failed']} failed, {test_res['skipped']} skipped."
    )

    event_id = None
    if publish_event:
        ev = build_event(
            event_type="test_result",
            group_id=group_cfg["group_id"],
            person_id=pid,
            payload={
                "scope": norm_scope,
                "commit": tested_commit,
                "commands": test_res["commands"],
                "automated_result": test_res["automated_result"],
                "passed": test_res["passed"],
                "failed": test_res["failed"],
                "skipped": test_res["skipped"],
                "human_checks_required": list(human_checks_required or []),
                "summary": auto_summary,
            },
        )
        ev_path = write_immutable_event(paths, ev)
        rel_ev = str(ev_path.relative_to(paths.root)).replace("\\", "/")
        _commit_and_push_paths(
            paths,
            [rel_ev],
            f"chore(event): publish test_result for {norm_scope} ({tested_commit})",
            push=True,
        )
        event_id = ev["event_id"]

    return {
        "command": "TEST",
        "event_id": event_id,
        "scope": norm_scope,
        "commit": tested_commit,
        "commands": test_res["commands"],
        "automated_result": test_res["automated_result"],
        "passed": test_res["passed"],
        "failed": test_res["failed"],
        "skipped": test_res["skipped"],
        "human_checks_required": list(human_checks_required or []),
        "log_file": str(log_file.relative_to(paths.root)).replace("\\", "/"),
        "summary": auto_summary,
    }


def _collect_finalization_state(paths: GroupPaths) -> Dict[str, Any]:
    """Gather canonical commit, incorporated vs. unincorporated changes, reviews, tests, and contributors."""
    group_cfg = load_group_config(paths)
    canonical_branch = group_cfg["canonical_branch"]
    fetch_all(paths.root)
    materialize_shared_group_files(paths)

    canonical_commit_full = resolve_ref_commit(paths.root, canonical_branch)
    canonical_commit_short = resolve_ref_commit(paths.root, canonical_branch, short=True) or ""

    all_events = load_all_events(paths)
    members = load_members(paths)

    published_changes = [e for e in all_events if e["event_type"] == "change_published"]
    reviews = [e for e in all_events if e["event_type"] == "review"]
    tests = [e for e in all_events if e["event_type"] == "test_result"]
    integrations = [e for e in all_events if e["event_type"] == "integration_result"]
    blockers = [e for e in all_events if e["event_type"] == "blocker"]

    incorporated: List[Dict[str, Any]] = []
    unincorporated: List[Dict[str, Any]] = []
    rejected_change_ids = {
        r["change_id"] for r in reviews if r.get("verdict") == "reject"
    }

    for chg in published_changes:
        c_sha = chg["commit"]
        if is_ancestor(paths.root, c_sha, canonical_branch):
            incorporated.append(chg)
        else:
            disposition = "rejected" if chg["change_id"] in rejected_change_ids else "pending_or_unmerged"
            unincorporated.append({**chg, "disposition": disposition})

    # Determine contributors from members and events
    contributor_ids = sorted(
        set(list(members.keys()) + [e["person_id"] for e in all_events if e.get("person_id")])
    )
    contributors = []
    for cid in contributor_ids:
        disp = members.get(cid, {}).get("display_name", cid)
        contributors.append(f"{cid} ({disp})" if disp != cid else cid)

    return {
        "group_cfg": group_cfg,
        "canonical_branch": canonical_branch,
        "canonical_commit_full": canonical_commit_full or canonical_commit_short,
        "canonical_commit_short": canonical_commit_short,
        "incorporated_changes": incorporated,
        "unincorporated_changes": unincorporated,
        "reviews": reviews,
        "tests": tests,
        "integrations": integrations,
        "blockers": blockers,
        "contributors": contributors,
    }


def _render_group_report_markdown(
    title: str,
    state: Dict[str, Any],
    result_summary: str,
    validation_res: Dict[str, Any],
    known_limitations: List[str],
    human_checks: List[str],
) -> str:
    """Format markdown report containing all required sections in 07_testing_and_finalization.md §8."""
    group_cfg = state["group_cfg"]
    assign_path = group_cfg.get("assignment_file", ".group/assignment/assignment.md")
    inc_lines = []
    for c in state["incorporated_changes"]:
        inc_lines.append(
            f"- **{c['change_id']}** ({c['person_id']} on `{c['branch']}`, commit `{c['commit']}`): {c['summary']}"
        )
    if not inc_lines:
        inc_lines.append("- Baseline canonical branch commit.")

    uninc_lines = []
    for u in state["unincorporated_changes"]:
        uninc_lines.append(
            f"- **{u['change_id']}** ({u['person_id']}, status: `{u['disposition']}`): {u['summary']}"
        )

    val_lines = [
        f"- **Automated Test Result**: `{validation_res['automated_result']}` "
        f"({validation_res['passed']} passed, {validation_res['failed']} failed, {validation_res['skipped']} skipped)",
        f"- **Commands Run**: `{', '.join(validation_res['commands']) or 'none'}`",
        f"- **Recorded Reviews**: {len(state['reviews'])} review event(s)",
        f"- **Recorded Integrations**: {len(state['integrations'])} integration_result event(s)",
    ]
    for hc in human_checks:
        val_lines.append(f"- **Human Check**: {hc}")

    lim_lines = [f"- {lim}" for lim in known_limitations] if known_limitations else ["- None reported."]
    contrib_lines = [f"- {c}" for c in state["contributors"]] if state["contributors"] else ["- Group members"]

    md = [
        f"# {title}",
        "",
        "## Assignment",
        f"Group `{group_cfg['group_id']}` assignment declared in `{assign_path}`.",
        "",
        "## Result",
        result_summary,
        "",
        "## Canonical Commit",
        f"- Branch: `{state['canonical_branch']}`",
        f"- Commit: `{state['canonical_commit_full']}`",
        "",
        "## Important Changes",
        *inc_lines,
    ]
    if uninc_lines:
        md.extend(["", "### Unincorporated Published Changes", *uninc_lines])
    md.extend(
        [
            "",
            "## Validation",
            *val_lines,
            "",
            "## Known Limitations",
            *lim_lines,
            "",
            "## Contributors",
            *contrib_lines,
            "",
        ]
    )
    return "\n".join(md)


def cmd_final_prepare(
    paths: GroupPaths,
    result_summary: str = "Completed integrated group software on canonical branch.",
    known_limitations: Optional[List[str]] = None,
    human_checks: Optional[List[str]] = None,
    person_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Steps 1-10 of FINAL (05_command_procedures.md §7):
    Synchronize, inspect canonical state and unincorporated work, run final validation,
    generate .group/final/candidate.md and publish final_candidate event for human review.
    """
    pid = require_person_id(paths, person_id)
    state = _collect_finalization_state(paths)
    val_res = run_project_tests(paths.root)

    limitations = list(known_limitations or [])
    pending_important = [
        u for u in state["unincorporated_changes"] if u["disposition"] == "pending_or_unmerged"
    ]
    if pending_important:
        for p in pending_important:
            limitations.append(
                f"Published change {p['change_id']} ({p['person_id']}) is not merged into {state['canonical_branch']}."
            )

    candidate_md_text = _render_group_report_markdown(
        title="Group Final Candidate Report",
        state=state,
        result_summary=result_summary,
        validation_res=val_res,
        known_limitations=limitations,
        human_checks=list(human_checks or []),
    )
    paths.ensure_directories()
    paths.candidate_md.write_text(candidate_md_text, encoding="utf-8")

    ev = build_event(
        event_type="final_candidate",
        group_id=state["group_cfg"]["group_id"],
        person_id=pid,
        payload={
            "canonical_commit": state["canonical_commit_full"],
            "candidate_report_path": ".group/final/candidate.md",
            "tests_considered": [e["event_id"] for e in state["tests"][-5:]],
            "known_issues": limitations,
        },
    )
    ev_file = write_immutable_event(paths, ev)
    rel_ev = str(ev_file.relative_to(paths.root)).replace("\\", "/")
    _commit_and_push_paths(
        paths,
        [".group/final/candidate.md", rel_ev],
        f"chore(final): prepare final_candidate ({state['canonical_commit_short']})",
        push=True,
    )

    return {
        "command": "FINAL (prepare)",
        "status": "awaiting_human_confirmation",
        "event_id": ev["event_id"],
        "canonical_branch": state["canonical_branch"],
        "canonical_commit": state["canonical_commit_full"],
        "candidate_file": ".group/final/candidate.md",
        "validation_result": val_res["automated_result"],
        "unincorporated_changes": [u["change_id"] for u in state["unincorporated_changes"]],
        "known_limitations": limitations,
        "next_step": "Show .group/final/candidate.md to the human, then run 'groupctl final confirm' after approval.",
    }


def cmd_final_confirm(
    paths: GroupPaths,
    result_summary: str = "Completed integrated group software on canonical branch.",
    known_limitations: Optional[List[str]] = None,
    human_checks: Optional[List[str]] = None,
    person_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Steps 11-13 of FINAL (05_command_procedures.md §7 & 07_testing_and_finalization.md §8-9):
    After human confirmation, write .group/final/final_report.md, .group/final/final.json,
    and publish final_result event.
    """
    pid = require_person_id(paths, person_id)
    state = _collect_finalization_state(paths)
    val_res = run_project_tests(paths.root)
    if val_res["automated_result"] == "fail":
        raise GroupConfigError(
            "Refusing to finalize: automated validation failed on canonical state (07 §9)."
        )

    limitations = list(known_limitations or [])
    final_status = (
        "completed_with_known_limitations" if limitations else "completed"
    )

    # Record canonical commit BEFORE committing the finalization metadata envelope
    canonical_commit = state["canonical_commit_full"]

    report_md_text = _render_group_report_markdown(
        title="Group Final Report",
        state=state,
        result_summary=result_summary,
        validation_res=val_res,
        known_limitations=limitations,
        human_checks=list(human_checks or []),
    )
    paths.ensure_directories()
    paths.final_report_md.write_text(report_md_text, encoding="utf-8")

    final_json_data = {
        "protocol_version": PROTOCOL_VERSION,
        "group_id": state["group_cfg"]["group_id"],
        "canonical_branch": state["canonical_branch"],
        "canonical_commit": canonical_commit,
        "report_file": ".group/final/final_report.md",
        "initiated_by": pid,
        "created_at": utc_now_iso(),
        "status": final_status,
        "known_limitations": limitations,
    }
    write_json(paths.final_json, final_json_data)

    test_evidence_ids = [e["event_id"] for e in state["tests"]]
    ev = build_event(
        event_type="final_result",
        group_id=state["group_cfg"]["group_id"],
        person_id=pid,
        payload={
            "canonical_commit": canonical_commit,
            "final_report_path": ".group/final/final_report.md",
            "test_evidence": test_evidence_ids,
            "known_limitations": limitations,
            "initiated_by": pid,
        },
    )
    ev_file = write_immutable_event(paths, ev)
    rel_ev = str(ev_file.relative_to(paths.root)).replace("\\", "/")

    _commit_and_push_paths(
        paths,
        [".group/final/final_report.md", ".group/final/final.json", rel_ev],
        f"chore(final): finalize group result ({canonical_commit[:7]})",
        push=True,
    )

    return {
        "command": "FINAL (confirm)",
        "status": final_status,
        "event_id": ev["event_id"],
        "canonical_branch": state["canonical_branch"],
        "canonical_commit": canonical_commit,
        "report_file": ".group/final/final_report.md",
        "final_json": ".group/final/final.json",
        "initiated_by": pid,
        "known_limitations": limitations,
    }


def cmd_event_publish_generic(
    paths: GroupPaths,
    event_type: str,
    payload: Dict[str, Any],
    related_events: Optional[List[str]] = None,
    person_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Publish a finding, question, answer, or blocker event."""
    group_cfg = load_group_config(paths)
    pid = require_person_id(paths, person_id)
    ev = build_event(
        event_type=event_type,
        group_id=group_cfg["group_id"],
        person_id=pid,
        payload=payload,
        related_events=related_events,
    )
    ev_file = write_immutable_event(paths, ev)
    rel_ev = str(ev_file.relative_to(paths.root)).replace("\\", "/")
    _commit_and_push_paths(
        paths,
        [rel_ev],
        f"chore(event): publish {event_type} ({ev['event_id']})",
        push=True,
    )
    return ev
