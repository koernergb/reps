from fastapi.testclient import TestClient


def create_course(client: TestClient) -> tuple[str, str]:
    response = client.post(
        "/v1/study/courses",
        json={"name": "EECS 482", "description": "Operating systems"},
    )
    assert response.status_code == 201
    return response.json()["id"], response.json()["default_concept_id"]


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
        json={"answer": "Mutual exclusion", "rating": "good"},
    )
    assert result.status_code == 200
    assert result.json()["correctness"] == 1.0
    assert result.json()["interval_days"] == 2.2
    assert client.get("/v1/study/queue").json()["count"] == 0


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
                "front,back,type,tags\n"
                "What is paging?,Virtual memory mapping,basic,os|memory\n"
            ),
        },
    )
    assert imported.status_code == 201
    assert imported.json() == {"imported": 1}
    exported = client.get(f"/v1/study/courses/{course_id}/export.csv")
    assert exported.status_code == 200
    assert "What is paging?" in exported.text
