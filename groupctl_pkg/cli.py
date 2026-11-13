"""Command-line interface for groupctl."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .commands import (
    cmd_branch_start,
    cmd_event_publish_generic,
    cmd_final_confirm,
    cmd_final_prepare,
    cmd_init,
    cmd_inspect,
    cmd_int_abort,
    cmd_int_finish,
    cmd_int_prepare,
    cmd_member_register,
    cmd_member_set_local,
    cmd_pub,
    cmd_rev,
    cmd_status,
    cmd_sync,
    cmd_test,
)
from .config import GroupConfigError, GroupPaths, find_repo_root, load_members
from .events import EventValidationError, load_all_events
from .git_ops import GitError


def _print_output(data: Dict[str, Any], as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    cmd = data.get("command") or data.get("status", "OK")
    print(f"=== groupctl: {cmd} ===")
    for k, v in data.items():
        if k in ("command",):
            continue
        if isinstance(v, (dict, list)):
            print(f"{k}: {json.dumps(v, indent=2, ensure_ascii=False)}")
        else:
            print(f"{k}: {v}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="groupctl",
        description="Deterministic collaboration helper for Human + AI software teams (Version 0.1).",
    )
    parser.add_argument(
        "--repo",
        type=str,
        default=None,
        help="Path to the repository root (defaults to current working directory).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output.",
    )

    sub = parser.add_subparsers(dest="subcommand", required=True)

    # init
    p_init = sub.add_parser("init", help="Initialize .group/ layout in repository.")
    p_init.add_argument("--group-id", required=True, help="Group identifier (e.g. G-12).")
    p_init.add_argument("--canonical-branch", default="main", help="Canonical branch name (default: main).")
    p_init.add_argument("--assignment-title", default="Group Programming Assignment")

    # member
    p_mem = sub.add_parser("member", help="Manage group members and local identity.")
    mem_sub = p_mem.add_subparsers(dest="member_action", required=True)

    p_mem_reg = mem_sub.add_parser("register", help="Register a member in .group/members/<person_id>.json.")
    p_mem_reg.add_argument("--person-id", required=True, help="Person ID (e.g. P17).")
    p_mem_reg.add_argument("--name", required=True, help="Display name (e.g. Susan).")
    p_mem_reg.add_argument("--no-local", action="store_true", help="Do not set as local identity.")
    p_mem_reg.add_argument("--commit", action="store_true", help="Commit and push member file.")

    p_mem_set = mem_sub.add_parser("set-local", help="Set local identity in .group/local/identity.json.")
    p_mem_set.add_argument("person_id", help="Person ID (e.g. P17).")
    p_mem_set.add_argument("--name", default=None, help="Optional display name.")

    mem_sub.add_parser("list", help="List known group members.")

    # branch
    p_br = sub.add_parser("branch", help="Start or switch to personal work branch people/<person_id>/<topic>.")
    p_br.add_argument("topic", help="Work branch topic (e.g. parser, renderer, tests).")
    p_br.add_argument("--person-id", default=None, help="Override person_id.")
    p_br.add_argument("--base", default=None, help="Optional base branch/ref.")

    # STATUS
    p_status = sub.add_parser("status", help="STATUS: Inspect local & group work state.")
    p_status.add_argument("--person-id", default=None)

    # SYNC
    p_sync = sub.add_parser("sync", help="SYNC: Fetch remotes, read new events, update from canonical when safe.")
    p_sync.add_argument("--no-merge-canonical", action="store_true", help="Do not merge canonical branch.")
    p_sync.add_argument("--skip-validation", action="store_true", help="Skip test run if sync merged code.")

    # PUB
    p_pub = sub.add_parser("pub", help="PUB: Commit, push personal branch, and publish change_published event.")
    p_pub.add_argument("--summary", required=True, help="Summary of the completed change.")
    p_pub.add_argument(
        "--interface-change",
        action="append",
        default=[],
        help="Interface or assumption change notice (repeatable).",
    )
    p_pub.add_argument(
        "--known-issue",
        action="append",
        default=[],
        help="Known issue notice (repeatable).",
    )
    p_pub.add_argument("--change-id", default=None, help="Explicit change ID (e.g. C-17).")
    p_pub.add_argument("--not-proposed", action="store_true", help="Set proposed_for_integration=false.")
    p_pub.add_argument("--skip-tests", action="store_true", help="Skip pre-publish test check.")
    p_pub.add_argument("--allow-main", action="store_true", help="Allow publishing on canonical branch.")
    p_pub.add_argument("--person-id", default=None)

    # inspect
    p_insp = sub.add_parser("inspect", help="Inspect a published change event and its actual Git diff.")
    p_insp.add_argument("change_id", help="Change ID (e.g. C-17).")

    # REV
    p_rev = sub.add_parser("rev", help="REV <change_id>: Review a published change and publish review event.")
    p_rev.add_argument("change_id", help="Change ID to review (e.g. C-22).")
    p_rev.add_argument(
        "--verdict",
        required=True,
        choices=["accept", "accept_with_changes", "reject", "needs_more_evidence"],
        help="Review verdict.",
    )
    p_rev.add_argument("--summary", required=True, help="Review summary.")
    p_rev.add_argument("--issue", action="append", default=[], help="Identified issue (repeatable).")
    p_rev.add_argument("--test-run", action="append", default=[], help="Test command run (repeatable).")
    p_rev.add_argument("--run-tests", action="store_true", help="Run project tests during review.")
    p_rev.add_argument("--person-id", default=None)

    # INT
    p_int = sub.add_parser("int", help="INT <change_id>: Integrate and verify a published change.")
    int_sub = p_int.add_subparsers(dest="int_action", required=True)

    p_int_prep = int_sub.add_parser("prepare", help="Steps 1-8: Inspect change and start merge.")
    p_int_prep.add_argument("change_id", help="Change ID (e.g. C-17).")

    p_int_fin = int_sub.add_parser(
        "finish",
        help="Steps 9-15: Verify ancestry, conflict markers, build/tests, semantic check, and publish integration_result.",
    )
    p_int_fin.add_argument("change_id", help="Change ID (e.g. C-17).")
    p_int_fin.add_argument("--summary", required=True, help="Integration summary.")
    p_int_fin.add_argument("--conflict-file", action="append", default=[], help="Conflicting file resolved.")
    p_int_fin.add_argument("--resolution-summary", default="", help="How conflicts or adaptations were resolved.")
    p_int_fin.add_argument(
        "--semantic-review",
        default="pass",
        choices=["pass", "fail", "needs_human"],
        help="Level 3 semantic compatibility review verdict.",
    )
    p_int_fin.add_argument("--person-id", default=None)

    p_int_run = int_sub.add_parser(
        "run",
        help="Run full INT <change_id> automatically if merge has no conflicts; pause if conflicts occur.",
    )
    p_int_run.add_argument("change_id", help="Change ID (e.g. C-17).")
    p_int_run.add_argument("--summary", default=None, help="Summary for integration_result.")
    p_int_run.add_argument("--semantic-review", default="pass", choices=["pass", "fail"])
    p_int_run.add_argument("--person-id", default=None)

    p_int_abort = int_sub.add_parser(
        "abort",
        help="Abort an unsafe integration and publish blocker + needs_human integration_result.",
    )
    p_int_abort.add_argument("change_id", help="Change ID (e.g. C-17).")
    p_int_abort.add_argument("--reason", required=True, help="Why conflict/integration cannot be safely resolved.")
    p_int_abort.add_argument("--requested-action", required=True, help="Decision requested from human.")
    p_int_abort.add_argument("--conflict-file", action="append", default=[])
    p_int_abort.add_argument("--person-id", default=None)

    # TEST
    p_test = sub.add_parser("test", help="TEST [scope]: Run automated validation and publish test_result.")
    p_test.add_argument("scope", nargs="?", default="current_branch", help="Scope: current_branch, main, or <change_id>.")
    p_test.add_argument("--human-check", action="append", default=[], help="Concrete human check required.")
    p_test.add_argument("--summary", default=None, help="Custom test summary.")
    p_test.add_argument("--command", default=None, help="Custom test command override.")
    p_test.add_argument("--no-publish", action="store_true", help="Do not publish a test_result event.")
    p_test.add_argument("--person-id", default=None)

    # FINAL
    p_final = sub.add_parser("final", help="FINAL: Group finalization workflow (prepare candidate -> confirm final).")
    final_sub = p_final.add_subparsers(dest="final_action", required=True)

    p_fin_prep = final_sub.add_parser(
        "prepare",
        help="Steps 1-10: Sync, validate canonical state, generate .group/final/candidate.md and final_candidate event.",
    )
    p_fin_prep.add_argument("--summary", default="Completed integrated group software on canonical branch.")
    p_fin_prep.add_argument("--limitation", action="append", default=[], help="Known limitation (repeatable).")
    p_fin_prep.add_argument("--human-check", action="append", default=[], help="Human check performed/needed.")
    p_fin_prep.add_argument("--person-id", default=None)

    p_fin_conf = final_sub.add_parser(
        "confirm",
        help="Steps 11-13: After human confirmation, create final_report.md, final.json, and final_result event.",
    )
    p_fin_conf.add_argument("--summary", default="Completed integrated group software on canonical branch.")
    p_fin_conf.add_argument("--limitation", action="append", default=[], help="Known limitation (repeatable).")
    p_fin_conf.add_argument("--human-check", action="append", default=[], help="Human check performed.")
    p_fin_conf.add_argument("--person-id", default=None)

    # event (finding, question, answer, blocker, list)
    p_ev = sub.add_parser("event", help="Inspect or publish collaboration events (finding, question, answer, blocker).")
    ev_sub = p_ev.add_subparsers(dest="event_action", required=True)

    ev_sub.add_parser("list", help="List all collaboration events in chronological order.")

    p_ev_find = ev_sub.add_parser("finding", help="Publish a finding event.")
    p_ev_find.add_argument("--summary", required=True)
    p_ev_find.add_argument("--evidence", action="append", required=True)
    p_ev_find.add_argument("--person-id", default=None)

    p_ev_q = ev_sub.add_parser("question", help="Publish a question event.")
    p_ev_q.add_argument("--question-id", required=True, help="e.g. Q-31")
    p_ev_q.add_argument("--text", required=True)
    p_ev_q.add_argument("--blocking", action="store_true")
    p_ev_q.add_argument("--person-id", default=None)

    p_ev_a = ev_sub.add_parser("answer", help="Publish an answer event.")
    p_ev_a.add_argument("--question-id", required=True, help="e.g. Q-31")
    p_ev_a.add_argument("--text", required=True)
    p_ev_a.add_argument("--related-event", action="append", default=[])
    p_ev_a.add_argument("--person-id", default=None)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    start_dir = Path(args.repo).resolve() if args.repo else Path.cwd()
    repo_root = Path(args.repo).resolve() if args.repo else find_repo_root(start_dir)
    paths = GroupPaths(repo_root)

    try:
        if args.subcommand == "init":
            res = cmd_init(
                paths,
                group_id=args.group_id,
                canonical_branch=args.canonical_branch,
                assignment_title=args.assignment_title,
            )
        elif args.subcommand == "member":
            if args.member_action == "register":
                res = cmd_member_register(
                    paths,
                    person_id=args.person_id,
                    display_name=args.name,
                    set_local=not args.no_local,
                    commit=args.commit,
                )
            elif args.member_action == "set-local":
                res = cmd_member_set_local(paths, person_id=args.person_id, display_name=args.name)
            else:
                res = {"members": load_members(paths)}
        elif args.subcommand == "branch":
            res = cmd_branch_start(paths, topic=args.topic, person_id=args.person_id, base_branch=args.base)
        elif args.subcommand == "status":
            res = cmd_status(paths, person_id=args.person_id)
        elif args.subcommand == "sync":
            res = cmd_sync(
                paths,
                merge_canonical=not args.no_merge_canonical,
                run_validation=not args.skip_validation,
            )
        elif args.subcommand == "pub":
            res = cmd_pub(
                paths,
                summary=args.summary,
                interface_changes=args.interface_change,
                known_issues=args.known_issue,
                proposed_for_integration=not args.not_proposed,
                change_id=args.change_id,
                person_id=args.person_id,
                skip_tests=args.skip_tests,
                allow_main=args.allow_main,
            )
        elif args.subcommand == "inspect":
            res = cmd_inspect(paths, change_id=args.change_id)
        elif args.subcommand == "rev":
            res = cmd_rev(
                paths,
                change_id=args.change_id,
                verdict=args.verdict,
                summary=args.summary,
                issues=args.issue,
                tests_run=args.test_run,
                run_tests_now=args.run_tests,
                person_id=args.person_id,
            )
        elif args.subcommand == "int":
            if args.int_action == "prepare":
                res = cmd_int_prepare(paths, change_id=args.change_id)
            elif args.int_action == "finish":
                res = cmd_int_finish(
                    paths,
                    change_id=args.change_id,
                    summary=args.summary,
                    conflicts_resolved=args.conflict_file,
                    conflict_resolution_summary=args.resolution_summary,
                    semantic_review=args.semantic_review,
                    person_id=args.person_id,
                )
            elif args.int_action == "run":
                prep = cmd_int_prepare(paths, change_id=args.change_id)
                if prep["status"] == "conflicts_detected":
                    res = prep
                else:
                    summary_txt = args.summary or f"Integrated {args.change_id} successfully."
                    res = cmd_int_finish(
                        paths,
                        change_id=args.change_id,
                        summary=summary_txt,
                        conflicts_resolved=[],
                        conflict_resolution_summary="",
                        semantic_review=args.semantic_review,
                        person_id=args.person_id,
                    )
            else:
                res = cmd_int_abort(
                    paths,
                    change_id=args.change_id,
                    reason=args.reason,
                    requested_action=args.requested_action,
                    conflicts=args.conflict_file,
                    person_id=args.person_id,
                )
        elif args.subcommand == "test":
            res = cmd_test(
                paths,
                scope=args.scope,
                human_checks_required=args.human_check,
                summary=args.summary,
                custom_command=args.command,
                publish_event=not args.no_publish,
                person_id=args.person_id,
            )
        elif args.subcommand == "final":
            if args.final_action == "prepare":
                res = cmd_final_prepare(
                    paths,
                    result_summary=args.summary,
                    known_limitations=args.limitation,
                    human_checks=args.human_check,
                    person_id=args.person_id,
                )
            else:
                res = cmd_final_confirm(
                    paths,
                    result_summary=args.summary,
                    known_limitations=args.limitation,
                    human_checks=args.human_check,
                    person_id=args.person_id,
                )
        elif args.subcommand == "event":
            if args.event_action == "list":
                events = load_all_events(paths)
                res = {"count": len(events), "events": events}
            elif args.event_action == "finding":
                res = cmd_event_publish_generic(
                    paths,
                    event_type="finding",
                    payload={"summary": args.summary, "evidence": args.evidence},
                    person_id=args.person_id,
                )
            elif args.event_action == "question":
                res = cmd_event_publish_generic(
                    paths,
                    event_type="question",
                    payload={
                        "question_id": args.question_id,
                        "text": args.text,
                        "blocking": bool(args.blocking),
                    },
                    person_id=args.person_id,
                )
            elif args.event_action == "answer":
                res = cmd_event_publish_generic(
                    paths,
                    event_type="answer",
                    payload={"question_id": args.question_id, "text": args.text},
                    related_events=args.related_event,
                    person_id=args.person_id,
                )
            else:
                res = {"status": "unknown_event_action"}
        else:
            parser.print_help()
            return 1

        _print_output(res, as_json=args.json)
        return 0
    except (GroupConfigError, EventValidationError, GitError) as exc:
        err_payload = {"error": type(exc).__name__, "message": str(exc)}
        if args.json:
            print(json.dumps(err_payload, indent=2, ensure_ascii=False), file=sys.stderr)
        else:
            print(f"[groupctl ERROR] ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
