# Authoring corpus content

## Problem lifecycle

1. **Author** a YAML file under `problems/<topic>/<slug>.yaml` following
   `apps/api/app/corpus/schema.py` (`ProblemDef`). Required: statement, examples,
   constraints, starter code, complexity, capability weights summing to 1.0, a five-level hint
   ladder, key insight, clarifications, follow-ups, common mistakes, visible tests, at least two
   hidden tests, a reference solution, and at least one known-wrong solution per important
   mistake.
2. **Test.** Every known-wrong solution declares how hidden tests must reject it
   (`wrong_answer`, `timeout`, or `error`). `pnpm corpus:validate` fails if the reference
   fails, outputs are non-deterministic, or any wrong solution survives hidden tests for its
   intended reason. Large performance inputs use trusted `args_expr` / `expected_expr`
   generators (restricted builtins; repository content only). Leave at least a 5x time
   margin between the expected complexity and the mistake you want to catch.
3. **Review (Human Gate 2).** An experienced interviewer reviews statement, clarifications,
   reference solution, complexity, hidden tests, capability mapping, and transfer relations,
   and a second person solves it blind. Record sign-off in `docs/human-gates/gate-2-review.md`
   and only then change `status` to `reviewed`.
4. **Version.** Any change to learner-visible text, tests, or evaluation bumps `version`.
   The seed updates rows whose version changed; stored attempts keep the version they used.
5. **Retire.** Set `status: retired` (or delete the file; the seed retires missing problems
   rather than deleting rows). Never reuse a retired slug.

## Rules

- No AI-generated full problems in the accepted corpus during the MVP.
- Public fields (statement, examples, constraints, starter code) must never contain reference
  solution lines; lint enforces this for lines of 24+ characters.
- Hints escalate: directional cue → conceptual cue → partial structure → near-answer → full
  explanation. Levels 3–5 must not appear in public content.
- Trees and linked lists use the harness adapters (`tree` = level order with `null`,
  `linked_list` = Python list). Avoid tests that only deep recursion can fail unless the
  constraints say so explicitly.
- Transfer groups link structurally related problems; a transfer item should share the
  technique but not the surface story.

## Exercises

Exercises (`exercises/<topic>.yaml`) target one capability. Text items need a rubric
(`key_points`, each a list of accepted phrasings) or exact `accepted_answers`. Code items
(`debug`, `code_fragment`) link a problem and reuse its tests; `from_mistake` seeds a debug
item with that problem's known-wrong solution. Explain items that target a misconception
should include `misconception` and a `confirmation_question` for the Rebuild flow.
