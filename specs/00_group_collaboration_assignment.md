# Group Collaboration Software Assignment
Version 0.1

## 1. Assignment

Build the first working layer of a future multi-agent programming system:

> Several human + AI pairs must be able to work together as one group on one programming assignment, using a shared GitHub repository, without requiring a Dispatcher.

The group already has an assignment. The problem in this assignment is not to decide which group receives which job. The problem is to make one group able to work together effectively.

A typical group contains two or more students. Each student works with a local AI coding agent such as Codex or Gemini. The students may talk to each other directly. Their AI agents must also be able to exchange useful engineering information indirectly through the shared repository and standardized collaboration records.

```text
                    GROUP ASSIGNMENT
                           |
                  shared GitHub repository
                           |
        +------------------+------------------+
        |                  |                  |
   Student A          Student B          Student C
      <->                <->                <->
   local AI           local AI           local AI
        |                  |                  |
        +--------- publish / review / --------+
                   integrate / test
                           |
                    accepted group state
                           |
                    ONE GROUP RESULT
```

## 2. Core Principle

Git provides source control and history.

The collaboration software adds a small layer above Git so that humans and AI agents can perform standard group operations reliably and consistently.

The AI should not improvise the meaning of routine collaboration operations every time. The project therefore defines a small human-facing command vocabulary:

```text
SYNC
PUB
INT
REV
TEST
STATUS
FINAL
```

Each command has a precise procedure.

The student should be able to tell an agent simply:

```text
SYNC
```

instead of repeatedly typing a paragraph explaining how to fetch, inspect, update, and assess group changes.

The command is prompt shorthand. Underneath it, the agent uses Git, GitHub, tests, and the collaboration software.

## 3. What Must Be Built

The implementation should provide:

1. A local collaboration tool, referred to in these documents as `groupctl`.
2. A portable agent instruction/skill file that teaches an AI agent the collaboration commands and when to use `groupctl`.
3. A shared repository convention that allows group members and agents to publish changes, findings, reviews, test evidence, and integration results without relying on private chat history.
4. A structured event/change format so that agents can reliably discover what other group members have done.
5. A safe Git workflow based on individual work branches and a canonical group branch.
6. Testing and verification behavior that goes beyond merely asking Git whether a merge succeeded.
7. A group finalization procedure that turns the accumulated group work into one final group result.

## 4. Important Scope Limits

Version 0.1 does NOT need:

- a Dispatcher;
- automatic task allocation among groups;
- OpenAI API integration;
- Gemini API integration;
- a server other than GitHub;
- autonomous project planning;
- sophisticated GUI automation;
- automatic grading;
- a custom network protocol.

The local AI coding agent may be operated normally by the student.

The collaboration software should be AI-vendor-neutral. It should work conceptually with Codex, Gemini, or another agent that can use Git and local command-line tools.

## 5. Expected Working Model

Each group uses one shared GitHub repository.

Each person has:

```text
person_id
group_id
local clone/worktree
personal work branch
local AI agent
```

The repository contains the project code, tests, the group assignment, structured collaboration events, change records, and finalization records.

Each person normally develops on a personal branch.

The canonical accepted group state lives on:

```text
main
```

or another configured canonical branch.

A completed local feature is not silently treated as accepted group work. It is first published as a change, reviewed/tested as appropriate, and then integrated.

## 6. Human Role

Humans remain active participants.

Students may say to each other:

> You work on the parser. I will work on the renderer.

They may then steer their individual AI agents separately.

A human may interrupt their agent with a collaboration command when the outside situation has changed:

```text
SYNC
INT C-17
TEST
REV C-22
```

The software and agent instructions should make these commands reliable and low-effort.

## 7. Success Demonstration

A successful Version 0.1 demonstration should show at least:

1. Three simulated or real people use the same GitHub repository.
2. Each person has a separate work branch.
3. Two people independently implement different changes.
4. Person A publishes a completed change using `PUB`.
5. Person B runs `SYNC` and discovers A's published change.
6. Person B integrates or reviews A's change using `INT` or `REV`.
7. Git automatically merges one case successfully.
8. The system verifies that "Git merged" is not treated as sufficient: build/tests/semantic checks are also performed.
9. A deliberately conflicting change produces a Git conflict.
10. An AI agent is guided through resolving the conflict, followed by verification.
11. A group member runs `TEST` against the combined software.
12. Test results are published so all group members can see them.
13. The group reaches an accepted canonical state.
14. Any recognized group member can initiate `FINAL`.
15. `FINAL` produces one group result based on the accumulated accepted code, change history, reviews, and test evidence.

## 8. Required Companion Specifications

Implement this assignment according to:

```text
01_architecture_and_workflow.md
02_repository_contract.md
03_event_format_contract.md
04_command_reference.md
05_command_procedures.md
06_agent_behavior_specification.md
07_testing_and_finalization.md
```

Where these documents specify exact formats or behavior, follow them rather than silently inventing incompatible alternatives.
