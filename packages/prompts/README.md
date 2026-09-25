# Prompts

Versioned prompt templates for every LLM task, rendered with `string.Template`:

| Task | File | Output schema |
| --- | --- | --- |
| Interviewer turn | `interviewer/v1.md` | `InterviewerTurn` (`app/interview/interviewer.py`) |
| Post-interview evaluation | `evaluator/v1.md` | `SemanticEvaluation` (`app/evaluation/schemas.py`) |
| Review answer grading | `grader/v1.md` | `AnswerGrade` (`app/reviews/grading.py`) |

Rules:

- Untrusted content (learner text, code, problem statement) is wrapped in XML-like fences and
  the prompt says to treat it as data.
- Prompts never contain hidden tests, reference solutions, or credentials. The evaluator
  receives deterministic execution facts, not test bodies.
- A prompt's identity is `<task>/<version>+<sha8>`; it is stored on every evaluation and LLM
  call audit row.
- Regression fixtures for the interviewer live in `fixtures/personas/`; run them with
  `pnpm --filter @reps/api personas`.
