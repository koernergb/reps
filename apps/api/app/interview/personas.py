"""Scripted candidate personas for interviewer regression (Human Gate 4 artifact).

    python -m app.interview.personas            # offline policy interviewer
    LLM_PROVIDER=openai python -m app.interview.personas --report personas.json

Runs each fixture in `packages/prompts/fixtures/personas/` against an isolated in-memory
database, executes trusted corpus code (reference / known-wrong solutions), and checks the
fixture's expectations plus global invariants: no solution leakage, no unsolicited hints,
valid final state, and evaluation alignment with deterministic facts.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.corpus.loader import get_corpus
from app.evaluation.service import latest_evaluation
from app.execution.backends import ExecutionBackend
from app.execution.service import (
    build_backend,
    claim_next_job,
    completion_hooks,
    run_job,
    submit_job,
)
from app.interview import service
from app.interview.guard import GuardContext, check_message, hidden_fingerprints
from app.local_mode import LOCAL_USER_ID
from app.models import Base, CapabilityEvidence, InterviewEvent, User
from app.seed import seed_database

FIXTURES = Path(__file__).resolve().parents[4] / "packages" / "prompts" / "fixtures" / "personas"


@dataclass
class PersonaResult:
    persona: str
    problem: str
    passed: bool
    failures: list[str] = field(default_factory=list)
    final_state: str = ""
    result: str | None = None
    weaknesses: list[str] = field(default_factory=list)
    leaks_blocked: int = 0
    leaks_shown: int = 0
    unsolicited_hints: int = 0
    transcript: list[dict[str, Any]] = field(default_factory=list)


def isolated_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    seed_database(session)
    return session


def code_for(problem_slug: str, spec: str) -> str:
    definition = get_corpus().problem(problem_slug).definition
    if spec == "reference":
        return definition.reference_solution
    if spec.startswith("wrong:"):
        mistake = spec.split(":", 1)[1]
        return next(item.code for item in definition.wrong_solutions if item.mistake == mistake)
    return spec


def execute(
    db: Session, backend: ExecutionBackend, interview_id: str, problem: str, code: str, kind: str
) -> None:
    submit_job(
        db,
        user_id=LOCAL_USER_ID,
        problem_slug=problem,
        code=code,
        kind=kind,
        idempotency_key=uuid4().hex,
        session_id=interview_id,
    )
    job = claim_next_job(db)
    assert job is not None
    run_job(db, job, backend)


def run_persona(path: Path, backend: ExecutionBackend | None = None) -> PersonaResult:
    fixture = yaml.safe_load(path.read_text())
    # The configured backend: the Docker sandbox normally, trusted subprocess only in tests.
    backend = backend or build_backend()
    db = isolated_session()
    completion_hooks[:] = [service.on_execution_completed]
    user = db.get(User, LOCAL_USER_ID)
    assert user is not None
    problem = fixture["problem"]
    if fixture.get("repeat"):
        warmup = service.start_session(db, user, problem, fixture.get("mode", "practice"))
        service.advance(db, user, warmup, "ABANDONED", warmup.version, uuid4().hex)
    interview = service.start_session(db, user, problem, fixture.get("mode", "practice"))
    result = PersonaResult(persona=fixture["persona"], problem=problem, passed=True)
    for step in fixture["steps"]:
        db.refresh(interview)
        if interview.state in ("COMPLETE", "ABANDONED"):
            break
        try:
            if "say" in step:
                service.post_message(
                    db, user, interview, step["say"], interview.version, uuid4().hex, None
                )
            elif "hint" in step:
                service.request_hint(db, user, interview, interview.version, uuid4().hex)
            elif "advance" in step:
                service.advance(
                    db, user, interview, step["advance"], interview.version, uuid4().hex
                )
            elif "code" in step:
                service.save_code(
                    db, interview, code_for(problem, step["code"]), uuid4().hex, "checkpoint"
                )
            elif "run" in step:
                spec = "reference" if step["run"] is True else step["run"]
                execute(db, backend, interview.id, problem, code_for(problem, spec), "run")
            elif "submit" in step:
                execute(
                    db, backend, interview.id, problem, code_for(problem, step["submit"]), "submit"
                )
        except Exception as exc:
            result.failures.append(f"step {step} raised {type(exc).__name__}: {exc}")
    db.refresh(interview)
    if interview.state not in ("COMPLETE", "ABANDONED"):
        service.advance(db, user, interview, "COMPLETE", interview.version, uuid4().hex)
        db.refresh(interview)
    events = db.scalars(
        select(InterviewEvent)
        .where(InterviewEvent.session_id == interview.id)
        .order_by(InterviewEvent.sequence)
    ).all()
    loaded = get_corpus().problem(problem)
    guard_context = GuardContext(
        reference_solution=loaded.definition.reference_solution,
        hidden_inputs=hidden_fingerprints(test.args for test in loaded.hidden_tests),
        key_insight=loaded.definition.key_insight,
    )
    requested = 0
    for event in events:
        if event.event_type == "leak_blocked":
            result.leaks_blocked += 1
        if event.event_type == "hint_requested":
            requested += 1
        if event.event_type == "hint_given":
            requested -= 1
            if requested < 0:
                result.unsolicited_hints += 1
                requested = 0
        if (
            event.event_type == "interviewer_message"
            and not check_message(event.payload["content"], guard_context).allowed
        ):
            result.leaks_shown += 1
        result.transcript.append(
            {
                "seq": event.sequence,
                "type": event.event_type,
                "actor": event.actor,
                "content": event.payload.get("content"),
            }
        )
    evaluation = latest_evaluation(db, interview.id)
    result.final_state = interview.state
    expect = fixture.get("expect", {})
    if evaluation is not None:
        report = evaluation.report
        result.result = report["facts"]["result"]
        result.weaknesses = [item["capability"] for item in report["weaknesses"]]
    if expect.get("result") and result.result != expect["result"]:
        result.failures.append(f"result {result.result} != {expect['result']}")
    if expect.get("final_state") and result.final_state != expect["final_state"]:
        result.failures.append(f"final state {result.final_state} != {expect['final_state']}")
    for capability in expect.get("weakness_in", []):
        if capability not in result.weaknesses:
            result.failures.append(f"missing expected weakness {capability}")
    for capability in expect.get("no_weakness_in", []):
        if capability in result.weaknesses:
            result.failures.append(f"unexpected weakness {capability}")
    if expect.get("repeat_exposure"):
        repeat = db.scalar(
            select(CapabilityEvidence.repeat_exposure)
            .where(CapabilityEvidence.source_id == interview.id)
            .limit(1)
        )
        if not repeat:
            result.failures.append("expected repeat exposure to be recorded")
    if result.leaks_shown:
        result.failures.append(f"{result.leaks_shown} interviewer message(s) leaked content")
    if result.unsolicited_hints:
        result.failures.append(f"{result.unsolicited_hints} unsolicited hint(s)")
    result.passed = not result.failures
    engine = db.get_bind()
    db.close()
    engine.dispose()  # type: ignore[union-attr]
    return result


def run_all(backend: ExecutionBackend | None = None) -> list[PersonaResult]:
    return [run_persona(path, backend) for path in sorted(FIXTURES.glob("*.yaml"))]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    results = run_all()
    for item in results:
        status = "PASS" if item.passed else "FAIL"
        print(
            f"{status} {item.persona:40} {item.result or '-':28} leaks_blocked={item.leaks_blocked}"
        )
        for failure in item.failures:
            print(f"     - {failure}")
    if args.report:
        args.report.write_text(json.dumps([asdict(item) for item in results], indent=2))
    return 0 if all(item.passed for item in results) else 1


if __name__ == "__main__":
    sys.exit(main())
