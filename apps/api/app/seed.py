"""Synchronize the database projection of the curated corpus.

Corpus files under `packages/problem-corpus` are the source of truth. This command is
idempotent: it inserts missing rows, updates rows whose content version changed, and retires
(never deletes) problems that left the corpus, so learner history keeps its references.
"""

from __future__ import annotations

from uuid import NAMESPACE_URL, uuid5

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.corpus.loader import Corpus, LoadedProblem, get_corpus
from app.db import create_database_engine, create_session_factory
from app.local_mode import LOCAL_USER_ID
from app.models import (
    Capability,
    Exercise,
    Problem,
    ProblemCapability,
    ProblemEvaluator,
    Topic,
    User,
)

logger = structlog.get_logger()


def stable_id(kind: str, slug: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"https://reps.local/{kind}/{slug}"))


def _hidden_tests(problem: LoadedProblem) -> list[dict[str, object]]:
    return [
        {"id": test.id, "args": test.args, "expected": test.expected, "label": test.label}
        for test in problem.hidden_tests
    ]


def _apply_problem(
    row: Problem,
    loaded: LoadedProblem,
    topics: dict[str, Topic],
    capabilities: dict[str, Capability],
) -> None:
    definition = loaded.definition
    row.slug = definition.slug
    row.title = definition.title
    row.statement = definition.statement.strip()
    row.difficulty = definition.difficulty
    row.language = "python"
    row.time_complexity = definition.time_complexity
    row.space_complexity = definition.space_complexity
    row.starter_code = definition.starter_code
    row.examples = [example.model_dump(exclude_none=True) for example in definition.examples]
    row.constraints = list(definition.constraints)
    row.visible_tests = [
        {"id": test.id, "args": test.args, "expected": test.expected}
        for test in loaded.visible_tests
    ]
    row.status = definition.status
    row.topic = topics[definition.topic]
    row.content_version = definition.version
    row.role = definition.role
    row.transfer_group = definition.transfer_group
    row.patterns = list(definition.patterns)
    row.related_slugs = list(definition.related)
    evaluator = row.evaluator or ProblemEvaluator()
    evaluator.reference_solution = definition.reference_solution
    evaluator.hidden_tests = _hidden_tests(loaded)
    evaluator.common_mistakes = [mistake.model_dump() for mistake in definition.common_mistakes]
    evaluator.follow_up_questions = list(definition.follow_ups)
    evaluator.evaluator_version = definition.version
    evaluator.hints = list(definition.hints)
    evaluator.key_insight = definition.key_insight
    evaluator.clarifications = [item.model_dump() for item in definition.clarifications]
    row.evaluator = evaluator
    wanted = {weight.slug: weight.weight for weight in definition.capabilities}
    row.capability_links = [link for link in row.capability_links if link.capability.slug in wanted]
    existing = {link.capability.slug: link for link in row.capability_links}
    for slug, weight in wanted.items():
        if slug in existing:
            existing[slug].weight = weight
        else:
            row.capability_links.append(
                ProblemCapability(capability=capabilities[slug], weight=weight)
            )


def sync_corpus(session: Session, corpus: Corpus) -> dict[str, int]:
    counts = {"problems_created": 0, "problems_updated": 0, "problems_retired": 0}
    topics: dict[str, Topic] = {topic.slug: topic for topic in session.scalars(select(Topic)).all()}
    for topic_def in corpus.taxonomy.topics:
        topic = topics.get(topic_def.slug)
        if topic is None:
            topic = Topic(id=stable_id("topic", topic_def.slug), slug=topic_def.slug)
            session.add(topic)
            topics[topic_def.slug] = topic
        topic.name = topic_def.name
    for topic_def in corpus.taxonomy.topics:
        topics[topic_def.slug].parent = topics.get(topic_def.parent or "")

    capabilities: dict[str, Capability] = {
        item.slug: item for item in session.scalars(select(Capability)).all()
    }
    for cap_def in corpus.taxonomy.capabilities:
        capability = capabilities.get(cap_def.slug)
        if capability is None:
            capability = Capability(id=stable_id("capability", cap_def.slug), slug=cap_def.slug)
            session.add(capability)
            capabilities[cap_def.slug] = capability
        capability.topic = topics[cap_def.topic]
        capability.name = cap_def.name
        capability.description = cap_def.description
        capability.capability_type = cap_def.type
    session.flush()

    rows = {
        row.slug: row
        for row in session.scalars(
            select(Problem).options(
                selectinload(Problem.capability_links).selectinload(ProblemCapability.capability),
                selectinload(Problem.evaluator),
            )
        ).all()
    }
    for slug, loaded in corpus.problems.items():
        row = rows.get(slug)
        if row is None:
            row = Problem(id=stable_id("problem", slug))
            _apply_problem(row, loaded, topics, capabilities)
            session.add(row)
            counts["problems_created"] += 1
        elif (
            row.content_version != loaded.definition.version
            or row.status != loaded.definition.status
            or row.evaluator is None
        ):
            _apply_problem(row, loaded, topics, capabilities)
            counts["problems_updated"] += 1
    for slug, row in rows.items():
        if slug not in corpus.problems and row.status != "retired":
            row.status = "retired"
            counts["problems_retired"] += 1
    session.flush()

    problem_ids = dict(session.execute(select(Problem.slug, Problem.id)).tuples().all())
    exercises = {
        row.source_id: row
        for row in session.scalars(select(Exercise).where(Exercise.source_type == "curated"))
    }
    for exercise_id, loaded_exercise in corpus.exercises.items():
        exercise_def = loaded_exercise.definition
        exercise_row = exercises.get(exercise_id)
        if exercise_row is None:
            exercise_row = Exercise(
                id=stable_id("exercise", exercise_id),
                source_type="curated",
                source_id=exercise_id,
            )
            session.add(exercise_row)
        exercise_row.capability_id = capabilities[exercise_def.capability].id
        exercise_row.problem_id = (
            problem_ids.get(exercise_def.problem) if exercise_def.problem else None
        )
        exercise_row.exercise_type = exercise_def.type
        exercise_row.prompt = exercise_def.prompt
        exercise_row.expected_answer = exercise_def.reference_answer
        exercise_row.status = exercise_def.status
        exercise_row.estimated_minutes = exercise_def.estimated_minutes
        exercise_row.provenance = {
            "source": "corpus",
            "reviewed": exercise_def.status == "reviewed",
        }
    session.commit()
    return counts


def seed_database(session: Session, corpus: Corpus | None = None) -> dict[str, int]:
    if session.get(User, LOCAL_USER_ID) is None:
        session.add(
            User(
                id=LOCAL_USER_ID,
                email=None,
                display_name="Local learner",
                mode="local",
            )
        )
        session.flush()
    return sync_corpus(session, corpus or get_corpus())


def main() -> None:
    engine = create_database_engine()
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        counts = seed_database(session)
    engine.dispose()
    logger.info("corpus_synchronized", **counts)


if __name__ == "__main__":
    main()
