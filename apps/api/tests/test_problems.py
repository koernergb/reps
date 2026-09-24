from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.corpus.loader import get_corpus
from app.models import Capability, Exercise, Problem, ProblemEvaluator, Topic, User
from app.seed import seed_database

EVALUATOR_FIELDS = (
    "hidden_tests",
    "reference_solution",
    "common_mistakes",
    "follow_up_questions",
    "key_insight",
    "clarifications",
    "wrong_solutions",
)


def test_seed_is_idempotent(seeded_engine: Engine) -> None:
    corpus = get_corpus()
    with Session(seeded_engine) as session:
        counts = seed_database(session)
        assert counts == {"problems_created": 0, "problems_updated": 0, "problems_retired": 0}
        assert session.scalar(select(func.count()).select_from(User)) == 1
        assert session.scalar(select(func.count()).select_from(Topic)) == len(
            corpus.taxonomy.topics
        )
        assert session.scalar(select(func.count()).select_from(Capability)) == len(
            corpus.taxonomy.capabilities
        )
        assert session.scalar(select(func.count()).select_from(Problem)) == len(corpus.problems)
        assert session.scalar(select(func.count()).select_from(ProblemEvaluator)) == len(
            corpus.problems
        )
        assert session.scalar(select(func.count()).select_from(Exercise)) == len(corpus.exercises)


def test_seed_updates_changed_versions_and_retires_removed_problems(
    seeded_engine: Engine,
) -> None:
    corpus = get_corpus()
    with Session(seeded_engine) as session:
        row = session.scalar(select(Problem).where(Problem.slug == "pair-sum-indices"))
        assert row is not None
        row.content_version = 0
        row.title = "stale"
        session.add(
            Problem(
                slug="removed-problem",
                title="Removed",
                statement="x",
                difficulty="easy",
                time_complexity="O(1)",
                space_complexity="O(1)",
                starter_code="",
                status="development",
            )
        )
        session.commit()
        counts = seed_database(session, corpus)
        assert counts["problems_updated"] == 1
        assert counts["problems_retired"] == 1
        refreshed = session.scalar(select(Problem).where(Problem.slug == "pair-sum-indices"))
        assert refreshed is not None
        assert refreshed.title == "Pair Sum Indices"
        retired = session.scalar(select(Problem).where(Problem.slug == "removed-problem"))
        assert retired is not None and retired.status == "retired"


def test_lists_problems_without_evaluator_material(client: TestClient) -> None:
    response = client.get("/v1/problems")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == len(get_corpus().problems)
    assert body == sorted(body, key=lambda item: item["title"])
    for field in EVALUATOR_FIELDS:
        assert field not in response.text


def test_every_public_problem_detail_excludes_evaluator_material(client: TestClient) -> None:
    corpus = get_corpus()
    for slug, loaded in corpus.problems.items():
        response = client.get(f"/v1/problems/{slug}")
        assert response.status_code == 200
        text = response.text
        for field in EVALUATOR_FIELDS:
            assert field not in text
        reference_lines = [
            line.strip()
            for line in loaded.definition.reference_solution.splitlines()
            if len(line.strip()) > 30
        ]
        for line in reference_lines:
            assert line not in text, f"{slug} leaks reference line"
        for hint in loaded.definition.hints[2:]:
            assert hint not in text


def test_gets_public_problem_detail(client: TestClient) -> None:
    response = client.get("/v1/problems/pair-sum-indices")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Pair Sum Indices"
    assert body["starter_code"].startswith("def pair_sum_indices")
    assert len(body["visible_tests"]) == 2
    assert body["topic"] == {"slug": "arrays-hashing", "name": "Arrays & Hashing"}
    assert "arrays-hashing.recognition" in {item["slug"] for item in body["capabilities"]}


def test_missing_problem_returns_not_found(client: TestClient) -> None:
    response = client.get("/v1/problems/not-real")
    assert response.status_code == 404
