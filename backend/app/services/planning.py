from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MasterPlan, MasterPlanVersion, StudentSubject, SubjectPlan, SubjectPlanVersion, User
from app.services.exam_profile import ExamProfileService
from app.services.master_plan_activation import MasterPlanActivationService, ProposeResult
from app.services.plan_draft import PlanDraftService


class PlanningService:
    def light_revise_from_profile(
        self, db: Session, student_user_id: uuid.UUID
    ) -> ProposeResult | None:
        master = db.execute(
            select(MasterPlan).where(MasterPlan.student_user_id == student_user_id)
        ).scalar_one_or_none()
        if master is None or master.current_version_id is None:
            self.create_initial_plans(db, student_user_id)
            return None

        draft = PlanDraftService().light_revise_draft(db, student_user_id=student_user_id)
        for subject_code, phases in draft.subject_phases_json.items():
            self._bump_subject_plan_version(
                db,
                student_user_id=student_user_id,
                subject_code=subject_code,
                phases_json=phases,
            )

        activation = MasterPlanActivationService()
        current = db.get(MasterPlanVersion, master.current_version_id)
        weekly_goals = draft.weekly_goals_json
        if current is not None and current.weekly_goals_json:
            weekly_goals = draft.weekly_goals_json or current.weekly_goals_json

        return activation.propose_version(
            db,
            plan=master,
            daily_time_budget_json=draft.daily_time_budget_json,
            weekly_goals_json=weekly_goals,
            source="ai",
        )

    def refresh_tactical_from_roadmap(
        self, db: Session, student_user_id: uuid.UUID, *, today: date | None = None
    ) -> bool:
        """Regenerate 7-day tactical plans using the current roadmap month slice."""
        master = db.execute(
            select(MasterPlan).where(MasterPlan.student_user_id == student_user_id)
        ).scalar_one_or_none()
        if master is None or master.current_version_id is None:
            return False

        subject_codes = list(
            db.execute(
                select(StudentSubject.subject_code).where(
                    StudentSubject.student_user_id == student_user_id,
                    StudentSubject.enabled.is_(True),
                )
            )
            .scalars()
            .all()
        )
        if not subject_codes:
            return False

        student = db.get(User, student_user_id)
        if student is None or student.org_id is None:
            return False

        day = today or date.today()
        draft = PlanDraftService().draft_initial_plans(
            db,
            student_user_id=student_user_id,
            org_id=student.org_id,
            subject_codes=subject_codes,
            today=day,
        )
        for subject_code, phases in draft.subject_phases_json.items():
            self._bump_subject_plan_version(
                db,
                student_user_id=student_user_id,
                subject_code=subject_code,
                phases_json=phases,
            )

        activation = MasterPlanActivationService()
        activation.propose_version(
            db,
            plan=master,
            daily_time_budget_json=draft.daily_time_budget_json,
            weekly_goals_json=draft.weekly_goals_json,
            source="ai",
        )
        return True

    @staticmethod
    def _bump_subject_plan_version(
        db: Session,
        *,
        student_user_id: uuid.UUID,
        subject_code: str,
        phases_json: list[dict],
    ) -> None:
        plan = db.execute(
            select(SubjectPlan).where(
                SubjectPlan.student_user_id == student_user_id,
                SubjectPlan.subject_code == subject_code,
            )
        ).scalar_one_or_none()
        if plan is None:
            return
        current_ver = (
            db.get(SubjectPlanVersion, plan.current_version_id)
            if plan.current_version_id is not None
            else None
        )
        next_version = (current_ver.version + 1) if current_ver is not None else 1
        ver = SubjectPlanVersion(
            plan_id=plan.id,
            version=next_version,
            source="ai",
            phases_json=phases_json,
        )
        db.add(ver)
        db.flush()
        plan.current_version_id = ver.id

    def create_initial_plans(self, db: Session, student_user_id: uuid.UUID) -> None:
        subject_codes = list(
            db.execute(
                select(StudentSubject.subject_code).where(
                    StudentSubject.student_user_id == student_user_id,
                    StudentSubject.enabled.is_(True),
                )
            )
            .scalars()
            .all()
        )
        if not subject_codes:
            return

        master = db.execute(
            select(MasterPlan).where(MasterPlan.student_user_id == student_user_id)
        ).scalar_one_or_none()
        if master is None:
            master = MasterPlan(student_user_id=student_user_id, status="active")
            db.add(master)
            db.flush()

        version = db.execute(
            select(MasterPlanVersion)
            .where(MasterPlanVersion.plan_id == master.id)
            .order_by(MasterPlanVersion.version.desc())
            .limit(1)
        ).scalar_one_or_none()

        needs_master = version is None
        needs_subjects: list[str] = []
        for subject_code in subject_codes:
            plan = db.execute(
                select(SubjectPlan).where(
                    SubjectPlan.student_user_id == student_user_id,
                    SubjectPlan.subject_code == subject_code,
                )
            ).scalar_one_or_none()
            if plan is None:
                needs_subjects.append(subject_code)
                continue
            ver = db.execute(
                select(SubjectPlanVersion)
                .where(SubjectPlanVersion.plan_id == plan.id)
                .order_by(SubjectPlanVersion.version.desc())
                .limit(1)
            ).scalar_one_or_none()
            if ver is None:
                needs_subjects.append(subject_code)

        draft = None
        if needs_master or needs_subjects:
            student = db.get(User, student_user_id)
            org_id = student.org_id if student is not None else None
            exam_profile_svc = ExamProfileService()
            profile_complete = exam_profile_svc.is_complete(db, student_user_id)
            effective_profile = exam_profile_svc.get_effective(db, student_user_id)
            profile_subject_codes = (
                effective_profile.subject_codes if effective_profile is not None else []
            )
            should_draft = profile_complete or bool(profile_subject_codes)
            if org_id is not None and should_draft:
                draft = PlanDraftService().draft_initial_plans(
                    db,
                    student_user_id=student_user_id,
                    org_id=org_id,
                    subject_codes=subject_codes,
                )

        if version is None:
            today = date.today()
            daily_time_budget = (
                draft.daily_time_budget_json
                if draft is not None
                else [
                    {"date": str(today + timedelta(days=i)), "minutes": 180}
                    for i in range(7)
                ]
            )
            weekly_goals = draft.weekly_goals_json if draft is not None else []
            version = MasterPlanVersion(
                plan_id=master.id,
                version=1,
                source="ai",
                weekly_goals_json=weekly_goals,
                daily_time_budget_json=daily_time_budget,
            )
            db.add(version)
            db.flush()

        master.current_version_id = version.id

        for subject_code in subject_codes:
            plan = db.execute(
                select(SubjectPlan).where(
                    SubjectPlan.student_user_id == student_user_id,
                    SubjectPlan.subject_code == subject_code,
                )
            ).scalar_one_or_none()
            if plan is None:
                plan = SubjectPlan(student_user_id=student_user_id, subject_code=subject_code)
                db.add(plan)
                db.flush()

            ver = db.execute(
                select(SubjectPlanVersion)
                .where(SubjectPlanVersion.plan_id == plan.id)
                .order_by(SubjectPlanVersion.version.desc())
                .limit(1)
            ).scalar_one_or_none()
            if ver is None:
                phases = None
                if draft is not None:
                    phases = draft.subject_phases_json.get(subject_code)
                if not phases:
                    phases = [
                        {
                            "title": "起步阶段",
                            "days": 7,
                            "notes": f"{subject_code} 基础巩固",
                        }
                    ]
                ver = SubjectPlanVersion(
                    plan_id=plan.id,
                    version=1,
                    source="ai",
                    phases_json=phases,
                )
                db.add(ver)
                db.flush()

            plan.current_version_id = ver.id

        db.flush()
