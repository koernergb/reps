import threading
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.corpus.loader import get_corpus
from app.execution.backends import TrustedSubprocessBackend
from app.execution.service import (
    ExecutionRejected,
    claim_next_job,
    process_available_jobs,
    recover_stale_running_jobs,
    run_job,
    submit_job,
    utcnow,
)
from app.local_mode import LOCAL_USER_ID
from app.models import Base, ExecutionJob, User
from app.seed import seed_database

BACKEND = TrustedSubprocessBackend()
REFERENCE = get_corpus().problem("pair-sum-indices").definition.reference_solution
WRONG = "def pair_sum_indices(nums, target):\n    return [0, 1]\n"


def key() -> str:
    return uuid4().hex


def submit(session: Session, code: str = REFERENCE, kind: str = "submit", **kwargs):  # type: ignore[no-untyped-def]
    return submit_job(
        session,
        user_id=LOCAL_USER_ID,
        problem_slug="pair-sum-indices",
        code=code,
        kind=kind,
        idempotency_key=kwargs.pop("idempotency_key", key()),
        **kwargs,
    )


def test_submit_is_idempotent_and_detects_key_reuse(seeded_engine: Engine) -> None:
    with Session(seeded_engine) as session:
        first, created = submit(session, idempotency_key="same-key-123")
        again, created_again = submit(session, idempotency_key="same-key-123")
        assert created and not created_again
        assert first.id == again.id
        with pytest.raises(ExecutionRejected) as error:
            submit(session, code=WRONG, idempotency_key="same-key-123")
        assert error.value.code == "idempotency_conflict"


def test_kill_switch_rejects_new_jobs(seeded_engine: Engine) -> None:
    settings = Settings(
        environment="test", execution_backend="trusted-subprocess", execution_enabled=False
    )
    with Session(seeded_engine) as session, pytest.raises(ExecutionRejected) as error:
        submit(session, settings=settings)
    assert error.value.status_code == 503


def test_queue_cap_and_rate_limit(seeded_engine: Engine) -> None:
    settings = Settings(
        environment="test",
        execution_backend="trusted-subprocess",
        execution_max_queued_per_user=2,
        execution_rate_per_minute=100,
    )
    with Session(seeded_engine) as session:
        submit(session, settings=settings)
        submit(session, settings=settings)
        with pytest.raises(ExecutionRejected) as error:
            submit(session, settings=settings)
        assert error.value.code == "queue_full"
    limited = Settings(
        environment="test",
        execution_backend="trusted-subprocess",
        execution_max_queued_per_user=100,
        execution_rate_per_minute=1,
    )
    with Session(seeded_engine) as session:
        with pytest.raises(ExecutionRejected) as error:
            submit(session, settings=limited)
        assert error.value.code == "rate_limited"


def test_unknown_problem_and_oversized_source(seeded_engine: Engine) -> None:
    with Session(seeded_engine) as session:
        with pytest.raises(ExecutionRejected) as error:
            submit_job(
                session,
                user_id=LOCAL_USER_ID,
                problem_slug="nope",
                code="x",
                kind="run",
                idempotency_key=key(),
            )
        assert error.value.status_code == 404
        with pytest.raises(ExecutionRejected) as error:
            submit(session, code="#" * 50_001)
        assert error.value.status_code == 413


def test_run_reports_visible_detail_only(seeded_engine: Engine) -> None:
    with Session(seeded_engine) as session:
        job, _ = submit(session, code=WRONG, kind="run")
        claimed = claim_next_job(session)
        assert claimed is not None and claimed.id == job.id
        run_job(session, claimed, BACKEND)
        assert job.status == "completed"
        assert job.verdict == "failed"
        assert "hidden" not in job.result_public
        assert len(job.result_public["visible"]) == 2
        assert all(test["visible"] for test in job.result_private["tests"])


def test_submit_reports_only_aggregate_hidden_feedback(seeded_engine: Engine) -> None:
    hidden = get_corpus().problem("pair-sum-indices").hidden_tests
    with Session(seeded_engine) as session:
        job, _ = submit(session, code=WRONG)
        run_job(session, claim_next_job(session), BACKEND)  # type: ignore[arg-type]
        public = job.result_public
        assert public["hidden"]["total"] == len(hidden)
        assert public["hidden"]["passed"] < len(hidden)
        assert set(public["hidden"]["failures"]) <= {"wrong_answer", "error", "timeout"}
        serialized = str(public)
        visible_expected = [test["expected"] for test in public["visible"]]
        for test in hidden:
            assert str(test.args)[:40] not in serialized
            if test.expected not in visible_expected:
                assert f"'expected': {test.expected!r}" not in serialized


def test_passing_submission(seeded_engine: Engine) -> None:
    with Session(seeded_engine) as session:
        job, _ = submit(session)
        run_job(session, claim_next_job(session), BACKEND)  # type: ignore[arg-type]
        assert job.verdict == "passed"
        assert job.result_public["hidden"]["passed"] == job.result_public["hidden"]["total"]


def test_concurrent_claims_never_run_a_job_twice(tmp_path: Path) -> None:
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'claims.sqlite'}", connect_args={"timeout": 30}
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_database(session)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        for _ in range(4):
            submit(session)
    claimed: list[str] = []
    lock = threading.Lock()

    def worker() -> None:
        with factory() as session:
            while (job := claim_next_job(session)) is not None:
                with lock:
                    claimed.append(job.id)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(claimed) == 4
    assert len(set(claimed)) == 4
    engine.dispose()


def test_process_available_jobs_and_expiry(seeded_engine: Engine) -> None:
    factory = sessionmaker(bind=seeded_engine, expire_on_commit=False)
    with factory() as session:
        stale, _ = submit(session)
        stale.expires_at = utcnow() - timedelta(seconds=1)
        session.commit()
        fresh, _ = submit(session)
    assert process_available_jobs(factory, BACKEND) == 1
    with factory() as session:
        assert session.get(ExecutionJob, stale.id).status == "expired"  # type: ignore[union-attr]
        assert session.get(ExecutionJob, fresh.id).status == "completed"  # type: ignore[union-attr]


def test_stale_running_jobs_are_recovered(seeded_engine: Engine) -> None:
    with Session(seeded_engine) as session:
        job, _ = submit(session)
        claim_next_job(session)
        job.started_at = utcnow() - timedelta(hours=1)
        session.commit()
        assert recover_stale_running_jobs(session) == 1
        session.refresh(job)
        assert job.status == "failed"


def test_trusted_backend_is_refused_outside_tests(seeded_engine: Engine) -> None:
    with pytest.raises(ValueError):
        Settings(environment="development", execution_backend="trusted-subprocess")


def test_api_create_poll_and_cancel(client: TestClient, seeded_engine: Engine) -> None:
    response = client.post(
        "/v1/executions",
        json={
            "problem_slug": "pair-sum-indices",
            "code": REFERENCE,
            "kind": "run",
            "idempotency_key": key(),
        },
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued" and body["result"] is None
    factory = sessionmaker(bind=seeded_engine, expire_on_commit=False)
    process_available_jobs(factory, BACKEND)
    polled = client.get(f"/v1/executions/{body['id']}").json()
    assert polled["status"] == "completed"
    assert polled["result"]["verdict"] == "passed"
    queued = client.post(
        "/v1/executions",
        json={
            "problem_slug": "pair-sum-indices",
            "code": REFERENCE,
            "kind": "run",
            "idempotency_key": key(),
        },
    ).json()
    cancelled = client.post(f"/v1/executions/{queued['id']}/cancel").json()
    assert cancelled["status"] == "cancelled"


def test_api_errors_use_envelope(client: TestClient) -> None:
    response = client.post(
        "/v1/executions",
        json={"problem_slug": "nope", "code": "x", "kind": "run", "idempotency_key": key()},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "problem_not_found"
    assert response.json()["error"]["request_id"]


def test_other_users_jobs_are_invisible(client: TestClient, seeded_engine: Engine) -> None:
    with Session(seeded_engine) as session:
        other = User(display_name="Other", mode="authenticated", email="other@example.com")
        session.add(other)
        session.flush()
        job, _ = submit_job(
            session,
            user_id=other.id,
            problem_slug="pair-sum-indices",
            code=REFERENCE,
            kind="run",
            idempotency_key=key(),
        )
    assert client.get(f"/v1/executions/{job.id}").status_code == 404
    assert client.post(f"/v1/executions/{job.id}/cancel").status_code == 404
    with Session(seeded_engine) as session:
        assert session.scalar(select(ExecutionJob.status).where(ExecutionJob.id == job.id)) == (
            "queued"
        )


def test_system_status_reports_flags(client: TestClient) -> None:
    body = client.get("/v1/system/status").json()
    assert body["execution"]["backend"] == get_settings().execution_backend
    assert body["features"]["interviews"] is True
