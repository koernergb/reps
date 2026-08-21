from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.models import Capability, Problem, ProblemEvaluator, Topic, User
from app.seed import seed_database


def test_seed_is_idempotent(seeded_engine: Engine) -> None:
    with Session(seeded_engine) as session:
        seed_database(session)
        assert session.scalar(select(func.count()).select_from(User)) == 1
        assert session.scalar(select(func.count()).select_from(Topic)) == 3
        assert session.scalar(select(func.count()).select_from(Capability)) == 5
        assert session.scalar(select(func.count()).select_from(Problem)) == 3
        assert session.scalar(select(func.count()).select_from(ProblemEvaluator)) == 3


def test_lists_seeded_problems_without_evaluator_material(client: TestClient) -> None:
    response = client.get("/v1/problems")

    assert response.status_code == 200
    body = response.json()
    assert [item["slug"] for item in body] == [
        "balanced-delimiters",
        "find-sorted-value",
        "pair-sum-indices",
    ]
    serialized = response.text
    assert "hidden_tests" not in serialized
    assert "reference_solution" not in serialized
    assert "common_mistakes" not in serialized


def test_gets_public_problem_detail_only(client: TestClient) -> None:
    response = client.get("/v1/problems/pair-sum-indices")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Pair Sum Indices"
    assert body["starter_code"].startswith("def pair_sum_indices")
    assert len(body["visible_tests"]) == 2
    assert {item["slug"] for item in body["capabilities"]} == {
        "hash-map-complement-recognition",
        "hash-map-single-pass-implementation",
    }
    assert "hidden_tests" not in response.text
    assert "reference_solution" not in response.text


def test_missing_problem_returns_not_found(client: TestClient) -> None:
    response = client.get("/v1/problems/not-real")
    assert response.status_code == 404
