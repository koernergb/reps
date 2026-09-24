"""Post-interview evaluation with provenance, validation, and a degraded fallback.

Pipeline: deterministic facts -> fact-derived weaknesses -> semantic interpretation (LLM when
configured, rules otherwise) -> validation (evidence, capability, contradiction checks) ->
stored report -> learner-model evidence and remediation scheduling.
"""

from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.corpus.loader import LoadedProblem, get_corpus
from app.evaluation.facts import compute_facts
from app.evaluation.rules import fact_weaknesses, rules_semantic, scorecard
from app.evaluation.schemas import (
    REPORT_SCHEMA_VERSION,
    Assessment,
    Claim,
    Facts,
    Report,
    SemanticEvaluation,
    Weakness,
)
from app.llm.audit import record_call
from app.llm.prompts import fence, load_prompt
from app.llm.provider import LLMProvider, LLMUnavailable, build_provider
from app.models import ExecutionJob, InterviewEvaluation, InterviewEvent, InterviewSession, Problem

logger = structlog.get_logger()
PROMPT_VERSION = "v1"
SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2}
POSITIVE_CORRECTNESS = re.compile(
    r"\b(passed|passes|all tests|correct solution|works correctly|solved it)\b", re.I
)
NEGATIVE_CORRECTNESS = re.compile(r"\b(failed|fails|incorrect code|does not work|broken)\b", re.I)

provider_factory = build_provider


def utcnow() -> datetime:
    return datetime.now(UTC)


def latest_evaluation(db: Session, session_id: str) -> InterviewEvaluation | None:
    return db.scalar(
        select(InterviewEvaluation)
        .where(InterviewEvaluation.session_id == session_id)
        .order_by(InterviewEvaluation.created_at.desc())
        .limit(1)
    )


def allowed_capabilities(problem: LoadedProblem) -> set[str]:
    topic = problem.definition.topic
    suffixes = (
        "recognition",
        "invariant",
        "implementation",
        "boundaries",
        "complexity",
        "transfer",
    )
    return {f"{topic}.{suffix}" for suffix in suffixes} | {
        "interview.clarification",
        "interview.communication",
        "interview.testing",
        "interview.independence",
    }


def transcript_for_prompt(events: list[InterviewEvent]) -> str:
    lines = []
    for event in events:
        payload = event.payload
        if event.event_type == "code_edit":
            content = f"(code checkpoint, {payload.get('chars', 0)} chars)"
        elif "content" in payload:
            content = str(payload["content"])
        else:
            content = json.dumps(
                {key: value for key, value in payload.items() if key not in ("code",)}
            )
        if event.actor == "learner":
            content = fence("learner_message", content, 1000)
        lines.append(f"{event.sequence}: [{event.actor}] {event.event_type}: {content[:1200]}")
    return "\n".join(lines[-120:])


def validate_semantic(
    semantic: SemanticEvaluation,
    facts: Facts,
    events: list[InterviewEvent],
    problem: LoadedProblem,
) -> tuple[list[Claim], list[Weakness], list[Claim], list[str]]:
    """Map evidence sequences to event ids and drop unsupported or contradictory claims."""
    by_sequence = {event.sequence: event.id for event in events}
    allowed = allowed_capabilities(problem)
    issues: list[str] = []

    def ids(sequences: list[int]) -> list[str]:
        return [by_sequence[sequence] for sequence in sequences if sequence in by_sequence]

    strengths: list[Claim] = []
    for claim in semantic.strengths:
        evidence = ids(claim.evidence_sequences)
        if not evidence:
            issues.append("unsupported_strength")
            continue
        if POSITIVE_CORRECTNESS.search(claim.text) and not facts.passed_hidden:
            issues.append("contradicts_execution")
            continue
        strengths.append(Claim(text=claim.text[:400], evidence_event_ids=evidence))
    weaknesses: list[Weakness] = []
    for item in semantic.weaknesses:
        evidence = ids(item.evidence_sequences)
        if item.capability not in allowed:
            issues.append("unknown_capability")
            continue
        if not evidence:
            issues.append("unsupported_weakness")
            continue
        if (
            NEGATIVE_CORRECTNESS.search(item.explanation)
            and facts.passed_hidden
            and (item.capability.endswith((".implementation", ".boundaries")))
        ):
            issues.append("contradicts_execution")
            continue
        weaknesses.append(
            Weakness(
                capability=item.capability,
                severity=item.severity,
                explanation=item.explanation[:400],
                evidence_event_ids=evidence,
                confidence=max(0.0, min(1.0, item.confidence)),
                source="llm",
            )
        )
    misconceptions = []
    for claim in semantic.misconceptions:
        evidence = ids(claim.evidence_sequences)
        if evidence:
            misconceptions.append(Claim(text=claim.text[:400], evidence_event_ids=evidence))
        else:
            issues.append("unsupported_misconception")
    return strengths, weaknesses, misconceptions, issues


def merge_weaknesses(*groups: list[Weakness]) -> list[Weakness]:
    """One entry per capability: keep the most severe, merge evidence."""
    merged: dict[str, Weakness] = {}
    for group in groups:
        for item in group:
            current = merged.get(item.capability)
            if current is None:
                merged[item.capability] = item
                continue
            stronger = (
                item if SEVERITY_RANK[item.severity] > SEVERITY_RANK[current.severity] else current
            )
            evidence = list(dict.fromkeys(current.evidence_event_ids + item.evidence_event_ids))
            merged[item.capability] = stronger.model_copy(
                update={
                    "evidence_event_ids": evidence,
                    "confidence": max(current.confidence, item.confidence),
                }
            )
    return sorted(merged.values(), key=lambda item: -SEVERITY_RANK[item.severity])


def llm_semantic(
    provider: LLMProvider,
    facts: Facts,
    events: list[InterviewEvent],
    problem: LoadedProblem,
) -> tuple[SemanticEvaluation, Any, str]:
    template = load_prompt("evaluator", PROMPT_VERSION)
    definition = problem.definition
    system = template.render(
        capability_slugs=", ".join(sorted(allowed_capabilities(problem))),
        facts=facts.model_dump_json(indent=2),
        title=definition.title,
        time_complexity=definition.time_complexity,
        space_complexity=definition.space_complexity,
        common_mistakes="; ".join(mistake.description for mistake in definition.common_mistakes),
        transcript=transcript_for_prompt(events),
    )
    result = provider.generate(
        system=system,
        user="Evaluate this interview and return the JSON object.",
        schema=SemanticEvaluation,
    )
    return result.value, result, template.id


def evaluate_session(
    db: Session, interview: InterviewSession, provider: LLMProvider | None = None
) -> InterviewEvaluation:
    started = time.perf_counter()
    problem_row = db.get(Problem, interview.problem_id)
    assert problem_row is not None
    problem = get_corpus().problem(problem_row.slug)
    events = list(
        db.scalars(
            select(InterviewEvent)
            .where(InterviewEvent.session_id == interview.id)
            .order_by(InterviewEvent.sequence)
        )
    )
    jobs = list(
        db.scalars(
            select(ExecutionJob)
            .where(ExecutionJob.session_id == interview.id)
            .order_by(ExecutionJob.created_at)
        )
    )
    facts = compute_facts(interview, events, jobs, problem)
    deterministic = fact_weaknesses(facts, events, problem)
    (
        rule_strengths,
        rule_weaknesses,
        communication,
        reasoning,
        confidence,
        transfer,
    ) = rules_semantic(facts, events)
    strengths, weaknesses, misconceptions = rule_strengths, rule_weaknesses, []
    notes: list[str] = []
    source = "rules"
    status = "completed"
    evaluator = "rules"
    provider_name, model, prompt_id = "none", "rules-v1", "evaluator/rules-v1"
    attempts = 1
    validation: dict[str, Any] = {"issues": []}
    provider = provider or (
        provider_factory() if get_settings().feature_semantic_evaluation else None
    )
    if provider is not None:
        provider_name, model = provider.name, provider.model
        try:
            semantic, result, prompt_id = llm_semantic(provider, facts, events, problem)
            attempts = result.attempts
            s_strengths, s_weaknesses, s_misconceptions, issues = validate_semantic(
                semantic, facts, events, problem
            )
            validation = {"issues": issues, "dropped": len(issues)}
            strengths, weaknesses, misconceptions = s_strengths, s_weaknesses, s_misconceptions
            communication = Assessment(
                rating=max(1, min(4, semantic.communication_rating)),
                summary=semantic.communication_summary[:500],
            )
            reasoning = Assessment(
                rating=max(1, min(4, semantic.reasoning_rating)),
                summary=semantic.reasoning_summary[:500],
            )
            confidence = max(0.0, min(1.0, semantic.overall_confidence))
            transfer = semantic.transfer_confidence if facts.passed_hidden else "low"
            source = evaluator = "llm"
            record_call(
                db,
                user_id=interview.user_id,
                session_id=interview.id,
                task="evaluator",
                provider=result.provider,
                model=result.model,
                prompt_version=prompt_id,
                schema_version=REPORT_SCHEMA_VERSION,
                status="ok",
                latency_ms=result.latency_ms,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                attempts=result.attempts,
            )
            if len(issues) > 3:
                notes.append("Several AI claims lacked evidence and were removed.")
                confidence = min(confidence, 0.5)
        except LLMUnavailable as exc:
            status = "degraded"
            attempts = exc.attempts
            validation = {"issues": [exc.code]}
            notes.append(
                "The AI evaluator was unavailable, so this report uses rule-based "
                "interpretation only. You can retry the AI evaluation later."
            )
            record_call(
                db,
                user_id=interview.user_id,
                session_id=interview.id,
                task="evaluator",
                provider=provider.name,
                model=provider.model,
                prompt_version=f"evaluator/{PROMPT_VERSION}",
                schema_version=REPORT_SCHEMA_VERSION,
                status="error",
                error_code=exc.code,
                attempts=exc.attempts,
            )
    else:
        notes.append(
            "Interpretation is rule-based (no AI evaluator configured). Test results and "
            "hint usage are exact; communication and reasoning ratings are rough estimates."
        )
    if facts.learner_utterances < 2:
        confidence = min(confidence, 0.35)
        notes.append("Few explanations were shared, so this diagnosis has low confidence.")
    report = Report(
        problem_slug=problem.definition.slug,
        facts=facts,
        strengths=strengths,
        weaknesses=merge_weaknesses(deterministic, weaknesses),
        misconceptions=misconceptions,
        communication=communication,
        reasoning=reasoning,
        confidence=round(confidence, 2),
        transfer_confidence=transfer,
        scorecard=scorecard(facts, reasoning, communication) if interview.mode == "mock" else None,
        interpretation_source=source,
        notes=notes,
    )
    evaluation = InterviewEvaluation(
        user_id=interview.user_id,
        session_id=interview.id,
        status=status,
        evaluator=evaluator,
        provider=provider_name,
        model=model,
        prompt_version=prompt_id,
        schema_version=REPORT_SCHEMA_VERSION,
        event_seq_from=events[0].sequence if events else 0,
        event_seq_to=events[-1].sequence if events else 0,
        report=report.model_dump(),
        validation=validation,
        latency_ms=round((time.perf_counter() - started) * 1000),
        attempts=attempts,
        fallback_used=status == "degraded",
        created_at=utcnow(),
    )
    db.add(evaluation)
    interview.evaluation = {"evaluation_id": evaluation.id, "result": facts.result}
    db.commit()
    logger.info(
        "interview_evaluated",
        session_id=interview.id,
        status=status,
        evaluator=evaluator,
        result=facts.result,
        weaknesses=len(report.weaknesses),
    )
    from app.learning.pipeline import apply_evaluation

    apply_evaluation(db, evaluation)
    return evaluation
