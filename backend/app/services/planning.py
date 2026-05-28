from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MasterPlan, MasterPlanVersion, StudentSubject, SubjectPlan, SubjectPlanVersion


class PlanningService:
    def create_initial_plans(self, db: Session, student_user_id: uuid.UUID) -> None:
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
        if version is None:
            today = date.today()
            daily_time_budget = [
                {"date": str(today + timedelta(days=i)), "minutes": 180} for i in range(7)
            ]
            version = MasterPlanVersion(
                plan_id=master.id,
                version=1,
                source="ai",
                weekly_goals_json=[],
                daily_time_budget_json=daily_time_budget,
            )
            db.add(version)
            db.flush()

        master.current_version_id = version.id

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
                ver = SubjectPlanVersion(
                    plan_id=plan.id,
                    version=1,
                    source="ai",
                    phases_json=[
                        {"title": "起步阶段", "days": 7, "notes": f"{subject_code} 基础巩固"}
                    ],
                )
                db.add(ver)
                db.flush()

            plan.current_version_id = ver.id

        db.commit()

