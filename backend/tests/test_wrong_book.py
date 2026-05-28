import uuid

from sqlalchemy import select

from app.auth.security import hash_password
from app.models import SyllabusNode, WrongBookItem, StudentProfile, StudentSubject, UserRole
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


def test_wrong_book_ingested_after_self_test_submit(client, db_session):
    _seed_student(db_session)
    token = _token(client)

    gen = client.post(
        "/student/self-tests/generate",
        json={"subject_code": "english"},
        headers={"Authorization": f"Bearer {token}"},
    )
    paper_id = gen.json()["id"]
    paper = client.get(
        f"/student/self-tests/{paper_id}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()

    # intentionally wrong answers
    answers = [{"question_id": q["id"], "content": "Z"} for q in paper["questions"]]
    submit = client.post(
        f"/student/self-tests/{paper_id}/submit",
        json={"answers": answers},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert submit.status_code == 200

    items = db_session.execute(select(WrongBookItem)).scalars().all()
    assert len(items) > 0


def test_student_can_list_wrong_book_items(client, db_session):
    _seed_student(db_session)
    token = _token(client)

    gen = client.post(
        "/student/self-tests/generate",
        json={"subject_code": "english"},
        headers={"Authorization": f"Bearer {token}"},
    )
    paper_id = gen.json()["id"]
    paper = client.get(
        f"/student/self-tests/{paper_id}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()

    answers = [{"question_id": q["id"], "content": "Z"} for q in paper["questions"]]
    submit = client.post(
        f"/student/self-tests/{paper_id}/submit",
        json={"answers": answers},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert submit.status_code == 200

    resp = client.get("/student/wrong-book?subject_code=english", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) > 0


def test_wrong_book_supports_source_type_and_pagination(client, db_session):
    student = _seed_student(db_session)
    token = _token(client)

    # create a placement-sourced item manually to test filtering
    db_session.add(
        WrongBookItem(
            student_user_id=student.id,
            subject_code="english",
            knowledge_node_id=None,
            source_type="placement",
            source_id=uuid.uuid4(),
            question_snapshot_json={"stem": "placement q"},
            answer_snapshot_json={"content": "x"},
            correct_snapshot_json={"answer_key": "y"},
        )
    )
    db_session.commit()

    gen = client.post(
        "/student/self-tests/generate",
        json={"subject_code": "english"},
        headers={"Authorization": f"Bearer {token}"},
    )
    paper_id = gen.json()["id"]
    paper = client.get(
        f"/student/self-tests/{paper_id}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    answers = [{"question_id": q["id"], "content": "Z"} for q in paper["questions"]]
    submit = client.post(
        f"/student/self-tests/{paper_id}/submit",
        json={"answers": answers},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert submit.status_code == 200

    # filter by source_type=self_test
    resp = client.get(
        "/student/wrong-book?subject_code=english&source_type=self_test",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert all(i["source_type"] == "self_test" for i in resp.json())

    # pagination
    page1 = client.get(
        "/student/wrong-book?subject_code=english&limit=2&offset=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert page1.status_code == 200
    assert len(page1.json()) == 2
    page2 = client.get(
        "/student/wrong-book?subject_code=english&limit=2&offset=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert page2.status_code == 200
    assert len(page2.json()) >= 0


def test_wrong_book_supports_knowledge_node_filter(client, db_session):
    student = _seed_student(db_session)
    token = _token(client)

    n1 = SyllabusNode(subject_code="english", name="n1", parent_id=None, weight=1)
    n2 = SyllabusNode(subject_code="english", name="n2", parent_id=None, weight=1)
    db_session.add_all([n1, n2])
    db_session.flush()

    db_session.add_all(
        [
            WrongBookItem(
                student_user_id=student.id,
                subject_code="english",
                knowledge_node_id=n1.id,
                source_type="self_test",
                source_id=uuid.uuid4(),
                question_snapshot_json={"stem": "q1"},
                answer_snapshot_json={"content": "x"},
                correct_snapshot_json={"answer_key": "y"},
            ),
            WrongBookItem(
                student_user_id=student.id,
                subject_code="english",
                knowledge_node_id=n2.id,
                source_type="self_test",
                source_id=uuid.uuid4(),
                question_snapshot_json={"stem": "q2"},
                answer_snapshot_json={"content": "x"},
                correct_snapshot_json={"answer_key": "y"},
            ),
        ]
    )
    db_session.commit()

    resp = client.get(
        f"/student/wrong-book?subject_code=english&knowledge_node_id={n1.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    out = resp.json()
    assert len(out) == 1
    assert out[0]["knowledge_node_id"] == str(n1.id)

