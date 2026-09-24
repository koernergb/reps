from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.corpus.loader import get_corpus
from app.evaluation.facts import derive_result
from app.evaluation.schemas import (
    Facts,
    SemanticClaim,
    SemanticEvaluation,
    SemanticWeakness,
    Weakness,
)
from app.evaluation.service import evaluate_session, merge_weaknesses, validate_semantic
from app.llm.provider import LLMResult, LLMUnavailable
from app.models import (
    CapabilityEvidence,
    InterviewEvaluation,
    InterviewEvent,
    InterviewSession,
    LLMCall,
)

PROBLEM = get_corpus().problem("pair-sum-indices")


def facts(**overrides: Any) -> Facts:
    base: dict[str, Any] = dict(
        result="solved_independently",
        passed_hidden=True,
        best_hidden_passed=5,
        hidden_total=5,
        visible_passed=2,
        visible_total=2,
        runs=1,
        submissions=1,
        first_submission_passed=True,
        hidden_failure_kinds=[],
        hints_used=0,
        max_hint_level=0,
        solution_viewed=False,
        clarifications_asked=1,
        learner_utterances=4,
        approach_before_code=True,
        complexity_time_correct=True,
        complexity_space_correct=True,
        duration_s=600,
        final_state="COMPLETE",
        mode="practice",
    )
    base.update(overrides)
    return Facts(**base)


def event(sequence: int, kind: str = "reasoning_statement") -> InterviewEvent:
    return InterviewEvent(
        id=f"event-{sequence}",
        session_id="s",
        sequence=sequence,
        event_type=kind,
        occurred_at=datetime.now(UTC),
        payload={"content": "x"},
        actor="learner",
    )


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        (
            {
                "final_state": "ABANDONED",
                "session_result": "abandoned",
                "passed_hidden": False,
                "submissions": 0,
                "max_hint_level": 0,
                "solution_viewed": False,
            },
            "abandoned",
        ),
        (
            {
                "final_state": "COMPLETE",
                "session_result": None,
                "passed_hidden": True,
                "submissions": 1,
                "max_hint_level": 0,
                "solution_viewed": False,
            },
            "solved_independently",
        ),
        (
            {
                "final_state": "COMPLETE",
                "session_result": None,
                "passed_hidden": True,
                "submissions": 1,
                "max_hint_level": 2,
                "solution_viewed": False,
            },
            "solved_with_minor_hints",
        ),
        (
            {
                "final_state": "COMPLETE",
                "session_result": None,
                "passed_hidden": True,
                "submissions": 1,
                "max_hint_level": 4,
                "solution_viewed": False,
            },
            "solved_with_major_hints",
        ),
        (
            {
                "final_state": "COMPLETE",
                "session_result": None,
                "passed_hidden": True,
                "submissions": 1,
                "max_hint_level": 0,
                "solution_viewed": True,
            },
            "solved_after_solution_view",
        ),
        (
            {
                "final_state": "COMPLETE",
                "session_result": "timed_out",
                "passed_hidden": False,
                "submissions": 1,
                "max_hint_level": 0,
                "solution_viewed": False,
            },
            "timed_out",
        ),
        (
            {
                "final_state": "COMPLETE",
                "session_result": None,
                "passed_hidden": False,
                "submissions": 2,
                "max_hint_level": 0,
                "solution_viewed": False,
            },
            "failed",
        ),
        (
            {
                "final_state": "COMPLETE",
                "session_result": None,
                "passed_hidden": False,
                "submissions": 0,
                "max_hint_level": 0,
                "solution_viewed": False,
            },
            "incomplete",
        ),
    ],
)
def test_result_is_deterministic_from_facts(kwargs: dict[str, Any], expected: str) -> None:
    assert derive_result(**kwargs) == expected


def test_validation_drops_unsupported_and_contradictory_claims() -> None:
    events = [event(1), event(2, "solution_submitted"), event(3, "complexity_answer")]
    semantic = SemanticEvaluation(
        strengths=[
            SemanticClaim(text="All tests passed on the first try.", evidence_sequences=[2]),
            SemanticClaim(text="Clear explanation.", evidence_sequences=[99]),
            SemanticClaim(text="Explained the invariant well.", evidence_sequences=[1]),
        ],
        weaknesses=[
            SemanticWeakness(
                capability="arrays-hashing.complexity",
                severity="medium",
                explanation="Unsure about space.",
                evidence_sequences=[3],
                confidence=0.6,
            ),
            SemanticWeakness(
                capability="graphs.recognition",
                severity="high",
                explanation="Wrong topic.",
                evidence_sequences=[1],
                confidence=0.9,
            ),
            SemanticWeakness(
                capability="arrays-hashing.recognition",
                severity="low",
                explanation="No evidence.",
                evidence_sequences=[],
                confidence=0.9,
            ),
        ],
        misconceptions=[SemanticClaim(text="Thinks maps are ordered.", evidence_sequences=[])],
        communication_rating=3,
        communication_summary="ok",
        reasoning_rating=3,
        reasoning_summary="ok",
        overall_confidence=0.7,
        transfer_confidence="medium",
    )
    strengths, weaknesses, misconceptions, issues = validate_semantic(
        semantic, facts(passed_hidden=False, result="failed"), events, PROBLEM
    )
    assert [claim.text for claim in strengths] == ["Explained the invariant well."]
    assert strengths[0].evidence_event_ids == ["event-1"]
    assert [item.capability for item in weaknesses] == ["arrays-hashing.complexity"]
    assert misconceptions == []
    assert sorted(set(issues)) == [
        "contradicts_execution",
        "unknown_capability",
        "unsupported_misconception",
        "unsupported_strength",
        "unsupported_weakness",
    ]


def test_merge_keeps_most_severe_and_unions_evidence() -> None:
    low = Weakness(
        capability="c.x",
        severity="low",
        explanation="a",
        evidence_event_ids=["1"],
        confidence=0.9,
        source="rules",
    )
    high = Weakness(
        capability="c.x",
        severity="high",
        explanation="b",
        evidence_event_ids=["2"],
        confidence=0.4,
        source="facts",
    )
    merged = merge_weaknesses([low], [high])
    assert len(merged) == 1
    assert merged[0].severity == "high" and merged[0].evidence_event_ids == ["1", "2"]
    assert merged[0].confidence == 0.9


def run_interview(
    client: TestClient, run_jobs: Any, problem: str, code: str, say: list[str]
) -> str:
    view = client.post("/v1/interviews", json={"problem_slug": problem}).json()
    for text in say:
        view = client.post(
            f"/v1/interviews/{view['id']}/messages",
            json={
                "content": text,
                "expected_version": view["version"],
                "idempotency_key": uuid4().hex,
            },
        ).json()
    if view["state"] != "IMPLEMENTATION":
        view = client.post(
            f"/v1/interviews/{view['id']}/advance",
            json={
                "target": "APPROACH_DISCUSSION"
                if view["state"] in ("INTRO", "CLARIFICATION")
                else "IMPLEMENTATION",
                "expected_version": view["version"],
                "idempotency_key": uuid4().hex,
            },
        ).json()
        if view["state"] != "IMPLEMENTATION":
            view = client.post(
                f"/v1/interviews/{view['id']}/advance",
                json={
                    "target": "IMPLEMENTATION",
                    "expected_version": view["version"],
                    "idempotency_key": uuid4().hex,
                },
            ).json()
    client.post(
        "/v1/executions",
        json={
            "problem_slug": problem,
            "code": code,
            "kind": "submit",
            "idempotency_key": uuid4().hex,
            "session_id": view["id"],
        },
    )
    run_jobs()
    view = client.get(f"/v1/interviews/{view['id']}").json()
    client.post(
        f"/v1/interviews/{view['id']}/advance",
        json={
            "target": "COMPLETE",
            "expected_version": view["version"],
            "idempotency_key": uuid4().hex,
        },
    )
    return str(view["id"])


def test_metamorphic_irrelevant_wording_keeps_diagnosis(client: TestClient, run_jobs: Any) -> None:
    wrong = get_corpus().problem("find-sorted-value").definition.wrong_solutions[0].code
    first = run_interview(
        client,
        run_jobs,
        "find-sorted-value",
        wrong,
        ["I will use binary search over the sorted list with two bounds."],
    )
    second = run_interview(
        client,
        run_jobs,
        "find-sorted-value",
        wrong,
        ["Since the values are ordered, binary search with left/right indices."],
    )
    reports = [
        client.get(f"/v1/interviews/{sid}/report").json()["report"] for sid in (first, second)
    ]
    assert reports[0]["facts"]["result"] == reports[1]["facts"]["result"] == "failed"
    capabilities = [
        {(w["capability"], w["severity"]) for w in r["weaknesses"] if w["source"] == "facts"}
        for r in reports
    ]
    assert capabilities[0] == capabilities[1]


def test_report_never_contradicts_execution(client: TestClient, run_jobs: Any) -> None:
    reference = get_corpus().problem("find-sorted-value").definition.reference_solution
    session_id = run_interview(client, run_jobs, "find-sorted-value", reference, [])
    report = client.get(f"/v1/interviews/{session_id}/report").json()["report"]
    assert report["facts"]["passed_hidden"] is True
    assert not any(
        w["capability"].endswith((".implementation", ".boundaries")) for w in report["weaknesses"]
    )
    assert report["confidence"] <= 0.35
    assert any("low confidence" in note for note in report["notes"])


class FailingProvider:
    name = "fake"
    model = "fake-model"

    def generate(self, *, system: str, user: str, schema: type[Any]) -> LLMResult[Any]:
        raise LLMUnavailable("malformed_output", "bad", attempts=3)


class GoodProvider:
    name = "fake"
    model = "fake-model"

    def __init__(self, sequence: int) -> None:
        self.sequence = sequence

    def generate(self, *, system: str, user: str, schema: type[Any]) -> LLMResult[Any]:
        assert "reference_solution" not in system and "def pair_sum_indices" not in system
        value = SemanticEvaluation(
            strengths=[
                SemanticClaim(
                    text="Asked a precise clarification.", evidence_sequences=[self.sequence]
                )
            ],
            weaknesses=[
                SemanticWeakness(
                    capability="interview.communication",
                    severity="low",
                    explanation="Brief explanations.",
                    evidence_sequences=[self.sequence],
                    confidence=0.6,
                )
            ],
            misconceptions=[],
            communication_rating=3,
            communication_summary="Clear.",
            reasoning_rating=3,
            reasoning_summary="Sound.",
            overall_confidence=0.8,
            transfer_confidence="high",
        )
        return LLMResult(value, "fake", "fake-model", 12, 100, 50, 1)


def completed_session(client: TestClient, run_jobs: Any) -> str:
    reference = PROBLEM.definition.reference_solution
    return run_interview(
        client,
        run_jobs,
        "pair-sum-indices",
        reference,
        ["Can the same element be used twice?", "A hash map of value to index."],
    )


def test_llm_evaluation_provenance(
    client: TestClient, run_jobs: Any, seeded_engine: Engine
) -> None:
    session_id = completed_session(client, run_jobs)
    with Session(seeded_engine) as session:
        interview = session.get(InterviewSession, session_id)
        assert interview is not None
        clarification = session.scalar(
            select(InterviewEvent.sequence).where(
                InterviewEvent.session_id == session_id,
                InterviewEvent.event_type == "clarification_asked",
            )
        )
        evaluation = evaluate_session(
            session, interview, provider=GoodProvider(int(clarification or 0))
        )
        assert evaluation.status == "completed" and evaluation.evaluator == "llm"
        assert evaluation.prompt_version.startswith("evaluator/v1+")
        report = evaluation.report
        assert report["interpretation_source"] == "llm"
        assert report["strengths"][0]["evidence_event_ids"]
        assert session.scalar(select(LLMCall).where(LLMCall.task == "evaluator")).status == "ok"  # type: ignore[union-attr]


def test_degraded_evaluation_when_llm_fails(
    client: TestClient, run_jobs: Any, seeded_engine: Engine
) -> None:
    session_id = completed_session(client, run_jobs)
    with Session(seeded_engine) as session:
        interview = session.get(InterviewSession, session_id)
        assert interview is not None
        evaluation = evaluate_session(session, interview, provider=FailingProvider())
        assert evaluation.status == "degraded" and evaluation.fallback_used
        assert any("unavailable" in note for note in evaluation.report["notes"])
        assert evaluation.report["facts"]["passed_hidden"] is True
        evidence = session.scalars(
            select(CapabilityEvidence).where(CapabilityEvidence.source_id == session_id)
        ).all()
        # Re-evaluation upserts the same evidence rows instead of duplicating them.
        assert len({row.dedupe_key for row in evidence}) == len(evidence)


def test_flagging_excludes_evidence_and_recomputes(
    client: TestClient, run_jobs: Any, seeded_engine: Engine
) -> None:
    wrong = PROBLEM.definition.wrong_solutions[0].code
    session_id = run_interview(client, run_jobs, "pair-sum-indices", wrong, ["hash map"])
    before = {item["slug"]: item for item in client.get("/v1/learner/capabilities").json()}
    flagged = client.post(
        f"/v1/interviews/{session_id}/report/flags",
        json={
            "capability_slug": "arrays-hashing.boundaries",
            "reason": "That was a typo, not a boundary issue.",
        },
    )
    assert flagged.status_code == 201
    assert flagged.json()["flags"][0]["capability_slug"] == "arrays-hashing.boundaries"
    after = {item["slug"]: item for item in client.get("/v1/learner/capabilities").json()}
    assert "arrays-hashing.boundaries" in before
    assert "arrays-hashing.boundaries" not in after
    with Session(seeded_engine) as session:
        rows = session.scalars(
            select(CapabilityEvidence).where(CapabilityEvidence.excluded.is_(True))
        ).all()
        assert rows and all("flagged" in (row.excluded_reason or "") for row in rows)
        assert session.scalar(select(InterviewEvaluation.id)) is not None
