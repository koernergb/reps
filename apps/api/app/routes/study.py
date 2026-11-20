from __future__ import annotations

import csv
import io
import re
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import SessionDependency, UserDependency
from app.errors import ApiError
from app.learning.evidence import recompute_capability, upsert_evidence
from app.llm.audit import record_call
from app.llm.prompts import fence, load_prompt
from app.llm.provider import LLMUnavailable, build_provider
from app.models import (
    Capability,
    ReviewTask,
    StudyCard,
    StudyConcept,
    StudyCourse,
    StudyReview,
    StudySource,
    StudyUnit,
    Topic,
    User,
    new_id,
)
from app.reviews.grading import AnswerGrade, Rubric, grade as grade_answer, overlap_grade

router = APIRouter(prefix="/v1/study", tags=["study"])
CardType = Literal["basic", "reversed", "cloze", "typed", "explain", "compare"]


class CourseInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    color: str = Field(default="#166534", pattern=r"^#[0-9a-fA-F]{6}$")


class UnitInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)


class ConceptInput(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    unit_id: str | None = None


class CardInput(BaseModel):
    concept_id: str
    unit_id: str | None = None
    source_id: str | None = None
    card_type: CardType = "basic"
    prompt: str = Field(min_length=1, max_length=12000)
    answer: str = Field(min_length=1, max_length=12000)
    accepted_answers: list[str] = Field(default_factory=list, max_length=20)
    tags: list[str] = Field(default_factory=list, max_length=20)
    status: Literal["draft", "active", "suspended", "archived"] = "active"


class CardUpdate(BaseModel):
    prompt: str | None = Field(default=None, min_length=1, max_length=12000)
    answer: str | None = Field(default=None, min_length=1, max_length=12000)
    card_type: CardType | None = None
    accepted_answers: list[str] | None = None
    tags: list[str] | None = None
    status: Literal["draft", "active", "suspended", "archived"] | None = None


class SourceInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=20, max_length=100000)


class GeneratedCard(BaseModel):
    concept: str = Field(min_length=1, max_length=160)
    card_type: CardType
    prompt: str = Field(min_length=1, max_length=4000)
    answer: str = Field(min_length=1, max_length=6000)
    accepted_answers: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class GeneratedCards(BaseModel):
    cards: list[GeneratedCard] = Field(min_length=1, max_length=30)


class ReviewInput(BaseModel):
    answer: str = Field(min_length=1, max_length=12000)
    confidence: int = Field(ge=0, le=5)


class ImportInput(BaseModel):
    csv_text: str = Field(min_length=1, max_length=500000)
    concept_id: str | None = None


def now() -> datetime:
    return datetime.now(UTC)


def owned(db: Session, model: Any, row_id: str, user_id: str) -> Any:
    row = db.get(model, row_id)
    if row is None or row.user_id != user_id:
        raise ApiError(404, "not_found", "That study item does not exist.")
    return row


def course_view(db: Session, course: StudyCourse) -> dict[str, Any]:
    due = db.scalar(
        select(func.count())
        .select_from(StudyCard)
        .where(
            StudyCard.course_id == course.id,
            StudyCard.status == "active",
            StudyCard.next_review_at <= now(),
        )
    )
    return {
        "id": course.id,
        "name": course.name,
        "description": course.description,
        "color": course.color,
        "status": course.status,
        "due_count": due or 0,
        "card_count": db.scalar(
            select(func.count()).select_from(StudyCard).where(StudyCard.course_id == course.id)
        )
        or 0,
        "created_at": course.created_at,
    }


def card_view(card: StudyCard) -> dict[str, Any]:
    return {
        "id": card.id,
        "course_id": card.course_id,
        "unit_id": card.unit_id,
        "concept_id": card.concept_id,
        "source_id": card.source_id,
        "concept": card.concept.name,
        "card_type": card.card_type,
        "prompt": card.prompt,
        "answer": card.answer,
        "accepted_answers": card.accepted_answers,
        "tags": card.tags,
        "status": card.status,
        "origin": card.origin,
        "review_count": card.review_count,
        "next_review_at": card.next_review_at,
    }


def ensure_topic(db: Session) -> Topic:
    topic = db.scalar(select(Topic).where(Topic.slug == "general-study"))
    if topic is None:
        topic = Topic(slug="general-study", name="General study")
        db.add(topic)
        db.flush()
    return topic


def create_concept(
    db: Session, user: User, course: StudyCourse, body: ConceptInput
) -> StudyConcept:
    if body.unit_id:
        unit = owned(db, StudyUnit, body.unit_id, user.id)
        if unit.course_id != course.id:
            raise ApiError(422, "wrong_course", "The unit belongs to another course.")
    concept_id = new_id()
    capability = Capability(
        topic_id=ensure_topic(db).id,
        slug=f"study.{concept_id}.recall",
        name=f"{course.name}: {body.name}",
        description=body.description or f"Recall and explain {body.name}",
        capability_type="recall",
    )
    db.add(capability)
    db.flush()
    concept = StudyConcept(
        id=concept_id,
        user_id=user.id,
        course_id=course.id,
        unit_id=body.unit_id,
        capability_id=capability.id,
        name=body.name,
        description=body.description,
    )
    db.add(concept)
    db.flush()
    return concept


def schedule(db: Session, card: StudyCard, due: datetime | None = None) -> ReviewTask:
    existing = db.scalar(
        select(ReviewTask).where(
            ReviewTask.user_id == card.user_id,
            ReviewTask.study_card_id == card.id,
            ReviewTask.status.in_(("pending", "snoozed")),
        )
    )
    target = due or now()
    card.next_review_at = target
    if existing:
        existing.due_at = target
        existing.snoozed_until = None
        existing.status = "pending"
        return existing
    task = ReviewTask(
        user_id=card.user_id,
        capability_id=card.concept.capability_id,
        study_card_id=card.id,
        task_type="study_card",
        status="pending",
        due_at=target,
        source_type="study_card",
        source_id=card.id,
        chain_id=card.id,
        step=card.review_count,
        reason="Spaced repetition review",
        dedupe_key=f"study-card:{card.id}:{card.review_count}",
        created_at=now(),
        updated_at=now(),
    )
    db.add(task)
    return task


@router.get("/courses")
def courses(db: SessionDependency, user: UserDependency) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(StudyCourse)
        .where(StudyCourse.user_id == user.id)
        .order_by(StudyCourse.created_at.desc())
    ).all()
    return [course_view(db, row) for row in rows]


@router.post("/courses", status_code=201)
def add_course(body: CourseInput, db: SessionDependency, user: UserDependency) -> dict[str, Any]:
    course = StudyCourse(user_id=user.id, **body.model_dump())
    db.add(course)
    db.flush()
    concept = create_concept(db, user, course, ConceptInput(name="General"))
    db.commit()
    result = course_view(db, course)
    result["default_concept_id"] = concept.id
    return result


@router.get("/courses/{course_id}")
def get_course(course_id: str, db: SessionDependency, user: UserDependency) -> dict[str, Any]:
    course = owned(db, StudyCourse, course_id, user.id)
    result = course_view(db, course)
    result["units"] = [
        {"id": x.id, "name": x.name, "description": x.description}
        for x in db.scalars(
            select(StudyUnit)
            .where(StudyUnit.course_id == course.id)
            .order_by(StudyUnit.sort_order, StudyUnit.created_at)
        ).all()
    ]
    result["concepts"] = [
        {"id": x.id, "name": x.name, "description": x.description, "unit_id": x.unit_id}
        for x in db.scalars(
            select(StudyConcept)
            .where(StudyConcept.course_id == course.id)
            .order_by(StudyConcept.created_at)
        ).all()
    ]
    result["cards"] = [
        card_view(x)
        for x in db.scalars(
            select(StudyCard)
            .where(StudyCard.course_id == course.id)
            .order_by(StudyCard.created_at.desc())
        ).all()
    ]
    return result


@router.post("/courses/{course_id}/units", status_code=201)
def add_unit(
    course_id: str, body: UnitInput, db: SessionDependency, user: UserDependency
) -> dict[str, Any]:
    course = owned(db, StudyCourse, course_id, user.id)
    count = (
        db.scalar(
            select(func.count()).select_from(StudyUnit).where(StudyUnit.course_id == course.id)
        )
        or 0
    )
    row = StudyUnit(user_id=user.id, course_id=course.id, sort_order=count, **body.model_dump())
    db.add(row)
    db.commit()
    return {"id": row.id, "name": row.name, "description": row.description}


@router.post("/courses/{course_id}/concepts", status_code=201)
def add_concept(
    course_id: str, body: ConceptInput, db: SessionDependency, user: UserDependency
) -> dict[str, Any]:
    concept = create_concept(db, user, owned(db, StudyCourse, course_id, user.id), body)
    db.commit()
    return {"id": concept.id, "name": concept.name, "unit_id": concept.unit_id}


@router.post("/courses/{course_id}/cards", status_code=201)
def add_card(
    course_id: str, body: CardInput, db: SessionDependency, user: UserDependency
) -> dict[str, Any]:
    course = owned(db, StudyCourse, course_id, user.id)
    concept = owned(db, StudyConcept, body.concept_id, user.id)
    if concept.course_id != course.id:
        raise ApiError(422, "wrong_course", "The concept belongs to another course.")
    card = StudyCard(user_id=user.id, course_id=course.id, origin="manual", **body.model_dump())
    db.add(card)
    db.flush()
    if card.status == "active":
        schedule(db, card)
    db.commit()
    return card_view(card)


@router.patch("/cards/{card_id}")
def update_card(
    card_id: str, body: CardUpdate, db: SessionDependency, user: UserDependency
) -> dict[str, Any]:
    card = owned(db, StudyCard, card_id, user.id)
    old_status = card.status
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(card, key, value)
    if card.status == "active" and old_status != "active":
        schedule(db, card)
    elif card.status != "active":
        for task in db.scalars(
            select(ReviewTask).where(
                ReviewTask.study_card_id == card.id, ReviewTask.status.in_(("pending", "snoozed"))
            )
        ).all():
            task.status = "invalidated"
            task.completed_at = now()
    db.commit()
    return card_view(card)


@router.delete("/cards/{card_id}", status_code=204)
def delete_card(card_id: str, db: SessionDependency, user: UserDependency) -> Response:
    card = owned(db, StudyCard, card_id, user.id)
    db.delete(card)
    db.commit()
    return Response(status_code=204)


@router.post("/courses/{course_id}/sources", status_code=201)
def add_source(
    course_id: str, body: SourceInput, db: SessionDependency, user: UserDependency
) -> dict[str, Any]:
    course = owned(db, StudyCourse, course_id, user.id)
    source = StudySource(user_id=user.id, course_id=course.id, **body.model_dump())
    db.add(source)
    db.commit()
    return {"id": source.id, "title": source.title}


@router.post("/sources/{source_id}/generate", status_code=201)
def generate_cards(source_id: str, db: SessionDependency, user: UserDependency) -> dict[str, Any]:
    source = owned(db, StudySource, source_id, user.id)
    provider = build_provider()
    if provider is None:
        raise ApiError(
            409,
            "llm_not_configured",
            "Configure OpenAI or Gemini in Settings before generating cards.",
        )
    notes = source.body.strip()
    if len(notes) > 24000:
        notes = notes[:24000] + "\n\n[Truncated for card generation. Focus on the material above.]"
    try:
        result = provider.generate(
            system=(
                "You create precise, atomic spaced-repetition cards from supplied notes. "
                "Never add facts absent from the notes. Prefer retrieval over recognition. "
                "If the notes are a lecture transcript, ignore streaming chatter, jokes, "
                "personal asides, and student Q&A; keep only exam/project-relevant facts. "
                "Return 8-15 useful cards with concise answers."
            ),
            user=f"Source title: {source.title}\n\n{notes}",
            schema=GeneratedCards,
        )
    except LLMUnavailable as exc:
        record_call(
            db,
            user_id=user.id,
            session_id=None,
            task="study_card_generation",
            provider=provider.name,
            model=provider.model,
            prompt_version="study-cards-v1",
            schema_version=1,
            status="failed",
            attempts=exc.attempts,
            error_code=exc.code,
        )
        db.commit()
        detail = str(exc)
        if "Failed to validate JSON" in detail or "failed_generation" in detail:
            raise ApiError(
                400,
                "generation_failed",
                "The model could not structure cards from that input. "
                "Paste a shorter summary of the lecture, or import a CSV instead.",
            ) from exc
        raise ApiError(503, exc.code, detail) from exc
    record_call(
        db,
        user_id=user.id,
        session_id=None,
        task="study_card_generation",
        provider=result.provider,
        model=result.model,
        prompt_version="study-cards-v1",
        schema_version=1,
        status="completed",
        latency_ms=result.latency_ms,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        attempts=result.attempts,
    )
    course = owned(db, StudyCourse, source.course_id, user.id)
    existing = {
        x.name.casefold(): x
        for x in db.scalars(select(StudyConcept).where(StudyConcept.course_id == course.id)).all()
    }
    cards: list[StudyCard] = []
    for proposal in result.value.cards:
        concept = existing.get(proposal.concept.casefold())
        if concept is None:
            concept = create_concept(db, user, course, ConceptInput(name=proposal.concept))
            existing[proposal.concept.casefold()] = concept
        card = StudyCard(
            user_id=user.id,
            course_id=course.id,
            concept_id=concept.id,
            source_id=source.id,
            status="draft",
            origin="generated",
            **proposal.model_dump(exclude={"concept"}),
        )
        db.add(card)
        cards.append(card)
    db.commit()
    return {
        "cards": [card_view(x) for x in cards],
        "provider": result.provider,
        "model": result.model,
    }


@router.get("/queue")
def queue(db: SessionDependency, user: UserDependency) -> dict[str, Any]:
    cards = db.scalars(
        select(StudyCard)
        .where(
            StudyCard.user_id == user.id,
            StudyCard.status == "active",
            StudyCard.next_review_at <= now(),
        )
        .order_by(StudyCard.next_review_at)
        .limit(user.daily_review_cap)
    ).all()
    return {"due": [card_view(x) for x in cards], "count": len(cards)}


def normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


STUDY_GRADER_VERSION = "v1"
# Flashcards: floor scores by the grader's own action so partial credit isn't harsh.
_STUDY_ACTION_FLOOR = {"advance": 0.85, "review": 0.72, "coach": 0.45, "rebuild": 0.0}


def _soften_study_score(correctness: float, action: str) -> float:
    return round(max(correctness, _STUDY_ACTION_FLOOR.get(action, 0.0)), 2)


def grade_study_card(card: StudyCard, answer: str) -> tuple[float, str, str]:
    """Grade a study answer. Returns (correctness, feedback, grader_id)."""
    accepted = [card.answer, *card.accepted_answers]
    if any(normalized(answer) == normalized(item) for item in accepted if item.strip()):
        return 1.0, "Correct.", "exact"
    if card.card_type in ("typed", "cloze"):
        graded, grader_id = grade_answer(
            Rubric(
                prompt=card.prompt,
                key_points=[],
                accepted_answers=accepted,
                reference=card.answer,
                misconception=None,
            ),
            answer,
            None,
        )
        return graded.correctness, graded.feedback, grader_id

    baseline = overlap_grade(card.answer, answer)
    provider = build_provider()
    if provider is None:
        score = _soften_study_score(baseline.correctness, baseline.recommended_action)
        return score, baseline.feedback, "overlap/v1-study"

    template = load_prompt("study_grader", STUDY_GRADER_VERSION)
    system = template.render(
        prompt=card.prompt,
        reference=card.answer,
        accepted="; ".join(a for a in accepted if a.strip()) or "(none)",
        answer=fence("learner_answer", answer, 3000),
    )
    try:
        result = provider.generate(
            system=system, user="Grade the flashcard answer.", schema=AnswerGrade
        )
    except LLMUnavailable:
        score = _soften_study_score(baseline.correctness, baseline.recommended_action)
        return score, baseline.feedback, "overlap/v1-study-fallback"

    graded = result.value
    score = _soften_study_score(
        max(graded.correctness, baseline.correctness), graded.recommended_action
    )
    return score, graded.feedback, template.id


def interval_for(stability_days: float, correctness: float, confidence: int) -> tuple[float, bool]:
    """LLM/correctness gates lapses; confidence modulates growth within the band."""
    current = max(stability_days, 1.0)
    if correctness < 0.45:
        return 0.007, True
    if correctness < 0.7:
        return max(0.5, current * (0.5 + 0.12 * confidence)), False
    if confidence <= 1:
        return max(1.0, current * 1.2), False
    if confidence == 2:
        return max(1.5, current * 1.6), False
    if confidence == 3:
        return max(2.0, current * 2.2), False
    if confidence == 4:
        return max(3.0, current * 2.8), False
    return max(4.0, current * 3.2), False


@router.post("/cards/{card_id}/review")
def review(
    card_id: str, body: ReviewInput, db: SessionDependency, user: UserDependency
) -> dict[str, Any]:
    card = owned(db, StudyCard, card_id, user.id)
    if card.status != "active":
        raise ApiError(409, "card_inactive", "Only active cards can be reviewed.")
    answer = body.answer.strip()
    if not answer:
        raise ApiError(422, "answer_required", "Type an answer before submitting.")
    correctness, feedback, grader_id = grade_study_card(card, answer)
    interval, lapsed = interval_for(card.stability_days, correctness, body.confidence)
    reviewed = now()
    task = db.scalar(
        select(ReviewTask).where(
            ReviewTask.study_card_id == card.id, ReviewTask.status.in_(("pending", "snoozed"))
        )
    )
    if task:
        task.status = "completed"
        task.completed_at = reviewed
        task.updated_at = reviewed
        task.attempt_count += 1
    card.review_count += 1
    card.lapses += int(lapsed)
    card.stability_days = interval
    card.last_reviewed_at = reviewed
    due = reviewed + timedelta(days=interval)
    row = StudyReview(
        user_id=user.id,
        card_id=card.id,
        task_id=task.id if task else None,
        answer=answer,
        confidence=body.confidence,
        correctness=correctness,
        interval_days=interval,
        reviewed_at=reviewed,
    )
    db.add(row)
    upsert_evidence(
        db,
        user_id=user.id,
        capability_id=card.concept.capability_id,
        source_type="study_card",
        source_id=row.id,
        dedupe_key=f"study-review:{row.id}",
        occurred_at=reviewed,
        score=correctness,
        confidence=0.5 + 0.1 * body.confidence,
        hint_level=0,
        exercise_type=card.card_type,
        explanation=f"confidence {body.confidence}/5 on {card.prompt[:120]}",
    )
    recompute_capability(db, user.id, card.concept.capability_id)
    schedule(db, card, due)
    db.commit()
    return {
        "correctness": correctness,
        "confidence": body.confidence,
        "feedback": feedback,
        "grader": grader_id,
        "lapsed": lapsed,
        "interval_days": interval,
        "next_review_at": due,
        "expected_answer": card.answer,
    }


@router.get("/courses/{course_id}/export.csv")
def export_csv(course_id: str, db: SessionDependency, user: UserDependency) -> Response:
    course = owned(db, StudyCourse, course_id, user.id)
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["concept", "type", "front", "back", "accepted_answers", "tags", "status"],
    )
    writer.writeheader()
    for card in db.scalars(select(StudyCard).where(StudyCard.course_id == course.id)).all():
        writer.writerow(
            {
                "concept": card.concept.name,
                "type": card.card_type,
                "front": card.prompt,
                "back": card.answer,
                "accepted_answers": "|".join(card.accepted_answers),
                "tags": "|".join(card.tags),
                "status": card.status,
            }
        )
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{course.name}.csv"'},
    )


@router.post("/courses/{course_id}/import", status_code=201)
def import_csv(
    course_id: str, body: ImportInput, db: SessionDependency, user: UserDependency
) -> dict[str, int]:
    course = owned(db, StudyCourse, course_id, user.id)
    existing = {
        item.name.casefold(): item
        for item in db.scalars(select(StudyConcept).where(StudyConcept.course_id == course.id)).all()
    }
    fallback: StudyConcept | None = None
    if body.concept_id:
        fallback = owned(db, StudyConcept, body.concept_id, user.id)
        if fallback.course_id != course.id:
            raise ApiError(422, "wrong_course", "The concept belongs to another course.")
    count = 0
    allowed_types = {"basic", "reversed", "cloze", "typed", "explain", "compare"}
    try:
        rows = csv.DictReader(io.StringIO(body.csv_text))
        for source in rows:
            prompt, answer = (source.get("front") or "").strip(), (source.get("back") or "").strip()
            if not prompt or not answer:
                continue
            concept_name = (source.get("concept") or "").strip()
            if concept_name:
                concept = existing.get(concept_name.casefold())
                if concept is None:
                    concept = create_concept(db, user, course, ConceptInput(name=concept_name))
                    existing[concept_name.casefold()] = concept
            elif fallback is not None:
                concept = fallback
            else:
                concept = existing.get("imported")
                if concept is None:
                    concept = create_concept(db, user, course, ConceptInput(name="Imported"))
                    existing["imported"] = concept
            card_type = (source.get("type") or "basic").strip()
            if card_type not in allowed_types:
                card_type = "basic"
            accepted = [part.strip() for part in (source.get("accepted_answers") or "").split("|") if part.strip()]
            tags = [part.strip() for part in (source.get("tags") or "").split("|") if part.strip()]
            card = StudyCard(
                user_id=user.id,
                course_id=course.id,
                concept_id=concept.id,
                card_type=card_type,
                prompt=prompt,
                answer=answer,
                accepted_answers=accepted,
                tags=tags,
                status="active",
                origin="imported",
            )
            db.add(card)
            db.flush()
            schedule(db, card)
            count += 1
    except (csv.Error, ValueError) as exc:
        raise ApiError(422, "invalid_csv", "The CSV could not be imported.") from exc
    db.commit()
    return {"imported": count}
