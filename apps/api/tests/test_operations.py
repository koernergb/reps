from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.corpus.loader import get_corpus
from app.execution.backends import DockerSandboxBackend
from app.execution.service import claim_next_job, run_job, submit_job
from app.local_mode import LOCAL_USER_ID
from app.metrics import percentile, request_metrics


def test_metrics_report_requests_jobs_and_slos(client: TestClient, run_jobs: Any) -> None:
    request_metrics.reset()
    view = client.post("/v1/interviews", json={"problem_slug": "pair-sum-indices"}).json()
    client.post(
        f"/v1/interviews/{view['id']}/messages",
        json={
            "content": "Is the input sorted?",
            "expected_version": view["version"],
            "idempotency_key": uuid4().hex,
        },
    )
    client.get("/v1/reviews/queue")
    reference = get_corpus().problem("pair-sum-indices").definition.reference_solution
    client.post(
        "/v1/executions",
        json={
            "problem_slug": "pair-sum-indices",
            "code": reference,
            "kind": "run",
            "idempotency_key": uuid4().hex,
        },
    )
    run_jobs()
    body = client.get("/v1/system/metrics").json()
    assert body["requests"]["POST /v1/interviews"]["count"] == 1
    assert body["execution"]["by_verdict"] == {"passed": 1}
    assert body["slo"]["session_start"]["met"] is True
    assert body["slo"]["code_execution"]["met"] is True
    assert "code" not in str(body["execution"])
    diagnostics = client.get("/v1/system/diagnostics").json()
    assert diagnostics["recent_jobs"][0]["verdict"] == "passed"
    assert "code" not in diagnostics["recent_jobs"][0]


def test_sandbox_outage_fails_closed_with_actionable_message(seeded_engine: Engine) -> None:
    with Session(seeded_engine) as session:
        submit_job(
            session,
            user_id=LOCAL_USER_ID,
            problem_slug="pair-sum-indices",
            code="x",
            kind="run",
            idempotency_key=uuid4().hex,
        )
        job = claim_next_job(session)
        assert job is not None
        run_job(
            session,
            job,
            DockerSandboxBackend("reps-sandbox:dev", docker_binary="/nonexistent/docker"),
        )
        assert job.status == "failed" and job.verdict is None
        assert "Docker" in job.result_public["message"]


def test_message_rate_limit(client: TestClient) -> None:
    view = client.post("/v1/interviews", json={"problem_slug": "pair-sum-indices"}).json()
    statuses = []
    for _ in range(32):
        response = client.post(
            f"/v1/interviews/{view['id']}/messages",
            json={
                "content": "hello",
                "expected_version": view["version"],
                "idempotency_key": uuid4().hex,
            },
        )
        statuses.append(response.status_code)
        if response.status_code == 200:
            view = response.json()
    assert 429 in statuses


def test_learning_metrics_have_denominators(client: TestClient, run_jobs: Any) -> None:
    empty = client.get("/v1/learner/metrics").json()
    assert empty["activated"] is False and empty["hints_per_problem"] is None
    view = client.post("/v1/interviews", json={"problem_slug": "pair-sum-indices"}).json()
    client.post(
        f"/v1/interviews/{view['id']}/advance",
        json={
            "target": "COMPLETE",
            "expected_version": view["version"],
            "idempotency_key": uuid4().hex,
        },
    )
    body = client.get("/v1/learner/metrics").json()
    assert body["activated"] is True and body["interviews_completed"] == 1
    assert body["hints_per_problem"] == 0


def test_percentile_edge_cases() -> None:
    assert percentile([], 95) == 0.0
    assert percentile([5.0], 95) == 5.0
    assert 90 <= percentile([float(i) for i in range(101)], 95) <= 96
