import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.permissions import require_roles
from app.database import get_db
from app.models import DailyTask, User, UserRole
from app.schemas.task import DailyTaskOut, TodayTasksOut
from app.services.learning_events import LearningEventService

router = APIRouter(prefix="/student/tasks", tags=["student-tasks"])


@router.get("/today", response_model=TodayTasksOut)
def get_today_tasks(
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> TodayTasksOut:
    today = date.today()
    tasks = (
        db.execute(
            select(DailyTask)
            .where(
                DailyTask.student_user_id == student.id,
                DailyTask.date == today,
                DailyTask.status == "pending",
            )
            .order_by(DailyTask.created_at)
        )
        .scalars()
        .all()
    )
    return TodayTasksOut(date=today, tasks=list(tasks))


@router.post("/{task_id}/complete", response_model=DailyTaskOut)
def complete_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    student: User = Depends(require_roles(UserRole.student)),
) -> DailyTaskOut:
    task = db.get(DailyTask, task_id)
    if task is None or task.student_user_id != student.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "task not found")
    if task.status == "cancelled":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "task is cancelled")

    task.status = "completed"
    LearningEventService.record(
        db,
        student_user_id=student.id,
        event_type="task_done",
        subject_code=task.subject_code,
        ref_type="daily_task",
        ref_id=task.id,
        payload={"task_type": task.type, "date": task.date.isoformat()},
    )
    db.commit()
    db.refresh(task)
    return DailyTaskOut.model_validate(task)

