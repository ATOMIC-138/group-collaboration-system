# AI Agent Collaboration Instructions (`AGENTS.md` / `GEMINI.md` / `CLAUDE.md`)
Protocol Version: 0.1

This repository uses the **Group Collaboration System** (`groupctl` + `.group/` contract).
Multiple human + AI pairs work in parallel on personal branches (`people/<person_id>/<topic>`) and coordinate through immutable JSON events in `.group/events/*.json` and the canonical branch (`main`).

Full specifications live in `specs/00_group_collaboration_assignment.md` through `specs/07_testing_and_finalization.md`, and the detailed skill procedure lives in `.agents/skills/group-collaboration/SKILL.md`.

---

## 1. Human-to-Agent Shorthand Commands

Whenever the human user types one of these seven commands, immediately execute the corresponding procedure using `python groupctl.py`:

| Command | Meaning | Primary Deterministic Tool Call |
| :--- | :--- | :--- |
| `SYNC` | Fetch remotes, discover new `.group/events/*.json`, safely merge `main`, check assumption warnings | `python groupctl.py --json sync` |
| `PUB` | Validate, commit, push personal branch, and publish a `change_published` event (`C-xx`) | `python groupctl.py --json pub --summary "..." [--interface-change "..."]` |
| `INT <change_id>` | Inspect diff, merge `<change_id>`, resolve conflicts safely, verify build/tests/semantics, publish `integration_result` | `python groupctl.py --json int prepare <id>` ➔ resolve/adapt ➔ `python groupctl.py --json int finish <id> --summary "..."` |
| `REV <change_id>` | Inspect real Git diff & tests without merging, then publish a `review` event (`accept`, `accept_with_changes`, `reject`, `needs_more_evidence`) | `python groupctl.py --json inspect <id>` ➔ `python groupctl.py --json rev <id> --verdict ... --summary "..."` |
| `TEST [scope]` | Run automated checks (`current_branch`, `main`, or `<change_id>`) and publish a `test_result` event | `python groupctl.py --json test [scope]` |
| `STATUS` | Report identity, branch, ahead/behind `main`, uncommitted edits, new events, and next recommended action | `python groupctl.py --json status` |
| `FINAL` | Synchronize, verify canonical `main`, prepare `.group/final/candidate.md` for human confirmation, then publish `.group/final/final_report.md` & `final.json` | `python groupctl.py --json final prepare` ➔ (human approves) ➔ `python groupctl.py --json final confirm` |

---

## 2. Non-Negotiable Engineering Rules

1. **Tool vs. Intelligence Boundary**:
   - Use `python groupctl.py` for mechanical facts (branch, commit ancestry, event schemas, test execution, conflict marker scans).
   - Use your reasoning for **Level 3 Semantic Review**: checking whether an incoming change's `interface_changes` or actual diff invalidates assumptions in caller code.
2. **Git Merge Is Not Proof of Correctness**:
   - After every `INT <change_id>`, verify:
     - **Level 1**: Commit ancestry (`git merge-base --is-ancestor`).
     - **Level 2**: No `<<<<<<<` conflict markers, build succeeds, automated tests pass.
     - **Level 3**: Combined code is semantically compatible.
3. **Conservative Conflict Resolution**:
   - When `groupctl int prepare <change_id>` reports `conflicts_detected`, inspect both sides carefully.
   - If the combined intent is clear, resolve the conflict, verify with tests, and run `groupctl int finish <change_id>`.
   - If the conflict requires an architectural or product decision, do **not** guess: run `groupctl int abort <change_id> --reason "..." --requested-action "..."` and ask the human.
4. **Never Silently Falsify Tests or History**:
   - Never force-push `main`, never edit already-published `.group/events/*.json` files, and never alter expected test outputs merely to make a failing implementation pass.
