from sqlalchemy import select

from app.auth.security import hash_password
from app.models import StudentProfile, StudentSubject, UserRole
from tests.factories import make_org, make_user


def _seed_student(db):
    org = make_org(db)
    student = make_user(
        db,
        org,
        role=UserRole.student,
        email="student@demo.example",
        password_hash=hash_password("pw"),
    )
    db.add(StudentProfile(user_id=student.id, exam_year=2027))
    db.add(StudentSubject(student_user_id=student.id, subject_code="english"))
    db.commit()
    return student


def _token(client):
    return client.post("/auth/login", json={"email": "student@demo.example", "password": "pw"}).json()[
        "access_token"
    ]


def test_student_can_get_report_overview(client, db_session):
    _seed_student(db_session)
    token = _token(client)

    start = client.post("/student/placement/start", headers={"Authorization": f"Bearer {token}"})
    assert start.status_code == 200
    paper_id = client.get("/student/placement", headers={"Authorization": f"Bearer {token}"}).json()[0]["id"]
    paper = client.get(f"/student/placement/{paper_id}", headers={"Authorization": f"Bearer {token}"}).json()
    wrong_payload = {"answers": [{"question_id": q["id"], "content": "Z"} for q in paper["questions"]]}
    submit = client.post(
        f"/student/placement/{paper_id}/submit",
        json=wrong_payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert submit.status_code == 200

    gen = client.post(
        "/student/self-tests/generate",
        json={"subject_code": "english"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert gen.status_code == 200
    self_paper_id = gen.json()["id"]
    self_paper = client.get(
        f"/student/self-tests/{self_paper_id}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    submit2 = client.post(
        f"/student/self-tests/{self_paper_id}/submit",
        json={"answers": [{"question_id": q["id"], "content": "Z"} for q in self_paper["questions"]]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert submit2.status_code == 200

    resp = client.get("/student/report/overview?subject_code=english", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["subject_code"] == "english"
    assert "wrong_source_counts" in body
    assert "weak_nodes" in body
    assert "self_test_trend" in body
    assert body["wrong_source_counts"].get("placement", 0) >= 1
    assert body["wrong_source_counts"].get("self_test", 0) >= 1
    assert len(body["weak_nodes"]) >= 1
    assert len(body["self_test_trend"]) >= 1

    # weak nodes should include readable knowledge node name (when available)
    first = body["weak_nodes"][0]
    assert "knowledge_node_name" in first
    if first["knowledge_node_id"] is not None:
        assert first["knowledge_node_name"]

