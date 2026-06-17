from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    DailyTask,
    MasterPlan,
    MasterPlanVersion,
    PlanReviewJob,
    SelfTestPaper,
    SelfTestSubmission,
    StudentSubject,
    SubjectPlan,
    SubjectPlanVersion,
    User,
    WrongBookItem,
)
from app.schemas.org_student import (
    MasterPlanVersionOut,
    OrgPaperSummaryOut,
    OrgStudentOverviewOut,
    OrgStudentPlansOut,
    SubjectPlanVersionOut,
)
from app.schemas.plan_review_job import PlanReviewJobOut
from app.schemas.report import ReportOverviewOut
from app.schemas.task import DailyTaskOut, TodayTasksOut
from app.services.report import ReportQuery, ReportService


def _plan_review_job_out(job: PlanReviewJob) -> PlanReviewJobOut:
    result = job.result_json or {}
    warnings = list(result.get("warnings") or [])
    scheduled = result.get("scheduled_minutes")
    budget = result.get("budget_minutes")
    over_budget = False
    if isinstance(scheduled, int) and isinstance(budget, int) and scheduled > budget:
        over_budget = True
    return PlanReviewJobOut(
        id=job.id,
        status=job.status,
        subject_code=job.subject_code,
        target_date=job.target_date,
        trigger=job.trigger,
        attempts=job.attempts,
        last_error=job.last_error,
        result_json=job.result_json,
        created_at=job.created_at,
        updated_at=job.updated_at,
        created_count=result.get("created_count"),
        skipped_count=result.get("skipped_count"),
        scheduled_minutes=scheduled,
        budget_minutes=budget,
        over_budget=over_budget,
        warnings=warnings,
    )


class OrgStudentService:
    def overview(self, db: Session, *, student: User) -> OrgStudentOverviewOut:
        subject_codes = list(
            db.execute(
                select(StudentSubject.subject_code).where(
                    StudentSubject.student_user_id == student.id,
                    StudentSubject.enabled.is_(True),
                )
            )
            .scalars()
            .all()
        )

        reports: dict[str, ReportOverviewOut] = {}
        for code in subject_codes:
            reports[code] = ReportService.overview(
                db,
                ReportQuery(student_user_id=student.id, subject_code=code),
            )

        wrong_total = db.execute(
            select(func.count(WrongBookItem.id)).where(
                WrongBookItem.student_user_id == student.id
            )
        ).scalar_one()

        papers = (
            db.execute(
                select(SelfTestPaper)
                .where(SelfTestPaper.student_user_id == student.id)
                .order_by(SelfTestPaper.created_at.desc())
                .limit(10)
            )
            .scalars()
            .all()
        )
        submitted_ids = set(
            db.execute(
                select(SelfTestSubmission.paper_id).where(
                    SelfTestSubmission.student_user_id == student.id
                )
            )
            .scalars()
            .all()
        )
        recent = [
            OrgPaperSummaryOut(
                id=p.id,
                subject_code=p.subject_code,
                status=p.status,
                created_at=p.created_at,
                has_submission=p.id in submitted_ids,
            )
            for p in papers
        ]

        return OrgStudentOverviewOut(
            student_id=student.id,
            name=student.name,
            email=student.email,
            subject_codes=subject_codes,
            wrong_book_total=int(wrong_total),
            reports_by_subject=reports,
            recent_papers=recent,
        )

    def plans(self, db: Session, *, student: User) -> OrgStudentPlansOut:
        master = db.execute(
            select(MasterPlan).where(MasterPlan.student_user_id == student.id)
        ).scalar_one_or_none()

        master_out: MasterPlanVersionOut | None = None
        pending_out: MasterPlanVersionOut | None = None
        master_status: str | None = None
        requires_confirmation = False
        if master is not None:
            master_status = master.status
            requires_confirmation = master.pending_version_id is not None
            if master.current_version_id:
                ver = db.get(MasterPlanVersion, master.current_version_id)
                if ver is not None:
                    master_out = MasterPlanVersionOut.model_validate(ver)
            if master.pending_version_id:
                pending = db.get(MasterPlanVersion, master.pending_version_id)
                if pending is not None:
                    pending_out = MasterPlanVersionOut.model_validate(pending)

        subject_versions: list[SubjectPlanVersionOut] = []
        subject_plans = db.execute(
            select(SubjectPlan).where(SubjectPlan.student_user_id == student.id)
        ).scalars().all()
        for plan in subject_plans:
            if not plan.current_version_id:
                continue
            ver = db.get(SubjectPlanVersion, plan.current_version_id)
            if ver is None:
                continue
            subject_versions.append(
                SubjectPlanVersionOut(
                    id=ver.id,
                    subject_code=plan.subject_code,
                    version=ver.version,
                    source=ver.source,
                    phases_json=ver.phases_json,
                    created_at=ver.created_at,
                )
            )

        review_jobs = (
            db.execute(
                select(PlanReviewJob)
                .where(PlanReviewJob.student_user_id == student.id)
                .order_by(PlanReviewJob.created_at.desc())
                .limit(10)
            )
            .scalars()
            .all()
        )

        return OrgStudentPlansOut(
            master_status=master_status,
            master_version=master_out,
            pending_version=pending_out,
            requires_confirmation=requires_confirmation,
            subject_versions=subject_versions,
            plan_review_jobs=[_plan_review_job_out(j) for j in review_jobs],
        )

    def list_tasks(
        self, db: Session, *, student: User, task_date: date | None = None
    ) -> TodayTasksOut:
        day = task_date or date.today()
        tasks = (
            db.execute(
                select(DailyTask)
                .where(
                    DailyTask.student_user_id == student.id,
                    DailyTask.date == day,
                    DailyTask.status == "pending",
                )
                .order_by(DailyTask.created_at)
            )
            .scalars()
            .all()
        )
        return TodayTasksOut(
            date=day,
            tasks=[DailyTaskOut.model_validate(t) for t in tasks],
        )

    def list_papers(self, db: Session, *, student: User, limit: int = 50) -> list[OrgPaperSummaryOut]:
        papers = (
            db.execute(
                select(SelfTestPaper)
                .where(SelfTestPaper.student_user_id == student.id)
                .order_by(SelfTestPaper.created_at.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )
        submitted_ids = set(
            db.execute(
                select(SelfTestSubmission.paper_id).where(
                    SelfTestSubmission.student_user_id == student.id
                )
            )
            .scalars()
            .all()
        )
        return [
            OrgPaperSummaryOut(
                id=p.id,
                subject_code=p.subject_code,
                status=p.status,
                created_at=p.created_at,
                has_submission=p.id in submitted_ids,
            )
            for p in papers
        ]
