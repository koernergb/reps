# AI-Native Technical Learning + Interview Coach
## Downloadable Build Brief — v2

### Product thesis

Build an AI-native technical learning system that combines:

1. **Adaptive spaced repetition**
2. **Concept-level learner modeling**
3. **AI-generated drills**
4. **LeetCode-style coding practice**
5. **Conversational AI technical interviewing**
6. **Structured diagnosis that feeds future review scheduling**

The product should not feel like “Anki with an LLM” or “LeetCode with a chatbot.”

The core idea is:

> **Schedule capabilities, not cards.**

The system should learn what a user can recall, explain, implement, and solve independently. It then chooses the next training interaction based on observed weaknesses.

The long-term loop is:

**Learn → Retrieve → Drill → Interview → Diagnose → Schedule → Transfer-test**

A failed interview is not merely a bad score. It is structured evidence about what the learner should practice next.

---

# 1. Product Goals

## Primary goal

Create a technical learning coach that can determine:

- what the learner knows,
- what they only recognize,
- what they can explain,
- what they can implement,
- what they can solve under interview conditions,
- what they forget after time,
- what kinds of hints they require,
- and whether they can transfer knowledge to unseen problems.

## MVP wedge

The first compelling product should be:

> **An AI coding interview coach that remembers exactly how the learner struggles and schedules targeted follow-up exercises until they can solve related unseen problems independently.**

This is narrower and easier to validate than building a full universal learning platform first.

---

# 2. Target User

Initial target user:

- CS student or early-career engineer
- preparing for technical interviews
- uses LeetCode / NeetCode
- watches solutions but has trouble retaining them
- repeatedly “understands” problems without being able to reproduce them later
- wants to improve reasoning and verbal explanation, not just memorize answers

Secondary expansion:

- university CS coursework
- algorithms/data structures
- systems
- networking
- ML / CV / robotics
- technical certification material

---

# 3. Core Product Surfaces

The product should ultimately have three primary surfaces:

## Learn

Used for:

- notes
- lecture material
- explanations
- uploaded content
- concept discovery
- generated candidate questions

## Drill

Used for:

- short spaced-repetition sessions
- recall prompts
- recognition questions
- implementation fragments
- debugging exercises
- previously failed questions
- targeted transfer problems

## Interview

Used for:

- realistic technical interviews
- full coding problems
- conversation with an AI interviewer
- test execution
- complexity discussion
- follow-up questions
- final structured evaluation

All three surfaces write into the same learner model.

---

# 4. Learning Model

Avoid treating a flashcard as the fundamental unit.

The fundamental unit should be a **capability**.

Example capability tree:

```text
Sliding Window
├── Recognition
├── Window invariant
├── Pointer movement reasoning
├── Frequency tracking
├── Boundary handling
├── Complexity analysis
├── Implementation
├── Verbal explanation
└── Transfer to unseen problems
```

The learner model should estimate mastery independently across these dimensions.

Example state:

```text
sliding_window.recognition            0.84
sliding_window.invariant              0.52
sliding_window.pointer_updates        0.65
sliding_window.complexity             0.90
sliding_window.implementation         0.68
sliding_window.interview_independence 0.39
```

Do not expose fake precision to users initially.

Internally these estimates can be continuous while the UI uses:

- Weak
- Developing
- Reliable
- Strong

---

# 5. Exercise Hierarchy

A capability can be tested through multiple exercise types.

Suggested progression:

## Level 1 — Recall

Example:

> What conditions usually suggest a sliding-window approach?

Expected duration:
15–45 seconds.

## Level 2 — Recognition

Present a problem and ask:

> What algorithmic pattern would you consider first, and why?

## Level 3 — Explain

Example:

> Why is the window allowed to move its left boundary forward without reconsidering earlier positions?

## Level 4 — Trace

Give data and ask the user to trace:

- pointers,
- queue,
- stack,
- hash map,
- DP state,
- recursion,
- graph traversal.

## Level 5 — Code fragment

Examples:

- fill in pointer update,
- implement helper,
- repair bug,
- finish loop,
- write recurrence.

## Level 6 — Full implementation

User writes a solution from scratch.

## Level 7 — Interview

User receives an unseen or semi-unseen problem and must:

- clarify,
- reason,
- choose an approach,
- explain,
- implement,
- test,
- analyze complexity.

## Level 8 — Transfer

Present a structurally related problem with different surface details.

The scheduler should progressively move users upward.

Repeated success at definition recall should not cause endless definition recall.

---

# 6. Review Loop

Each review attempt should produce structured evidence.

Example flow:

```text
Prompt
↓
User answer
↓
Deterministic checks if available
↓
LLM semantic evaluation
↓
Misconception extraction
↓
Hint usage analysis
↓
Mastery update
↓
Next interval + next exercise-type decision
```

The user should be able to answer naturally.

The system should evaluate:

- correctness,
- completeness,
- misconceptions,
- confidence,
- hints required,
- independence,
- whether the answer appears memorized but shallow.

---

# 7. Three Review Depths

## Retrieve

Fast interaction.

Target:
15–45 seconds.

Example:

> Why is binary search O(log n)?

User answers.

AI returns concise feedback and schedules the concept.

---

## Coach

Used when the learner is stuck.

The AI should not immediately reveal the answer.

Hint ladder:

1. directional cue,
2. conceptual cue,
3. partial structure,
4. near-answer,
5. full explanation.

The number and strength of hints must become learner-model evidence.

Example:

```text
event: hint_requested
hint_level: 2
capability: sliding_window.invariant
```

---

## Rebuild

Triggered when an answer indicates the mental model itself is wrong.

The system temporarily stops pure retrieval.

Sequence:

1. identify misconception,
2. explain the missing concept,
3. ask a smaller diagnostic question,
4. confirm understanding,
5. create a future targeted retrieval task.

---

# 8. Coding Interview Mode

## UI layout

Desktop-first:

```text
┌───────────────────────────┬──────────────────────────┐
│                           │                          │
│ Problem statement         │ AI interviewer           │
│                           │                          │
├───────────────────────────┤                          │
│                           │                          │
│ Code editor               │ Conversation             │
│                           │                          │
│                           │                          │
├───────────────────────────┤                          │
│ Tests / output            │                          │
└───────────────────────────┴──────────────────────────┘
```

Allow resizing panes.

---

# 9. Interviewer Behavior

The AI interviewer should behave under a strict policy.

It should:

- ask the learner to clarify assumptions,
- ask for initial thoughts,
- avoid giving unsolicited solutions,
- answer reasonable clarification questions,
- challenge suspicious reasoning,
- ask about complexity,
- allow silence / working time,
- provide hints only according to interview mode,
- ask follow-up questions after completion,
- evaluate communication separately from code correctness.

Example:

```text
AI:
Before you code, walk me through the approach you're considering.

USER:
I think I can use a hash map...

AI:
What information would the map store?
```

Later:

```text
AI:
What's the time and space complexity?

AI:
If the input were already sorted, could you do better on space?
```

---

# 10. Interview Modes

## Practice Mode

Generous coaching.

Allowed:

- hints,
- conceptual explanations,
- discussion,
- debugging help,
- pausing to learn.

Goal:
skill acquisition.

---

## Mock Interview

Realistic constraints.

The interviewer:

- does not volunteer help,
- gives minimal clarification,
- may provide small nudges only when appropriate,
- waits while user works,
- scores independence strongly.

Goal:
simulation.

---

## Adaptive Drill

5–15 minute sessions generated from learner weaknesses.

Example session:

```text
12-minute adaptive drill

1. Sliding-window recognition
2. Fix a pointer-update bug
3. Re-implement a previously failed helper
4. Solve a short transfer problem
```

This should become the default daily-use mode.

---

# 11. Voice Strategy

Voice is **not required for MVP**.

Architecture should be voice-ready but modality-independent.

## Phase 1

Text chat only.

Capture:

- user reasoning typed into interviewer,
- code edits,
- tests,
- hints,
- timing,
- interview outcomes.

## Phase 2

Add push-to-talk speech input.

Speech is transcribed.

AI may continue responding primarily in text.

Benefits:

- lets users practice thinking aloud,
- provides verbal reasoning data,
- avoids the latency complexity of fully realtime conversation.

## Phase 3

Realtime voice interviewer.

Capabilities:

- natural turn-taking,
- interruptions,
- follow-up questions,
- latency-sensitive responses,
- realistic mock-interview behavior.

Voice should primarily enhance **Mock Interview Mode**.

It should never be required for the product's core learning loop.

---

# 12. Interview Event Model

Do not store an interview as a giant chat transcript only.

Every meaningful action should generate structured events.

Example:

```json
{
  "type": "reasoning_statement",
  "timestamp": 1724104321,
  "capability_ids": ["sliding_window.invariant"],
  "content": "I think the window should..."
}
```

Other event types:

```text
interview_started
problem_opened
clarification_asked
reasoning_statement
approach_proposed
approach_changed
code_edit
run_tests
test_failure
test_success
hint_requested
hint_given
complexity_answer
followup_answer
solution_submitted
interview_completed
```

This makes replay, analytics, evaluation, and future voice support much easier.

---

# 13. Code Evaluation

Do not let an LLM decide whether code works.

Use two evaluation layers.

## Deterministic execution

Responsible for:

- compilation,
- execution,
- visible tests,
- hidden tests,
- timeout,
- runtime errors,
- memory limits.

## LLM evaluation

Responsible for:

- reasoning quality,
- algorithm choice,
- explanation quality,
- misconception detection,
- hint independence,
- communication,
- complexity reasoning,
- whether the learner understands why the solution works.

---

# 14. Post-Interview Diagnosis

The system should generate structured output such as:

```json
{
  "problem_id": "longest-substring",
  "result": "completed_with_hints",
  "strengths": [
    "Correct complexity analysis",
    "Good hashmap implementation"
  ],
  "weaknesses": [
    {
      "capability": "sliding_window.recognition",
      "severity": "medium"
    },
    {
      "capability": "sliding_window.invariant",
      "severity": "high"
    },
    {
      "capability": "pointer_updates",
      "severity": "medium"
    }
  ],
  "hints_used": 2,
  "transfer_confidence": "low"
}
```

This diagnosis drives scheduling.

---

# 15. The Critical Feedback Loop

Example learner attempt:

The user fails:

**Longest Substring Without Repeating Characters**

Observed:

- failed to recognize sliding window,
- proposed brute force,
- moved to hashmap after hint,
- misunderstood window invariant,
- implemented final solution correctly,
- explained complexity correctly.

The system schedules:

### Tomorrow

Short conceptual review:

> What must remain true about the current window in a longest-unique-substring algorithm?

### 3 days

Debugging exercise:

> Find the pointer-update error.

### 7 days

Implementation:

> Reconstruct the algorithm from scratch.

### 14 days

Transfer problem:

> Solve Max Consecutive Ones III.

### Later

Unseen medium with related structure.

The system should explicitly distinguish:

> remembers this problem

from:

> understands this technique

from:

> transfers this technique independently.

---

# 16. Watched-Solution Workflow

Users frequently watch a solution after failing.

Do not mark that problem complete.

Instead:

```text
Failed attempt
↓
Solution viewed
↓
Immediate comprehension check
↓
Delayed reconstruction
↓
Delayed implementation
↓
Transfer problem
```

Suggested sequence:

## Immediately

> Explain the key insight without looking.

## Next day

> Reconstruct the approach in pseudocode.

## 3–4 days

> Implement from memory.

## 1–2 weeks

> Solve a related problem.

## Later

> Solve an unseen transfer problem.

This should be a major product differentiator.

---

# 17. Problem Corpus

Do not begin with unrestricted AI-generated interview problems.

Start with a curated corpus.

Suggested initial domains:

```text
Arrays
Hashing
Two pointers
Sliding window
Stack
Binary search
Linked lists
Trees
Heap / priority queue
Backtracking
Graphs
1-D DP
Intervals
Greedy
```

Initial problem count:

50–100 carefully selected problems.

For every problem store:

```text
difficulty
patterns
concepts
prerequisites
common mistakes
canonical complexity
test cases
follow-up questions
related problems
transfer group
```

---

# 18. AI-Generated Problems

Later feature.

Use AI for:

- micro-variations,
- debugging exercises,
- boundary-condition drills,
- trace questions,
- transfer problems.

Example:

If a user repeatedly makes endpoint mistakes:

> Generate a sliding-window problem where inclusive/exclusive boundaries are essential.

Generated problems must go through:

1. static validation,
2. reference-solution execution,
3. generated-test validation,
4. optionally human review for corpus promotion.

Do not trust an LLM-generated problem and answer blindly.

---

# 19. Course Material Ingestion

After the interview MVP is validated, expand into academic material.

Supported sources:

- pasted notes,
- markdown,
- PDFs,
- lecture slides,
- textbook excerpts,
- project specifications.

Pipeline:

```text
Material
↓
Chunk / parse
↓
Concept extraction
↓
Question generation
↓
Candidate inbox
↓
User approves / edits / rejects
↓
Learning items enter scheduler
```

Never dump hundreds of generated flashcards directly into the user's review queue.

---

# 20. Candidate Inbox

Generated material should appear as suggestions.

Each item:

```text
Question
Suggested answer
Source
Capability tags
Difficulty
Generation confidence
```

Actions:

- Approve
- Edit
- Reject
- Merge
- Change concept
- Generate alternative

Provenance should be preserved.

---

# 21. Spaced-Repetition Scheduler

Do not build a novel scheduler initially.

Use an established model such as FSRS or an FSRS-inspired implementation.

However, expand the scheduler's inputs beyond pass/fail.

Possible signals:

```text
correctness
response latency
hint count
hint strength
confidence
exercise difficulty
exercise type
transfer distance
time since last exposure
interview independence
```

The scheduler should separately reason about:

```text
memory strength
conceptual understanding
implementation fluency
transfer ability
```

For the MVP, simplify this into a manageable mastery score + review interval.

---

# 22. Suggested Data Model

## User

```text
id
email
created_at
```

## Topic

```text
id
name
parent_topic_id
```

## Capability

```text
id
topic_id
name
description
capability_type
```

Example capability types:

```text
recall
recognition
reasoning
implementation
debugging
communication
transfer
```

## Problem

```text
id
slug
title
statement
difficulty
reference_solution
time_complexity
space_complexity
```

## ProblemCapability

```text
problem_id
capability_id
weight
```

## Exercise

```text
id
exercise_type
capability_id
problem_id
prompt
expected_answer
source_type
source_id
```

## ReviewAttempt

```text
id
user_id
exercise_id
started_at
completed_at
answer
correctness
confidence
hints_used
evaluation_json
```

## LearnerCapabilityState

```text
user_id
capability_id
mastery
stability
difficulty
last_reviewed_at
next_review_at
```

## InterviewSession

```text
id
user_id
problem_id
mode
started_at
completed_at
result
evaluation_json
```

## InterviewEvent

```text
id
session_id
event_type
timestamp
payload_json
```

## HintLog

```text
id
user_id
session_id
exercise_id
hint_level
hint_text
timestamp
```

---

# 23. Architecture

Recommended MVP stack:

## Frontend

Next.js

Use:

- TypeScript
- React
- Tailwind
- shadcn/ui
- Monaco Editor

## Backend

FastAPI

Use:

- Python
- Pydantic
- SQLAlchemy
- Alembic

## Database

PostgreSQL

## Queue

Initially optional.

Later:

- Redis
- Celery / Dramatiq / Arq

for:

- ingestion,
- document parsing,
- bulk question generation,
- long evaluations.

## Code sandbox

Use isolated containers.

Possible architecture:

```text
API
↓
execution service
↓
ephemeral sandbox
↓
compile/run
↓
results
```

Never execute arbitrary learner code inside the main API process.

---

# 24. LLM Service Boundaries

Create explicit backend services instead of scattering prompts throughout routes.

Suggested modules:

```text
llm/
├── interviewer.py
├── grader.py
├── misconception_detector.py
├── hint_generator.py
├── explanation_generator.py
├── question_generator.py
└── post_interview_evaluator.py
```

All LLM outputs used by product logic should return structured schemas.

Example:

```python
class AnswerEvaluation(BaseModel):
    correctness: float
    missing_points: list[str]
    misconceptions: list[str]
    capability_updates: list[CapabilityUpdate]
    recommended_action: Literal[
        "advance",
        "review",
        "coach",
        "rebuild"
    ]
```

Avoid parsing prose when structured output can be used.

---

# 25. Interviewer State Machine

Do not rely on the language model to implicitly manage the whole interview.

Use an application-level state machine.

Example:

```text
INTRO
↓
CLARIFICATION
↓
APPROACH_DISCUSSION
↓
IMPLEMENTATION
↓
TESTING
↓
COMPLEXITY
↓
FOLLOW_UP
↓
COMPLETE
```

State influences the interviewer prompt.

Example:

During `IMPLEMENTATION`:

- avoid asking unnecessary conceptual questions,
- respond to direct questions,
- only intervene according to mode.

During `COMPLEXITY`:

- explicitly ask time and space complexity.

This gives far more consistent behavior.

---

# 26. Prompt Architecture

The interviewer system prompt should define:

## Role

You are a technical interviewer.

## Goals

Assess:

- problem solving,
- algorithmic reasoning,
- code correctness,
- communication,
- independence.

## Forbidden behavior

Do not:

- give away the solution prematurely,
- dump code,
- reveal hidden tests,
- provide hints unless policy permits,
- falsely claim execution results.

## Context

The interviewer receives:

```text
problem
mode
current interview state
conversation events
current code
test results
known learner weaknesses
hint budget
```

Known weaknesses may influence follow-ups but should not make the interviewer artificially lead the user toward the answer.

---

# 27. MVP User Journey

## Onboarding

User chooses:

```text
Interview prep
Course learning
Both
```

For V0, emphasize interview prep.

User chooses language:

```text
Python
Java
C++
JavaScript / TypeScript
```

---

## Dashboard

Show:

```text
Today's training
Weak patterns
Upcoming reviews
Recent interviews
Mastery trends
```

Primary button:

> Start 10-minute drill

Secondary:

> Start mock interview

---

## Drill session

Example:

```text
Card 1:
Explain BFS vs DFS.

Card 2:
Which approach fits this problem?

Card 3:
Fix this DFS visited-state bug.

Card 4:
Implement this tree helper.
```

---

## Interview session

1. problem shown,
2. interviewer asks for initial reasoning,
3. user reasons,
4. user codes,
5. tests run,
6. interviewer asks follow-ups,
7. evaluation generated,
8. weaknesses added to scheduler.

---

# 28. MVP Scope

## Build

### Authentication

- email/social login
- user profile

### Curated problem set

Start with ~50 problems.

### Monaco editor

Support one language initially if necessary.

Python is the simplest starting language.

### Safe execution

- run visible tests
- run hidden tests
- timeout protection

### Text AI interviewer

- interview state machine
- Practice Mode
- Mock Interview Mode

### Evaluation

- deterministic correctness
- structured LLM evaluation

### Learner state

- capability mastery
- weaknesses
- history

### Adaptive scheduler

- daily review queue
- targeted re-test

### Post-interview report

- strengths
- weaknesses
- hints
- next training items

### Adaptive Drill Mode

Generate 5–15 minute sessions.

---

# 29. Explicitly Exclude From MVP

Do not initially build:

- realtime voice,
- mobile apps,
- social features,
- full Anki compatibility,
- hundreds of subjects,
- giant knowledge graph,
- AI-generated full problem corpus,
- competitive leaderboards,
- live human interview matching,
- sophisticated Bayesian learner modeling,
- browser extensions,
- IDE plugins.

These are distractions until the core loop is proven.

---

# 30. MVP Success Criteria

The MVP is successful if users repeatedly experience:

> “It remembered exactly what I was bad at and made me practice it again at the right time.”

Quantitative metrics:

## Engagement

- >= 40% week-2 retention among activated users
- >= 3 training sessions / week for engaged users
- >= 30% of interview users return for a scheduled re-test

## Learning

Measure:

```text
initial failure
→ delayed reconstruction
→ delayed transfer
```

Key metric:

**Transfer success after remediation**

Not merely:

**Number of problems solved**

## Interview independence

Track reduction in:

- hints per problem,
- time to identify pattern,
- time to first viable approach,
- implementation errors.

---

# 31. Development Milestones

## Milestone 0 — Foundation

Build:

- monorepo,
- auth,
- PostgreSQL,
- capability schema,
- problem schema,
- basic frontend.

Acceptance:

User can log in and view a problem.

---

## Milestone 1 — Coding environment

Build:

- Monaco editor,
- Python execution,
- visible tests,
- hidden tests,
- execution API.

Acceptance:

User can write and execute a solution safely.

---

## Milestone 2 — AI interviewer

Build:

- text interviewer panel,
- interview state machine,
- event logging,
- Practice Mode.

Acceptance:

AI conducts an entire interview without prematurely revealing the solution.

---

## Milestone 3 — Evaluation

Build:

- deterministic test scoring,
- structured LLM evaluation,
- capability weakness extraction,
- post-interview report.

Acceptance:

Completed interviews generate reliable structured diagnoses.

---

## Milestone 4 — Learner model

Build:

- capability state,
- mastery updates,
- attempt history,
- weak-capability dashboard.

Acceptance:

System can identify a learner's persistent weaknesses across multiple problems.

---

## Milestone 5 — Spaced remediation

Build:

- review scheduler,
- conceptual questions,
- code fragments,
- previously failed exercises,
- scheduled re-tests.

Acceptance:

A failed interview automatically produces future targeted learning tasks.

---

## Milestone 6 — Adaptive Drill

Build:

- session composer,
- time-budgeted drills,
- exercise diversity,
- progression.

Acceptance:

System can generate a useful 10-minute training session from learner history.

---

## Milestone 7 — Mock interviews

Build:

- stricter interviewer policy,
- timing,
- realistic hint constraints,
- interview scorecard.

Acceptance:

Mock mode meaningfully feels different from coaching mode.

---

## Milestone 8 — Solution-watching remediation

Build:

- mark solution viewed,
- comprehension check,
- delayed reconstruction,
- transfer scheduling.

Acceptance:

Viewing a solution no longer counts as mastery.

---

# 32. Post-MVP Expansion

## Voice Phase 1

Push-to-talk.

Implement:

```text
microphone
↓
speech-to-text
↓
InterviewEvent(reasoning_statement)
↓
normal interviewer logic
```

Do not make the rest of the product depend on audio.

---

## Voice Phase 2

Realtime interviewer.

Add:

- streaming speech recognition,
- streaming TTS,
- turn detection,
- interruptions,
- latency optimization.

---

## Academic learning

Add:

- PDF ingestion,
- lecture notes,
- slides,
- candidate inbox,
- source provenance.

---

## Rich learner modeling

Potential techniques:

- FSRS
- Bayesian Knowledge Tracing
- Item Response Theory
- Deep Knowledge Tracing

Do not use these merely for sophistication.

Adopt only when there is enough learner interaction data to justify them.

---

# 33. Recommended Repository Layout

```text
ai-learning-coach/
├── apps/
│   ├── web/
│   │   ├── app/
│   │   ├── components/
│   │   ├── features/
│   │   │   ├── interview/
│   │   │   ├── editor/
│   │   │   ├── review/
│   │   │   ├── dashboard/
│   │   │   └── learner-model/
│   │   └── lib/
│   │
│   └── api/
│       ├── app/
│       │   ├── routes/
│       │   ├── models/
│       │   ├── schemas/
│       │   ├── services/
│       │   │   ├── scheduling/
│       │   │   ├── interviewing/
│       │   │   ├── evaluation/
│       │   │   └── execution/
│       │   ├── llm/
│       │   └── db/
│       └── tests/
│
├── packages/
│   ├── shared-types/
│   ├── problem-corpus/
│   └── prompts/
│
├── infra/
│   ├── docker/
│   └── sandbox/
│
├── scripts/
├── docs/
└── README.md
```

---

# 34. First 50 Problems

Do not select them solely by popularity.

Choose problems that provide coverage across capabilities.

Suggested distribution:

```text
Arrays / Hashing       8
Two Pointers           5
Sliding Window         5
Stack                   4
Binary Search           4
Linked List             4
Trees                    7
Heap                     3
Graphs                   5
1-D DP                   5
```

For each pattern include:

- easy recognition problem,
- canonical implementation problem,
- boundary-heavy problem,
- transfer problem.

---

# 35. Evaluation Harness

The AI interviewer itself needs testing.

Create scripted synthetic candidates.

Examples:

```text
candidate_perfect
candidate_needs_hint
candidate_wrong_complexity
candidate_memorized_solution
candidate_boundary_bug
candidate_silent_then_correct
candidate_bad_reasoning_correct_code
candidate_good_reasoning_buggy_code
```

Run these against interviewer versions.

Measure:

- solution leakage,
- unnecessary hints,
- missed misconceptions,
- evaluation consistency,
- interview-state correctness.

Keep a regression suite for prompts.

---

# 36. Privacy and Safety

Code and interview transcripts may contain personal information.

Requirements:

- clear data retention policy,
- delete interview history,
- export account data,
- do not train external models on user content without explicit permission,
- minimize source material included in prompts,
- isolate code execution.

---

# 37. Product Principle Checklist

When evaluating a feature, ask:

### Does this increase evidence about mastery?

If no, it may not belong.

### Does this reduce passive recognition?

Prefer active reconstruction.

### Does this encourage transfer?

Prefer unseen variation over repeated memorization.

### Does this improve scheduling?

Learning evidence should change future training.

### Does it require voice?

If yes, reconsider.

Voice should enhance realism, not underpin the learning architecture.

### Is the LLM doing something deterministic software should do?

If yes, move it out of the LLM.

---

# 38. Core Differentiator

The core differentiator is not:

> AI-generated flashcards.

It is not:

> AI technical interviews.

It is not:

> spaced repetition for LeetCode.

It is the closed loop:

```text
INTERVIEW
↓
OBSERVE FAILURE
↓
DECOMPOSE FAILURE INTO CAPABILITIES
↓
GENERATE TARGETED TRAINING
↓
SPACE RETRIEVAL
↓
TEST IMPLEMENTATION
↓
TEST TRANSFER
↓
RE-INTERVIEW
```

Every interaction should make the next interaction smarter.

---

# 39. North-Star User Experience

A learner fails a graph problem.

The app eventually learns:

```text
The learner:
- recognizes BFS vs DFS reliably,
- understands queues and recursion,
- often fails to define state correctly,
- forgets to mark visited at insertion time,
- explains complexity well,
- needs hints when graph state is implicit.
```

Three weeks later, the learner solves an unfamiliar graph problem cleanly without assistance.

The system can explain why:

```text
You previously struggled with visited-state semantics.

Since then you:
- completed 3 targeted traces,
- fixed 2 visited-state bugs,
- reimplemented BFS twice,
- solved 2 transfer problems,
- completed today's interview without hints.
```

That is the product.

---

# 40. Recommended Immediate Build Order

Start here:

```text
1. 25–50 curated problems
2. Monaco + Python execution
3. Text interviewer
4. Interview event stream
5. Deterministic tests
6. Structured post-interview evaluation
7. Capability taxonomy
8. Learner capability state
9. Scheduled remediation
10. Adaptive 10-minute drill
11. Mock Interview Mode
12. Only then consider voice
```

Do not start with PDF ingestion or realtime speech.

Prove the interview → diagnosis → remediation → transfer loop first.

---

## One-sentence pitch

> **An AI technical interview coach that remembers how you think, diagnoses exactly why you fail, and uses spaced repetition and targeted coding drills until you can solve unseen problems independently.**
