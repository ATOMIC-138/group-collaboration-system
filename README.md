# Group Collaboration System (`groupctl` v0.1)

A vendor-neutral collaboration system enabling multiple **Human + AI Agent** pairs (e.g., Codex, Gemini, Claude Code) to work together as one group on a shared GitHub repository without requiring a central Dispatcher.

---

## 1. Repository Layout

```text
group_collaboration/
├── groupctl.py / groupctl / groupctl.cmd   # Deterministic collaboration CLI helper
├── groupctl_pkg/                           # Core Python package (zero external dependencies)
├── AGENTS.md / GEMINI.md / CLAUDE.md       # Portable AI Agent instructions
├── .agents/skills/group-collaboration/     # Portable Skill definition (SKILL.md)
├── .group/                                 # Shared Repository Contract (02_repository_contract.md)
│   ├── group.json                          # Group protocol & canonical branch config
│   ├── assignment/assignment.md            # Group assignment specification
│   ├── members/<person_id>.json            # Registered group member descriptors
│   ├── events/<event_id>.json              # Immutable collaboration event logs
│   ├── final/                              # candidate.md, final_report.md, final.json
│   └── local/                              # Local-only state (ignored by Git except .gitkeep)
├── src/                                    # Collaborative project source code (Parser + Renderer)
├── tests/                                  # Unit & integration tests
├── scripts/demo_simulation.py              # 15-step end-to-end verification & simulation script
└── specs/                                  # Authoritative specifications (00 through 07)
```

---

## 2. Human Shorthand Commands

Students can type these concise commands directly to their local AI agent, or invoke `groupctl` directly:

| Shorthand | Purpose | `groupctl` CLI Equivalent |
| :--- | :--- | :--- |
| **`SYNC`** | Fetch remotes, inspect new `.group/events/*.json`, merge canonical `main` when safe, and check assumption warnings | `python groupctl.py sync` |
| **`PUB`** | Validate, commit, push personal branch (`people/<id>/<topic>`), and publish a `change_published` event | `python groupctl.py pub --summary "..." [--interface-change "..."]` |
| **`INT <id>`** | Inspect diff, merge `<change_id>`, resolve conflicts safely, verify build/tests/semantics, and publish `integration_result` | `python groupctl.py int prepare <id>` ➔ `python groupctl.py int finish <id> --summary "..."` (or `python groupctl.py int run <id>`) |
| **`REV <id>`** | Review a published change's actual Git diff & tests without merging, and publish a `review` event | `python groupctl.py inspect <id>` ➔ `python groupctl.py rev <id> --verdict accept --summary "..."` |
| **`TEST [scope]`** | Run automated checks (`current_branch`, `main`, or `<change_id>`) and publish a `test_result` event | `python groupctl.py test [scope]` |
| **`STATUS`** | Report identity, branch, ahead/behind `main`, uncommitted edits, new events, blockers, and recommended next action | `python groupctl.py status` |
| **`FINAL`** | Prepare `.group/final/candidate.md` for human confirmation, then generate `.group/final/final_report.md`, `final.json`, and `final_result` | `python groupctl.py final prepare` ➔ `python groupctl.py final confirm` |

---

## 3. Quick Start

### Initialize or Join a Group Repository
```bash
# Set your local identity for this clone
python groupctl.py member set-local P17 --name "Susan"

# Start your personal work branch (people/P17/parser)
python groupctl.py branch parser

# Check current group status
python groupctl.py status
```

### Run the 15-Step End-to-End Verification Simulation
```bash
python scripts/demo_simulation.py
```
