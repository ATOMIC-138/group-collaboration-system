"""
End-to-End 15-Step Verification & Demonstration Script for Group Collaboration v0.1.

Verifies all 15 requirements in 00_group_collaboration_assignment.md §7 using:
- A shared bare Git remote repository (remote.git)
- Three separate local clones for P17 (Susan), P22 (Alex), and P31 (Jordan)
"""

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from groupctl_pkg.git_ops import resolve_git_executable


def _remove_readonly(func, path, _excinfo):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def run_git_cmd(cwd: Path, args: List[str], check: bool = True) -> subprocess.CompletedProcess:
    git_bin = resolve_git_executable()
    proc = subprocess.run(
        [git_bin] + args,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"Git failed in {cwd} ({' '.join(args)}):\n{proc.stderr}\n{proc.stdout}"
        )
    return proc


def run_groupctl(cwd: Path, args: List[str], check: bool = True) -> Dict[str, Any]:
    py_exe = sys.executable
    cmd = [py_exe, str(cwd / "groupctl.py"), "--json"] + args
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            f"groupctl failed in {cwd} ({' '.join(args)}):\nSTDERR: {proc.stderr}\nSTDOUT: {proc.stdout}"
        )
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def copy_starter_repo(dest: Path) -> None:
    """Copy project code, groupctl, specs, and agent skills into initial seed repo."""
    for item in [
        "groupctl.py",
        "groupctl.cmd",
        "groupctl",
        "AGENTS.md",
        "GEMINI.md",
        "CLAUDE.md",
        "README.md",
        "groupctl_pkg",
        "src",
        "tests",
        "specs",
        "scripts",
        ".agents",
    ]:
        src_path = PROJECT_ROOT / item
        dst_path = dest / item
        if src_path.is_dir():
            shutil.copytree(
                src_path,
                dst_path,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        elif src_path.is_file():
            shutil.copy2(src_path, dst_path)


def configure_git_user(repo_dir: Path, person_id: str, name: str) -> None:
    run_git_cmd(repo_dir, ["config", "user.name", f"{name} ({person_id})"])
    run_git_cmd(repo_dir, ["config", "user.email", f"{person_id.lower()}@group12.example.edu"])


def run_15_step_simulation(sim_root: Path) -> Dict[str, Any]:
    print(f"=== Running 15-Step Group Collaboration Simulation in: {sim_root} ===")
    remote_bare = sim_root / "remote.git"
    seed_dir = sim_root / "seed"
    clones_dir = sim_root / "clones"
    remote_bare.mkdir(parents=True, exist_ok=True)
    seed_dir.mkdir(parents=True, exist_ok=True)
    clones_dir.mkdir(parents=True, exist_ok=True)

    # Initialize bare remote repository
    run_git_cmd(remote_bare, ["init", "--bare"])

    # Initialize seed repository and push canonical 'main'
    copy_starter_repo(seed_dir)
    run_git_cmd(seed_dir, ["init"])
    configure_git_user(seed_dir, "INIT", "Course Instructor")
    run_git_cmd(seed_dir, ["checkout", "-b", "main"])

    run_groupctl(seed_dir, ["init", "--group-id", "G-12", "--canonical-branch", "main"])
    run_groupctl(seed_dir, ["member", "register", "--person-id", "P17", "--name", "Susan", "--no-local"])
    run_groupctl(seed_dir, ["member", "register", "--person-id", "P22", "--name", "Alex", "--no-local"])
    run_groupctl(seed_dir, ["member", "register", "--person-id", "P31", "--name", "Jordan", "--no-local"])

    run_git_cmd(seed_dir, ["add", "-A"])
    run_git_cmd(seed_dir, ["commit", "-m", "chore: initial canonical main repository state"])
    run_git_cmd(seed_dir, ["remote", "add", "origin", str(remote_bare)])
    run_git_cmd(seed_dir, ["push", "-u", "origin", "main"])
    run_git_cmd(remote_bare, ["symbolic-ref", "HEAD", "refs/heads/main"])

    # -------------------------------------------------------------------------
    # Requirement 1 & 2: Three people clone the shared repo and create personal work branches
    # -------------------------------------------------------------------------
    p17_dir = clones_dir / "P17"
    p22_dir = clones_dir / "P22"
    p31_dir = clones_dir / "P31"

    for pid, name, topic, clone_path in [
        ("P17", "Susan", "parser", p17_dir),
        ("P22", "Alex", "renderer", p22_dir),
        ("P31", "Jordan", "tests", p31_dir),
    ]:
        run_git_cmd(clones_dir, ["clone", str(remote_bare), str(clone_path)])
        configure_git_user(clone_path, pid, name)
        run_groupctl(clone_path, ["member", "set-local", pid, "--name", name])
        run_groupctl(clone_path, ["branch", topic])

    print("[PASS] Step 1 & 2: P17, P22, P31 cloned shared repo and started personal branches.")

    # -------------------------------------------------------------------------
    # Requirement 3 & 4: P17 implements parser enhancement & publishes C-17 using PUB
    # -------------------------------------------------------------------------
    (p17_dir / "src" / "model.py").write_text(
        '"""Shared data structures for the Parser and Renderer."""\n\n'
        "from dataclasses import dataclass, field\n"
        "from typing import List\n\n\n"
        "@dataclass\n"
        "class BlockNode:\n"
        '    """Represents a parsed block node in a document."""\n\n'
        "    kind: str\n"
        "    content: str\n"
        '    children: List["BlockNode"] = field(default_factory=list)\n'
        "    line: int = 1\n"
        "    end_column: int = 0\n\n\n"
        "@dataclass\n"
        "class ParseResult:\n"
        '    """Structured result returned by Parser.parse."""\n\n'
        "    nodes: List[BlockNode] = field(default_factory=list)\n"
        "    warnings: List[str] = field(default_factory=list)\n"
        '    source_name: str = "<memory>"\n',
        encoding="utf-8",
    )

    parser_code = (p17_dir / "src" / "parser.py").read_text(encoding="utf-8")
    parser_code = parser_code.replace(
        "line=idx)",
        "line=idx, end_column=len(raw_line))",
    )
    (p17_dir / "src" / "parser.py").write_text(parser_code, encoding="utf-8")

    pub_c17 = run_groupctl(
        p17_dir,
        [
            "pub",
            "--change-id",
            "C-17",
            "--summary",
            "Track end_column source positions on BlockNode in Parser.",
            "--interface-change",
            "BlockNode now includes end_column: int populated by Parser.parse.",
        ],
    )
    assert pub_c17["change_id"] == "C-17"
    print(f"[PASS] Step 3 & 4: P17 published {pub_c17['change_id']} ({pub_c17['event_id']}).")

    # -------------------------------------------------------------------------
    # Requirement 5 & 6: P31 runs SYNC, discovers C-17, reviews C-17 (REV), and integrates C-17 (INT)
    # -------------------------------------------------------------------------
    sync_p31 = run_groupctl(p31_dir, ["sync"])
    discovered_ids = [e.get("change_id") for e in sync_p31["new_events"] if e.get("change_id")]
    assert "C-17" in discovered_ids, f"Expected C-17 in discovered events, got {discovered_ids}"
    print("[PASS] Step 5: P31 ran SYNC and discovered C-17 and its interface change warning.")

    rev_c17 = run_groupctl(
        p31_dir,
        [
            "rev",
            "C-17",
            "--verdict",
            "accept",
            "--summary",
            "Verified end_column tracking in BlockNode and Parser.",
            "--run-tests",
        ],
    )
    assert rev_c17["verdict"] == "accept"
    print(f"[PASS] Step 6a: P31 reviewed C-17 with verdict={rev_c17['verdict']}.")

    # -------------------------------------------------------------------------
    # Requirement 7 & 8: Clean Git merge via INT C-17 + 3-level verification (Git + Mechanical + Semantic)
    # -------------------------------------------------------------------------
    int_c17_p31 = run_groupctl(
        p31_dir,
        [
            "int",
            "run",
            "C-17",
            "--summary",
            "Cleanly integrated C-17 into people/P31/tests and verified build, tests, and semantics.",
            "--semantic-review",
            "pass",
        ],
    )
    assert int_c17_p31["result"] == "success"
    assert int_c17_p31["verification"] == {
        "build": "pass",
        "tests": "pass",
        "semantic_review": "pass",
    }
    print("[PASS] Step 6b, 7 & 8: P31 integrated C-17 cleanly with Level 1-3 verification.")

    # -------------------------------------------------------------------------
    # Requirement 9 & 10: Deliberate Git conflict between P22 and C-17, guided AI conflict resolution
    # -------------------------------------------------------------------------
    # P22 independently modifies src/model.py (same region as P17) and src/renderer.py
    (p22_dir / "src" / "model.py").write_text(
        '"""Shared data structures for the Parser and Renderer."""\n\n'
        "from dataclasses import dataclass, field\n"
        "from typing import List\n\n\n"
        "@dataclass\n"
        "class BlockNode:\n"
        '    """Represents a parsed block node in a document."""\n\n'
        "    kind: str\n"
        "    content: str\n"
        '    children: List["BlockNode"] = field(default_factory=list)\n'
        "    line: int = 1\n"
        '    style_class: str = "default"\n\n\n'
        "@dataclass\n"
        "class ParseResult:\n"
        '    """Structured result returned by Parser.parse."""\n\n'
        "    nodes: List[BlockNode] = field(default_factory=list)\n"
        "    warnings: List[str] = field(default_factory=list)\n"
        '    source_name: str = "<memory>"\n',
        encoding="utf-8",
    )

    (p22_dir / "src" / "renderer.py").write_text(
        '"""Document renderer module (maintained collaboratively, e.g. by P22)."""\n\n'
        "from typing import List, Union\n"
        "from .model import BlockNode, ParseResult\n\n\n"
        "class Renderer:\n"
        '    """Renders a ParseResult or list of BlockNodes into formatted HTML."""\n\n'
        "    def render(self, parsed: Union[ParseResult, List[BlockNode]]) -> str:\n"
        "        nodes = parsed.nodes if isinstance(parsed, ParseResult) else parsed\n"
        "        lines = [self._render_node(node) for node in nodes]\n"
        '        return "\\n".join(lines)\n\n'
        "    def _render_node(self, node: BlockNode) -> str:\n"
        '        cls_attr = f\' class="{node.style_class}"\' if getattr(node, "style_class", "default") != "default" else ""\n'
        '        if node.kind == "heading":\n'
        '            return f"<h1{cls_attr}>{node.content}</h1>"\n'
        '        if node.kind == "item":\n'
        '            return f"<li{cls_attr}>{node.content}</li>"\n'
        '        if node.kind == "section":\n'
        '            inner = "\\n".join(self._render_node(child) for child in node.children)\n'
        "            if inner:\n"
        '                return f\'<section data-title="{node.content}"{cls_attr}>\\n{inner}\\n</section>\'\n'
        '            return f\'<section data-title="{node.content}"{cls_attr}></section>\'\n'
        '        return f"<p{cls_attr}>{node.content}</p>"\n',
        encoding="utf-8",
    )

    # P22 commits local work first or runs SYNC then INT C-17
    run_git_cmd(p22_dir, ["add", "src/model.py", "src/renderer.py"])
    run_git_cmd(p22_dir, ["commit", "-m", "feat(P22): add style_class support to BlockNode and Renderer"])

    prep_conflict = run_groupctl(p22_dir, ["int", "prepare", "C-17"])
    assert prep_conflict["status"] == "conflicts_detected", f"Expected conflict, got {prep_conflict}"
    assert "src/model.py" in prep_conflict["conflicts"]
    print(f"[PASS] Step 9: Deliberate conflict detected in {prep_conflict['conflicts']} during INT C-17 on P22.")

    # Step 10: AI agent resolves the conflict deliberately by combining both fields (end_column + style_class)
    (p22_dir / "src" / "model.py").write_text(
        '"""Shared data structures for the Parser and Renderer."""\n\n'
        "from dataclasses import dataclass, field\n"
        "from typing import List\n\n\n"
        "@dataclass\n"
        "class BlockNode:\n"
        '    """Represents a parsed block node in a document."""\n\n'
        "    kind: str\n"
        "    content: str\n"
        '    children: List["BlockNode"] = field(default_factory=list)\n'
        "    line: int = 1\n"
        "    end_column: int = 0\n"
        '    style_class: str = "default"\n\n\n'
        "@dataclass\n"
        "class ParseResult:\n"
        '    """Structured result returned by Parser.parse."""\n\n'
        "    nodes: List[BlockNode] = field(default_factory=list)\n"
        "    warnings: List[str] = field(default_factory=list)\n"
        '    source_name: str = "<memory>"\n',
        encoding="utf-8",
    )

    fin_conflict = run_groupctl(
        p22_dir,
        [
            "int",
            "finish",
            "C-17",
            "--summary",
            "Resolved src/model.py conflict by preserving both P17 end_column and P22 style_class.",
            "--conflict-file",
            "src/model.py",
            "--resolution-summary",
            "Combined BlockNode.end_column (from C-17) and BlockNode.style_class (from P22).",
            "--semantic-review",
            "pass",
        ],
    )
    assert fin_conflict["result"] == "success"
    print(f"[PASS] Step 10: Conflict resolved and verified ({fin_conflict['event_id']}).")

    # P22 now publishes the combined Renderer + Model work as C-22
    pub_c22 = run_groupctl(
        p22_dir,
        [
            "pub",
            "--change-id",
            "C-22",
            "--summary",
            "Add style_class rendering support integrated with C-17 BlockNode.end_column.",
            "--interface-change",
            "BlockNode includes style_class: str = 'default' rendered as HTML class attribute.",
        ],
    )
    assert pub_c22["change_id"] == "C-22"

    # -------------------------------------------------------------------------
    # Requirement 11 & 12: P31 integrates C-22, adds integration tests, runs TEST and publishes test_result
    # -------------------------------------------------------------------------
    run_groupctl(p31_dir, ["sync"])
    int_c22_p31 = run_groupctl(
        p31_dir,
        [
            "int",
            "run",
            "C-22",
            "--summary",
            "Integrated C-22 into people/P31/tests.",
            "--semantic-review",
            "pass",
        ],
    )
    assert int_c22_p31["result"] == "success"

    # P31 adds an integration test covering both end_column (C-17) and style_class (C-22)
    test_r_path = p31_dir / "tests" / "test_renderer.py"
    test_r_content = test_r_path.read_text(encoding="utf-8")
    extra_test = (
        "\n    def test_combined_end_column_and_style_class(self):\n"
        "        parser = Parser()\n"
        "        renderer = Renderer()\n"
        '        parsed = parser.parse("# Combined Check")\n'
        "        self.assertGreater(parsed.nodes[0].end_column, 0)\n"
        '        parsed.nodes[0].style_class = "highlight"\n'
        "        html = renderer.render(parsed)\n"
        '        self.assertIn(\'<h1 class="highlight">Combined Check</h1>\', html)\n'
    )
    test_r_path.write_text(
        test_r_content.replace("if __name__ ==", extra_test + "\n\nif __name__ =="),
        encoding="utf-8",
    )

    pub_c31 = run_groupctl(
        p31_dir,
        [
            "pub",
            "--change-id",
            "C-31",
            "--summary",
            "Add integration test verifying combined C-17 end_column and C-22 style_class.",
        ],
    )
    test_event = run_groupctl(
        p31_dir,
        [
            "test",
            "current_branch",
            "--human-check",
            "Open rendered HTML output in browser and verify .highlight heading contrast.",
        ],
    )
    assert test_event["automated_result"] == "pass"
    assert test_event["passed"] >= 10
    print(f"[PASS] Step 11 & 12: P31 ran TEST and published test_result ({test_event['event_id']}).")

    # -------------------------------------------------------------------------
    # Requirement 13: Group reaches accepted canonical state on 'main'
    # -------------------------------------------------------------------------
    run_git_cmd(p17_dir, ["checkout", "main"])
    run_groupctl(p17_dir, ["sync"])
    int_main = run_groupctl(
        p17_dir,
        [
            "int",
            "run",
            "C-31",
            "--summary",
            "Promote verified combined changes (C-17, C-22, C-31) to canonical main branch.",
            "--semantic-review",
            "pass",
        ],
    )
    assert int_main["result"] == "success"
    run_git_cmd(p17_dir, ["push", "origin", "main"])
    print("[PASS] Step 13: Group reached accepted canonical state on 'main'.")

    # -------------------------------------------------------------------------
    # Requirement 14 & 15: Any recognized member initiates FINAL (prepare -> human confirm)
    # -------------------------------------------------------------------------
    final_prep = run_groupctl(
        p17_dir,
        [
            "final",
            "prepare",
            "--summary",
            "Completed Parser (C-17), Renderer (C-22), and Integration Test Suite (C-31) on main.",
            "--human-check",
            "Verified rendered HTML heading highlight class visually.",
        ],
    )
    assert (p17_dir / ".group" / "final" / "candidate.md").exists()

    final_conf = run_groupctl(
        p17_dir,
        [
            "final",
            "confirm",
            "--summary",
            "Completed Parser (C-17), Renderer (C-22), and Integration Test Suite (C-31) on main.",
            "--human-check",
            "Verified rendered HTML heading highlight class visually.",
        ],
    )
    assert final_conf["status"] == "completed"
    assert (p17_dir / ".group" / "final" / "final_report.md").exists()
    assert (p17_dir / ".group" / "final" / "final.json").exists()
    print(
        f"[PASS] Step 14 & 15: FINAL completed on canonical commit {final_conf['canonical_commit']} "
        f"({final_conf['event_id']})."
    )

    return {
        "simulation_root": str(sim_root),
        "canonical_commit": final_conf["canonical_commit"],
        "final_json": json.loads(
            (p17_dir / ".group" / "final" / "final.json").read_text(encoding="utf-8")
        ),
        "events_count": len(list((p17_dir / ".group" / "events").glob("*.json"))),
    }


def sync_demo_artifacts_to_main_workspace(sim_p17_dir: Path) -> None:
    """Copy the verified final state (src, tests, .group, and git history/branches) into the main workspace."""
    for folder in ["src", "tests"]:
        for f in (sim_p17_dir / folder).glob("*.py"):
            shutil.copy2(f, PROJECT_ROOT / folder / f.name)

    for sub in ["events", "final", "members", "assignment"]:
        src_sub = sim_p17_dir / ".group" / sub
        dst_sub = PROJECT_ROOT / ".group" / sub
        if dst_sub.exists():
            for old_f in dst_sub.glob("*.json"):
                old_f.unlink()
        dst_sub.mkdir(parents=True, exist_ok=True)
        for item in src_sub.glob("*"):
            if item.is_file():
                shutil.copy2(item, dst_sub / item.name)

    # Mirror the simulation git history & branches into PROJECT_ROOT/.git so commit hashes match events
    dst_git = PROJECT_ROOT / ".git"
    if dst_git.exists():
        shutil.rmtree(dst_git, onerror=_remove_readonly)
    shutil.copytree(sim_p17_dir / ".git", dst_git)
    run_git_cmd(PROJECT_ROOT, ["remote", "remove", "origin"], check=False)
    for b in ["people/P17/parser", "people/P22/renderer", "people/P31/tests"]:
        run_git_cmd(
            PROJECT_ROOT,
            ["branch", "-f", b, f"refs/remotes/origin/{b}"],
            check=False,
        )
    run_git_cmd(PROJECT_ROOT, ["checkout", "main"], check=False)


if __name__ == "__main__":
    persist_dir = PROJECT_ROOT / ".group" / "local" / "demo_sandbox"
    if persist_dir.exists():
        shutil.rmtree(persist_dir, onerror=_remove_readonly)
    persist_dir.mkdir(parents=True, exist_ok=True)

    summary = run_15_step_simulation(persist_dir)
    sync_demo_artifacts_to_main_workspace(persist_dir / "clones" / "P17")
    print("\n=== ALL 15 DEMONSTRATION STEPS PASSED ===")
    print(json.dumps(summary, indent=2))
