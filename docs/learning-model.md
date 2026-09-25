# Learner model, scheduler, and drill composer (MVP)

All three are deterministic and documented here; constants live in code next to their tests.

## Evidence

Every signal is an append-only `capability_evidence` row keyed by a dedupe key (so duplicate
delivery is idempotent): score 0–1, confidence 0–1, hint level, exercise type, and flags
`assisted` (after viewing a solution), `transfer` (unseen related problem), `repeat_exposure`
(problem seen before), `excluded` (learner flagged the diagnosis). Aggregates in
`learner_capability_states` are always recomputed from evidence (`POST /v1/learner/rebuild`
replays everything).

Interview evidence per capability: base score 1.0 if hidden tests passed, else 0.6 × hidden pass
ratio; complexity uses the deterministic complexity check; weaknesses cap the score (high 0.2,
medium 0.45, low 0.7); independence = 1 − 0.18 × max hint level (0.1 after solution viewing).

## Update policy (`app/learning/model.py`)

- Start at `PRIOR_MASTERY` 0.3. For each evidence item in time order:
  `effective = score × (1 − hint_penalty[level])`, capped at 0.5 if assisted.
  `weight = confidence × (0.5 + 0.5 × difficulty[type])`, × 0.5 for repeat exposure, × 1.25 for
  independent transfer, × up to 1.5 for long gaps.
  `mastery += clamp(0.4 × weight × (effective − mastery), −0.25, +0.25)`.
- Interval (stability): first success 1–2 days; later successes grow by `1.8 + 0.7 × score`,
  scaled by how much of the interval elapsed (massed practice earns little) and capped at 1.2×
  for repeat exposure; partial success grows 1.2×; failure resets to 1 day (low-confidence
  failures shrink by 0.6× instead). Max 60 days.
- Bands: Weak < 0.35 ≤ Developing < 0.6 ≤ Reliable < 0.8 ≤ Strong. **Strong** additionally needs
  ≥ 3 evidence items including an independent (≤ level-1 hint, unassisted) interview,
  implementation, or transfer success; transfer capabilities need an independent transfer success.
  Transfer evidence that is entirely assisted never exceeds Developing.
- Explanations summarize the last three items ("2 recent misses in debugging with a level-2
  hint"); no decimals are shown to learners.

`docs/human-gates/gate-6-histories.md` traces five synthetic histories step by step.

## Scheduler (`app/scheduling/scheduler.py`)

Weaknesses are grouped per topic. The most severe weakness's template sets the spacing; other
weaknesses add step types it lacks (max 6 steps). Templates (days):

| Capability type | High | Medium | Low |
| --- | --- | --- | --- |
| recognition | 1 recognition, 3 explain, 7 implementation, 14 transfer, 30 re-interview | 1, 4 explain, 10 transfer | 3 recall, 10 transfer |
| reasoning (invariant) | 1 explain, 3 trace, 7 implementation, 14 transfer, 30 re-interview | 1 explain, 4 trace, 10 transfer | 3 explain, 12 transfer |
| implementation | 1 trace, 3 debug, 7 implementation, 14 transfer, 30 re-interview | 2 debug, 5 implementation, 12 transfer | 4 debug, 14 transfer |
| debugging (boundaries) | 1 debug, 3 trace, 7 implementation, 14 transfer | 2 debug, 6 implementation, 14 transfer | 4 debug |
| complexity | 1 explain, 4 recall, 10 transfer | 2 explain, 8 recall | 5 recall |
| transfer | 3 explain, 10 transfer, 30 re-interview | 5 explain, 14 transfer | 14 transfer |
| independence | 7 implementation, 21 re-interview | 14 re-interview | — |

Tasks become due at 04:00 in the learner's time zone (DST-safe). A daily cap (default 12) pushes
overflow to the next day. One active task per `(capability, task type)` (transfer and
re-interview are one per capability) enforced by a partial unique index. Failed reviews (< 0.5)
get one next-day Rebuild retry (max 3 attempts). Low-confidence interpretive weaknesses
(< 0.3) never schedule work; fact-derived ones always do. Communication/clarification/testing
are practiced in every interview and do not create tasks.

Viewing a solution schedules: key insight now, pseudocode +1 day, implementation +3, related
problem +10, unseen transfer interview +21.

## Drill composer (`app/drills/composer.py`)

Priority: due tasks `10 + 2 × overdue days (≤ 14) + 4 × (1 − mastery)`; weak-skill practice
`5 + 4 × (1 − mastery)`; calibration items for brand-new learners. Tie-break by due date then id.
Constraints: total ≤ budget, one item per capability (except retries), ≤ 2 per topic, ≤ 1 code
item (2 if budget ≥ 25), no exercise twice, no re-interviews. Items are ordered light → heavy
with topics interleaved.
