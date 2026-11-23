from fastapi.testclient import TestClient

from app.reviews.grading import AnswerGrade
from app.routes.study import _clamp_study_score, _study_has_gaps


def test_clamp_study_score_blocks_perfect_when_gaps() -> None:
    # Model said "advance"/1.0 but also listed wrong facts — must not stay at 100%.
    assert _clamp_study_score(1.0, "advance", errors=True) == 0.7
    assert _clamp_study_score(1.0, "review", errors=True) == 0.75
    assert _clamp_study_score(0.9, "advance", errors=False) == 0.9
    assert _study_has_gaps(
        AnswerGrade(
            correctness=1.0,
            missing_points=["test runs n+1 times"],
            misconceptions=["update is n not n+1"],
            recommended_action="advance",
            feedback="init once is right; the other counts are swapped.",
        )
    )


def create_course(client: TestClient) -> tuple[str, str]:
    response = client.post(
        "/v1/study/courses",
        json={"name": "EECS 482", "description": "Operating systems"},
    )
    assert response.status_code == 201
    return response.json()["id"], response.json()["default_concept_id"]


def test_queue_filters_by_course_and_practice_mode(client: TestClient) -> None:
    course_a, concept_a = create_course(client)
    course_b = client.post(
        "/v1/study/courses",
        json={"name": "EECS 376", "description": "Foundations"},
    ).json()
    concept_b = course_b["default_concept_id"]
    client.post(
        f"/v1/study/courses/{course_a}/cards",
        json={
            "concept_id": concept_a,
            "card_type": "basic",
            "prompt": "Mutex?",
            "answer": "mutual exclusion",
        },
    )
    client.post(
        f"/v1/study/courses/{course_b['id']}/cards",
        json={
            "concept_id": concept_b,
            "card_type": "basic",
            "prompt": "Skip list height?",
            "answer": "O(log n)",
        },
    )
    # Review the 376 card so it is no longer due, but still practiceable.
    card_b = client.get(f"/v1/study/courses/{course_b['id']}").json()["cards"][0]
    reviewed = client.post(
        f"/v1/study/cards/{card_b['id']}/review",
        json={"answer": "O(log n)", "confidence": 4},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["interval_days"] >= 1

    all_due = client.get("/v1/study/queue").json()
    assert all_due["mode"] == "due"
    assert all_due["course_id"] is None
    assert {card["prompt"] for card in all_due["due"]} == {"Mutex?"}

    scoped = client.get(f"/v1/study/queue?course_id={course_b['id']}&mode=due").json()
    assert scoped["course_name"] == "EECS 376"
    assert scoped["count"] == 0

    practice = client.get(f"/v1/study/queue?course_id={course_b['id']}&mode=practice").json()
    assert practice["mode"] == "practice"
    assert practice["count"] == 1
    assert practice["due"][0]["prompt"] == "Skip list height?"


def test_course_card_and_review_flow(client: TestClient) -> None:
    course_id, concept_id = create_course(client)
    card = client.post(
        f"/v1/study/courses/{course_id}/cards",
        json={
            "concept_id": concept_id,
            "card_type": "typed",
            "prompt": "What does a mutex provide?",
            "answer": "mutual exclusion",
            "accepted_answers": ["mutual exclusion"],
        },
    )
    assert card.status_code == 201
    queue = client.get("/v1/study/queue").json()
    assert queue["count"] == 1
    assert queue["due"][0]["prompt"] == "What does a mutex provide?"

    result = client.post(
        f"/v1/study/cards/{card.json()['id']}/review",
        json={"answer": "Mutual exclusion", "confidence": 3},
    )
    assert result.status_code == 200
    body = result.json()
    assert body["correctness"] == 1.0
    assert body["confidence"] == 3
    assert body["interval_days"] == 2.2
    assert body["feedback"] == "Correct."
    assert client.get("/v1/study/queue").json()["count"] == 0


def test_review_requires_answer_and_uses_confidence(client: TestClient) -> None:
    course_id, concept_id = create_course(client)
    card = client.post(
        f"/v1/study/courses/{course_id}/cards",
        json={
            "concept_id": concept_id,
            "card_type": "typed",
            "prompt": "Heapify build cost?",
            "answer": "O(n)",
            "accepted_answers": ["O(n)", "linear"],
        },
    ).json()
    missing = client.post(f"/v1/study/cards/{card['id']}/review", json={"confidence": 5})
    assert missing.status_code == 422
    wrong = client.post(
        f"/v1/study/cards/{card['id']}/review",
        json={"answer": "O(log n)", "confidence": 5},
    )
    assert wrong.status_code == 200
    assert wrong.json()["correctness"] == 0.0
    assert wrong.json()["lapsed"] is True
    assert wrong.json()["interval_days"] < 1


def test_discard_draft_card(client: TestClient) -> None:
    course_id, concept_id = create_course(client)
    card = client.post(
        f"/v1/study/courses/{course_id}/cards",
        json={
            "concept_id": concept_id,
            "card_type": "basic",
            "prompt": "Temporary draft?",
            "answer": "Yes",
            "status": "draft",
        },
    )
    assert card.status_code == 201
    card_id = card.json()["id"]
    assert client.delete(f"/v1/study/cards/{card_id}").status_code == 204
    detail = client.get(f"/v1/study/courses/{course_id}").json()
    assert all(item["id"] != card_id for item in detail["cards"])


def test_generated_cards_require_a_provider(client: TestClient) -> None:
    course_id, _ = create_course(client)
    source = client.post(
        f"/v1/study/courses/{course_id}/sources",
        json={
            "title": "Scheduling notes",
            "body": "Round robin rotates runnable processes after a fixed time quantum.",
        },
    )
    response = client.post(f"/v1/study/sources/{source.json()['id']}/generate")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "llm_not_configured"


def test_reset_removes_study_content_and_dynamic_capabilities(client: TestClient) -> None:
    course_id, _ = create_course(client)
    exported = client.get("/v1/me/export").json()["additional"]
    assert exported["study_courses"][0]["id"] == course_id

    response = client.delete("/v1/me/history")
    assert response.status_code == 200
    assert response.json()["deleted"]["study_courses"] == 1
    assert client.get("/v1/study/courses").json() == []


def test_csv_import_and_export(client: TestClient) -> None:
    course_id, concept_id = create_course(client)
    imported = client.post(
        f"/v1/study/courses/{course_id}/import",
        json={
            "concept_id": concept_id,
            "csv_text": (
                "concept,type,front,back,accepted_answers,tags,status\n"
                'Paging,basic,"What is paging?","Virtual memory mapping",,os|memory,active\n'
                'Heaps,typed,"Heapify cost?","O(n)",O(n)|linear,eecs281|heaps,active\n'
            ),
        },
    )
    assert imported.status_code == 201
    assert imported.json() == {"imported": 2}
    detail = client.get(f"/v1/study/courses/{course_id}").json()
    names = {item["name"] for item in detail["concepts"]}
    assert "Paging" in names
    assert "Heaps" in names
    exported = client.get(f"/v1/study/courses/{course_id}/export.csv")
    assert exported.status_code == 200
    assert "What is paging?" in exported.text
    assert "Heapify cost?" in exported.text
