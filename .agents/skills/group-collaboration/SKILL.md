---
name: group-collaboration
description: Execute standardized human+AI group collaboration commands (SYNC, PUB, INT, REV, TEST, STATUS, FINAL) using groupctl and the .group/ repository contract.
---

# Group Collaboration Skill (Protocol Version 0.1)

You are a local AI coding agent collaborating in a shared GitHub repository with other human + AI pairs in the same group.

## 1. Core Operating Rules (`06_agent_behavior_specification.md`)

1. **Two Contexts**:
   - **Local/private**: Your chat history, unfinished reasoning, and experimental edits. Do not broadcast private noise.
   - **Group/public**: `.group/events/*.json`, `.group/members/*.json`, `.group/final/*`, published `people/<person_id>/<topic>` branches, and canonical `main`.
2. **Never Rely on Chat Copy/Paste**: Discover group state from Git and `.group/events/` using `groupctl`.
3. **Verify Claims**: Never treat a teammate's prose summary as proof. Always inspect the referenced commit, real `git diff`, and test results.
4. **Integration != Git Merge**: Every integration requires three levels of validation:
   - **Level 1 (Git Integration)**: Target commit is an ancestor of `HEAD`.
   - **Level 2 (Mechanical Validation)**: No leftover conflict markers (`<<<<<<<`), project builds, and automated tests pass.
   - **Level 3 (Semantic Review)**: Incoming interface/assumption changes make sense with current code and do not silently break caller assumptions.
5. **Conservative With Destructive Operations**: Never force-push shared branches, overwrite tests merely to pass, or guess when resolving ambiguous conflicts. Stop and ask the human (and publish a `blocker` event) when uncertain.

---

## 2. Human Shorthand Command Procedures (`04` & `05`)

When the human types one of the seven shorthand commands, execute the exact procedure below using `python groupctl.py` (or `./groupctl` / `groupctl.cmd`).

### `SYNC`
Bring the local working context up to date with the group:
1. Run:
   ```bash
   python groupctl.py --json sync
   ```
2. Inspect the JSON output:
   - Check `post_sync.canonical_incorporation` to see if `main` was cleanly merged or deferred due to uncommitted work.
   - Read `new_events` (`change_published`, `review`, `test_result`, `integration_result`, `blocker`).
   - Read `separate_unintegrated_changes` (remember: `SYNC` never blindly merges unrelated feature branches).
   - Check `assumption_and_interface_warnings`.
3. If `SYNC` merged new commits from `main`, verify `validation_after_sync`.
4. Report to the human: what changed in the group, what was incorporated from `main`, what feature branches remain separate, and whether any `interface_changes` invalidate current assumptions.

---

### `PUB`
Publish completed, coherent local work on a personal branch (`people/<person_id>/<topic>`):
1. Verify you are on `people/<person_id>/<topic>` (if not, run `python groupctl.py branch <topic>`).
2. Inspect `git status` and `git diff` to identify all modified files and any **interface or assumption changes** (function signatures, return types, data models, file formats).
3. Run:
   ```bash
   python groupctl.py --json pub \
     --summary "<concise engineering summary>" \
     --interface-change "<interface/assumption change if any>"
   ```
   *(Note: `groupctl pub` automatically checks for accidental secrets/junk/conflict markers, runs automated tests, commits, creates a unique `change_id` such as `C-17`, writes `.group/events/E-...json`, and pushes to `origin`.)*
4. Report the published `change_id`, `event_id`, branch, and commit hash to the human.

---

### `INT <change_id>`
Integrate a specific published change (e.g., `INT C-17`) into the current working branch and verify all three levels:
1. **Prepare & Merge (Steps 1–8)**:
   ```bash
   python groupctl.py --json int prepare <change_id>
   ```
2. **Inspect Diff & Semantic Assumptions**:
   - Read `actual_diff` and `interface_changes` from the output.
   - Check whether the incoming change alters APIs or data structures used by the current branch.
3. **Handle Conflicts (if `status == "conflicts_detected"`)**:
   - Inspect each file in `conflicts`.
   - Read both sides (`HEAD` vs incoming commit) and determine both authors' intent.
   - **If the combined intent is clear**: edit the conflicting files to preserve both intended behaviors and remove all conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`).
   - **If the conflict is ambiguous or architectural**: DO NOT guess. Run:
     ```bash
     python groupctl.py --json int abort <change_id> \
       --reason "<why conflict cannot be safely resolved>" \
       --requested-action "<decision needed from human>"
     ```
     and ask the human.
4. **Adapt Call Sites for Semantic Compatibility (Level 3)**:
   - Even if Git merged cleanly without textual conflicts, if `interface_changes` or `actual_diff` invalidated assumptions in current files, update the affected call sites now.
5. **Verify & Publish Integration Result (Steps 9–15)**:
   ```bash
   python groupctl.py --json int finish <change_id> \
     --summary "Integrated <change_id> and verified build, tests, and semantic compatibility." \
     --conflict-file "<file_if_any>" \
     --resolution-summary "<how conflict or semantic adaptation was handled>" \
     --semantic-review pass
   ```
6. Report the Level 1 (Git ancestry), Level 2 (build/tests), and Level 3 (semantic review) results to the human.

---

### `REV <change_id>`
Review a teammate's published change without merging it into your branch:
1. Inspect the published event and actual Git diff:
   ```bash
   python groupctl.py --json inspect <change_id>
   ```
2. Examine `actual_diff`, surrounding source code, `interface_changes`, and test coverage.
3. Separate definite defects, plausible risks, and subjective preferences. Choose one verdict:
   - `accept`
   - `accept_with_changes`
   - `reject`
   - `needs_more_evidence`
4. Publish the review event:
   ```bash
   python groupctl.py --json rev <change_id> \
     --verdict <verdict> \
     --summary "<review summary>" \
     --issue "<specific defect or risk if any>" \
     --run-tests
   ```
5. Report the review findings and verdict to the human. Do NOT merge the change merely because the review is positive.

---

### `TEST [scope]`
Test the software (`current_branch` by default, `main`, or `<change_id>`) and publish evidence:
1. Run:
   ```bash
   python groupctl.py --json test [scope] \
     --human-check "<concrete step-by-step human check if UI/interactive behavior applies>"
   ```
2. If any test fails, inspect `.group/local/logs/test_<commit>.log` to distinguish product-code defects, outdated tests, or environment issues. Never silently rewrite expected outputs just to make tests pass.
3. Report what passed, what failed, and any concrete human checks required.

---

### `STATUS`
Report where current work stands relative to the group:
1. Run:
   ```bash
   python groupctl.py --json status
   ```
2. Present a clear summary covering: identity (`person_id`, `group_id`), current branch & commit, uncommitted changes, ahead/behind relative to `main`, new events since last sync, unincorporated published changes, latest test result, active blockers, and the recommended next action.

---

### `FINAL`
Finalize the group assignment on the canonical branch (`main`):
1. **Stage 1 — Prepare Candidate (Steps 1–10)**:
   ```bash
   python groupctl.py --json final prepare \
     --summary "<summary of what the group produced>" \
     --limitation "<known limitation if any>"
   ```
2. Read `.group/final/candidate.md` and show it to the initiating human. Highlight any unincorporated published changes, test evidence, and known limitations.
3. **Stage 2 — Confirm Finalization (Steps 11–13, ONLY after human approval)**:
   ```bash
   python groupctl.py --json final confirm \
     --summary "<summary of what the group produced>" \
     --limitation "<known limitation if any>"
   ```
4. Report the final canonical commit, `.group/final/final_report.md`, `.group/final/final.json`, and the published `final_result` event ID.
