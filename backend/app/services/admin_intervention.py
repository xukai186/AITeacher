from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyTask, MasterPlan, MasterPlanVersion, SelfTestPaper, User
from app.schemas.org_student import MasterPlanVersionOut, PaperActionOut
from app.services.audit import record_audit
from app.services.self_test import SelfTestService


class AdminInterventionService:
    def update_master_budget(
        self,
        db: Session,
        *,
        actor: User,
        student: User,
        daily_time_budget_json: list[dict],
    ) -> MasterPlanVersionOut:
        master = db.execute(
            select(MasterPlan).where(MasterPlan.student_user_id == student.id)
        ).scalar_one_or_none()
        if master is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "master plan not found")

        current = None
        if master.current_version_id:
            current = db.get(MasterPlanVersion, master.current_version_id)

        next_ver = 1
        if current is not None:
            next_ver = current.version + 1

        version = MasterPlanVersion(
            plan_id=master.id,
            version=next_ver,
            source="admin",
            weekly_goals_json=current.weekly_goals_json if current else [],
            daily_time_budget_json=daily_time_budget_json,
        )
        db.add(version)
        db.flush()
        master.current_version_id = version.id
        master.pending_version_id = None

        record_audit(
            db,
            actor=actor,
            action="plan.master_budget_update",
            target_type="student",
            target_id=str(student.id),
            after={"version": next_ver, "daily_time_budget_json": daily_time_budget_json},
        )
        db.flush()
        return MasterPlanVersionOut.model_validate(version)

    def lock_paper(
        self,
        db: Session,
        *,
        actor: User,
        student: User,
        paper_id: uuid.UUID,
    ) -> PaperActionOut:
        paper = self._get_student_paper(db, student, paper_id)
        if paper.status in ("replaced",):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "paper already replaced")

        before = paper.status
        paper.status = "locked"
        record_audit(
            db,
            actor=actor,
            action="paper.lock",
            target_type="self_test_paper",
            target_id=str(paper.id),
            before={"status": before},
            after={"status": "locked"},
        )
        db.flush()
        return PaperActionOut(paper_id=paper.id, status=paper.status)

    def replace_paper(
        self,
        db: Session,
        *,
        actor: User,
        student: User,
        paper_id: uuid.UUID,
    ) -> PaperActionOut:
        paper = self._get_student_paper(db, student, paper_id)
        if paper.status == "replaced":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "paper already replaced")

        before_status = paper.status
        paper.status = "replaced"
        db.flush()

        from app.services.paper_gen_jobs import run_paper_gen_job_if_needed

        new_paper, gen_job_id = SelfTestService.generate(
            db, student.id, paper.subject_code, skip_eligibility=True
        )
        run_paper_gen_job_if_needed(db, gen_job_id)

        tasks = db.execute(
            select(DailyTask).where(
                DailyTask.student_user_id == student.id,
                DailyTask.type == "self_test",
            )
        ).scalars().all()
        for task in tasks:
            payload = task.payload_json or {}
            if payload.get("paper_id") == str(paper.id):
                task.payload_json = {**payload, "paper_id": str(new_paper.id), "replaced_from": str(paper.id)}

        record_audit(
            db,
            actor=actor,
            action="paper.replace",
            target_type="self_test_paper",
            target_id=str(paper.id),
            before={"status": before_status},
            after={"status": "replaced", "new_paper_id": str(new_paper.id)},
        )
        db.flush()
        return PaperActionOut(
            paper_id=paper.id,
            status=paper.status,
            replaced_by_paper_id=new_paper.id,
        )

    @staticmethod
    def _get_student_paper(db: Session, student: User, paper_id: uuid.UUID) -> SelfTestPaper:
        paper = db.get(SelfTestPaper, paper_id)
        if paper is None or paper.student_user_id != student.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "paper not found")
        return paper
