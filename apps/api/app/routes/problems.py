from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.local_mode import get_session
from app.models import Problem, ProblemCapability
from app.schemas import CapabilitySummary, ProblemDetail, ProblemSummary, TopicSummary

router = APIRouter(prefix="/v1/problems", tags=["problems"])
SessionDependency = Annotated[Session, Depends(get_session)]


def to_summary(problem: Problem) -> ProblemSummary:
    return ProblemSummary(
        id=problem.id,
        slug=problem.slug,
        title=problem.title,
        difficulty=problem.difficulty,
        language=problem.language,
        status=problem.status,
        topic=TopicSummary(slug=problem.topic.slug, name=problem.topic.name)
        if problem.topic
        else None,
        capabilities=[
            CapabilitySummary(
                slug=link.capability.slug,
                name=link.capability.name,
                capability_type=link.capability.capability_type,
                weight=link.weight,
            )
            for link in sorted(problem.capability_links, key=lambda item: item.capability.slug)
        ],
    )


@router.get("", response_model=list[ProblemSummary])
def list_problems(session: SessionDependency) -> list[ProblemSummary]:
    statement = (
        select(Problem)
        .options(
            selectinload(Problem.capability_links).selectinload(ProblemCapability.capability),
            selectinload(Problem.topic),
        )
        .where(Problem.status != "retired")
        .order_by(Problem.title)
    )
    return [to_summary(problem) for problem in session.scalars(statement).all()]


@router.get("/{slug}", response_model=ProblemDetail)
def get_problem(slug: str, session: SessionDependency) -> ProblemDetail:
    statement = (
        select(Problem)
        .options(
            selectinload(Problem.capability_links).selectinload(ProblemCapability.capability),
            selectinload(Problem.topic),
        )
        .where(Problem.slug == slug, Problem.status != "retired")
    )
    problem = session.scalar(statement)
    if problem is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found")
    summary = to_summary(problem)
    return ProblemDetail(
        **summary.model_dump(),
        statement=problem.statement,
        examples=problem.examples,
        constraints=problem.constraints,
        starter_code=problem.starter_code,
        visible_tests=problem.visible_tests,
    )
