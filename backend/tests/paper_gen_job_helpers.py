from app.services.paper_gen_jobs import PaperGenJobRunner, run_paper_gen_job_if_needed


def finish_paper_gen_jobs(db_session, *, limit: int = 20) -> int:
    return PaperGenJobRunner().run_pending(db_session, limit=limit)


def run_paper_gen_job_if_needed(db_session, job_id) -> None:
    if job_id is not None:
        PaperGenJobRunner().run_pending(db_session, limit=1, job_id=job_id)


def wait_paper_gen_job_api(client, token: str, job_id) -> dict:
    resp = client.get(
        f"/student/paper-gen-jobs/{job_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "succeeded", body
    return body


def _finish_job(db_session, job_id) -> None:
    if job_id is None:
        return
    if db_session is not None:
        run_paper_gen_job_if_needed(db_session, job_id)
        return
    raise AssertionError("job_id requires db_session in tests")


def start_placement_and_wait(
    client,
    token: str,
    payload: dict | None = None,
    *,
    db_session=None,
) -> dict:
    kwargs: dict = {"headers": {"Authorization": f"Bearer {token}"}}
    if payload is not None:
        kwargs["json"] = payload
    start = client.post("/student/placement/start", **kwargs)
    assert start.status_code == 200, start.text
    body = start.json()
    _finish_job(db_session, body.get("gen_job_id"))
    return body


def generate_self_test_and_wait(
    client,
    token: str,
    subject_code: str = "english",
    *,
    db_session=None,
) -> dict:
    gen = client.post(
        "/student/self-tests/generate",
        json={"subject_code": subject_code},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert gen.status_code == 200, gen.text
    body = gen.json()
    _finish_job(db_session, body.get("gen_job_id"))
    return body
