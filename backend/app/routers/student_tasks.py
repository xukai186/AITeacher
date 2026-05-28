from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.permissions import require_roles
from app.database import get_db
from app.models import DailyTask, User, UserRole
from app.schemas.task import TodayTasksOut

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
            .where(DailyTask.student_user_id == student.id, DailyTask.date == today)
            .order_by(DailyTask.created_at)
        )
        .scalars()
        .all()
    )
    return TodayTasksOut(date=today, tasks=list(tasks))

