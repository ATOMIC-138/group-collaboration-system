"""Deterministic Git operations and repository inspection helpers."""

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import GroupPaths


class GitError(Exception):
    """Raised when a Git command fails unexpectedly."""


def resolve_git_executable() -> str:
    """Resolve the git executable across PATH and common Windows installation paths."""
    env_git = os.environ.get("GROUPCTL_GIT_BIN")
    if env_git and Path(env_git).exists():
        return env_git

    which_git = shutil.which("git")
    if which_git:
        return which_git

    candidates = [
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files\Git\bin\git.exe",
        r"C:\Program Files (x86)\Git\cmd\git.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Git\cmd\git.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\GitHubDesktop\app-*\resources\app\git\cmd\git.exe"),
        r"C:\Xilinx\Vivado\2018.3\tps\win64\git-2.16.2\cmd\git.exe",
        r"C:\Xilinx\Vivado\2018.3\tps\win64\git-2.16.2\bin\git.exe",
    ]
    for candidate in candidates:
        if "*" in candidate:
            parent = Path(candidate.split("*")[0]).parent
            if parent.exists():
                for match in parent.glob("app-*/resources/app/git/cmd/git.exe"):
                    return str(match)
        elif Path(candidate).exists():
            return candidate

    return "git"


def run_git(
    repo_root: Path,
    args: List[str],
    check: bool = True,
) -> subprocess.CompletedProcess:
    git_bin = resolve_git_executable()
    cmd = [git_bin] + args
    proc = subprocess.run(
        cmd,
        cwd=str(repo_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and proc.returncode != 0:
        raise GitError(
            f"Git command failed ({' '.join(args)}): {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc


def is_git_repo(repo_root: Path) -> bool:
    proc = run_git(repo_root, ["rev-parse", "--is-inside-work-tree"], check=False)
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def get_current_branch(repo_root: Path) -> str:
    proc = run_git(repo_root, ["symbolic-ref", "--short", "HEAD"], check=False)
    if proc.returncode != 0:
        proc = run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"], check=False)
    return proc.stdout.strip() or "HEAD"


def get_head_commit(repo_root: Path, short: bool = False) -> Optional[str]:
    flag = ["--short"] if short else []
    proc = run_git(repo_root, ["rev-parse"] + flag + ["HEAD"], check=False)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def resolve_ref_commit(repo_root: Path, ref: str, short: bool = False) -> Optional[str]:
    flag = ["--short"] if short else []
    for candidate in [ref, f"origin/{ref}", f"refs/heads/{ref}", f"refs/remotes/origin/{ref}"]:
        proc = run_git(
            repo_root,
            ["rev-parse", "--verify", "--quiet"] + flag + [f"{candidate}^{{commit}}"],
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip()
    return None


def get_uncommitted_files(repo_root: Path) -> List[Dict[str, str]]:
    """Return list of modified/untracked files from git status --porcelain."""
    proc = run_git(repo_root, ["status", "--porcelain"], check=False)
    if proc.returncode != 0:
        return []
    items: List[Dict[str, str]] = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        status = line[:2]
        file_path = line[3:].strip()
        items.append({"status": status, "path": file_path})
    return items


def get_unmerged_conflicts(repo_root: Path) -> List[str]:
    """Return list of files with unmerged Git conflict entries."""
    proc = run_git(repo_root, ["diff", "--name-only", "--diff-filter=U"], check=False)
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


CONFLICT_MARKER_RE = re.compile(r"^(<{7}\s|={7}$|>{7}\s)", re.MULTILINE)


def scan_conflict_markers(repo_root: Path) -> List[str]:
    """Scan tracked working-tree files for leftover conflict markers (01 §5, 05 §3.10)."""
    proc = run_git(repo_root, ["ls-files"], check=False)
    if proc.returncode != 0:
        return []
    flagged: List[str] = []
    for rel_path in proc.stdout.splitlines():
        rel_path = rel_path.strip()
        if not rel_path or rel_path.startswith(".group/"):
            continue
        full_path = repo_root / rel_path
        if not full_path.is_file():
            continue
        try:
            text = full_path.read_text(encoding="utf-8", errors="ignore")
            if CONFLICT_MARKER_RE.search(text):
                flagged.append(rel_path)
        except Exception:
            continue
    return flagged


SUSPICIOUS_FILE_PATTERNS = [
    re.compile(r"(^|/)\.env(\..+)?$", re.IGNORECASE),
    re.compile(r"\.(pem|key|p12|pfx)$", re.IGNORECASE),
    re.compile(r"(^|/)id_(rsa|ed25519)$", re.IGNORECASE),
    re.compile(r"(^|/)__pycache__(/|$)"),
    re.compile(r"\.(pyc|pyo|pyd|DS_Store|thumbs\.db)$", re.IGNORECASE),
]

SECRET_CONTENT_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"AIza[0-9A-Za-z\-_]{30,}"),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH |)PRIVATE KEY-----"),
]


def scan_hygiene_issues(repo_root: Path, paths_to_check: List[str]) -> List[str]:
    """Check for accidental secrets, generated junk, or conflict markers (05 §2.2)."""
    issues: List[str] = []
    for rel_path in paths_to_check:
        norm = rel_path.replace("\\", "/")
        for pat in SUSPICIOUS_FILE_PATTERNS:
            if pat.search(norm):
                issues.append(f"Suspicious/junk/secret file path detected: {norm}")
                break
        full_path = repo_root / rel_path
        if full_path.is_file():
            try:
                content = full_path.read_text(encoding="utf-8", errors="ignore")
                if CONFLICT_MARKER_RE.search(content):
                    issues.append(f"Leftover conflict markers in: {norm}")
                for sec_pat in SECRET_CONTENT_PATTERNS:
                    if sec_pat.search(content):
                        issues.append(f"Potential secret token/key detected in: {norm}")
                        break
            except Exception:
                continue
    return issues


def is_ancestor(repo_root: Path, ancestor_ref: str, descendant_ref: str = "HEAD") -> bool:
    """Return True if ancestor_ref is merged into descendant_ref (05 §3.9)."""
    anc = resolve_ref_commit(repo_root, ancestor_ref)
    desc = resolve_ref_commit(repo_root, descendant_ref)
    if not anc or not desc:
        return False
    proc = run_git(repo_root, ["merge-base", "--is-ancestor", anc, desc], check=False)
    return proc.returncode == 0


def get_ahead_behind(repo_root: Path, branch_a: str, branch_b: str) -> Tuple[int, int]:
    """Return (ahead, behind) of branch_a relative to branch_b."""
    ref_a = resolve_ref_commit(repo_root, branch_a)
    ref_b = resolve_ref_commit(repo_root, branch_b)
    if not ref_a or not ref_b:
        return (0, 0)
    proc = run_git(
        repo_root,
        ["rev-list", "--left-right", "--count", f"{ref_a}...{ref_b}"],
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return (0, 0)
    parts = proc.stdout.strip().split()
    if len(parts) == 2:
        return (int(parts[0]), int(parts[1]))
    return (0, 0)


def has_remote(repo_root: Path, remote_name: str = "origin") -> bool:
    proc = run_git(repo_root, ["remote"], check=False)
    if proc.returncode != 0:
        return False
    remotes = [r.strip() for r in proc.stdout.splitlines() if r.strip()]
    return remote_name in remotes


def fetch_all(repo_root: Path) -> bool:
    """Fetch all remote branches and tags if a remote is configured."""
    if not has_remote(repo_root):
        return False
    proc = run_git(repo_root, ["fetch", "--all", "--tags", "--prune"], check=False)
    return proc.returncode == 0


def list_all_branch_refs(repo_root: Path) -> List[str]:
    """List all local and remote branch refs in the repository."""
    proc = run_git(
        repo_root,
        ["for-each-ref", "--format=%(refname)", "refs/heads/", "refs/remotes/"],
        check=False,
    )
    if proc.returncode != 0:
        return []
    refs = []
    for line in proc.stdout.splitlines():
        ref = line.strip()
        if ref and not ref.endswith("/HEAD"):
            refs.append(ref)
    return refs


def materialize_shared_group_files(paths: GroupPaths) -> Dict[str, List[str]]:
    """
    Discover immutable .group/events/*.json and .group/members/*.json across all
    local and fetched remote branches, materializing any missing files into the
    local working tree so agents have full group awareness before merging branches.
    """
    repo_root = paths.root
    paths.ensure_directories()
    imported_events: List[str] = []
    imported_members: List[str] = []

    for ref in list_all_branch_refs(repo_root):
        for subdir, target_dir, bucket in [
            (".group/events", paths.events_dir, imported_events),
            (".group/members", paths.members_dir, imported_members),
        ]:
            proc = run_git(
                repo_root,
                ["ls-tree", "--name-only", ref, f"{subdir}/"],
                check=False,
            )
            if proc.returncode != 0 or not proc.stdout.strip():
                continue
            for rel_item in proc.stdout.splitlines():
                rel_item = rel_item.strip()
                if not rel_item.endswith(".json"):
                    continue
                fname = Path(rel_item).name
                local_file = target_dir / fname
                if local_file.exists():
                    continue
                show_proc = run_git(repo_root, ["show", f"{ref}:{rel_item}"], check=False)
                if show_proc.returncode == 0 and show_proc.stdout.strip():
                    local_file.write_text(show_proc.stdout, encoding="utf-8")
                    bucket.append(fname)

    return {
        "imported_events": sorted(set(imported_events)),
        "imported_members": sorted(set(imported_members)),
    }


def get_commit_diff_and_files(
    repo_root: Path,
    target_commit: str,
    base_ref: Optional[str] = None,
) -> Dict[str, Any]:
    """Return changed files and unified diff for a commit or branch."""
    resolved = resolve_ref_commit(repo_root, target_commit)
    if not resolved:
        raise GitError(f"Cannot resolve commit or branch '{target_commit}'.")

    if base_ref:
        resolved_base = resolve_ref_commit(repo_root, base_ref)
        mb_proc = run_git(
            repo_root,
            ["merge-base", resolved_base or base_ref, resolved],
            check=False,
        )
        base = mb_proc.stdout.strip() if mb_proc.returncode == 0 else f"{resolved}~1"
        diff_range = f"{base}..{resolved}"
    else:
        parent_check = run_git(repo_root, ["rev-parse", "--verify", f"{resolved}~1"], check=False)
        diff_range = f"{resolved}~1..{resolved}" if parent_check.returncode == 0 else resolved

    files_proc = run_git(
        repo_root,
        ["diff-tree", "--no-commit-id", "--name-only", "-r", resolved],
        check=False,
    )
    files = [
        f.strip()
        for f in files_proc.stdout.splitlines()
        if f.strip() and not f.strip().startswith(".group/")
    ]

    diff_proc = run_git(
        repo_root,
        ["diff", diff_range, "--", ".", ":(exclude).group/events"],
        check=False,
    )
    return {
        "commit": resolved,
        "short_commit": resolved[:7],
        "files_changed": files,
        "diff": diff_proc.stdout,
    }
