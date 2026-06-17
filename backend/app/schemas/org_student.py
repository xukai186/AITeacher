import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.plan_review_job import PlanReviewJobOut
from app.schemas.report import ReportOverviewOut
from app.schemas.wrong_book import WrongBookItemOut


class OrgStudentOverviewOut(BaseModel):
    student_id: uuid.UUID
    name: str
    email: str
    subject_codes: list[str]
    wrong_book_total: int
    reports_by_subject: dict[str, ReportOverviewOut]
    recent_papers: list["OrgPaperSummaryOut"]


class OrgPaperSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject_code: str
    status: str
    created_at: datetime
    has_submission: bool = False


class MasterPlanVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    source: str
    weekly_goals_json: list[dict] | None
    daily_time_budget_json: list[dict] | None
    created_at: datetime


class SubjectPlanVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    subject_code: str
    version: int
    source: str
    phases_json: list[dict] | None
    created_at: datetime


class OrgStudentPlansOut(BaseModel):
    master_status: str | None
    master_version: MasterPlanVersionOut | None
    pending_version: MasterPlanVersionOut | None = None
    requires_confirmation: bool = False
    subject_versions: list[SubjectPlanVersionOut]
    plan_review_jobs: list[PlanReviewJobOut] = Field(default_factory=list)


class MasterPlanBudgetPatchIn(BaseModel):
    daily_time_budget_json: list[dict] = Field(min_length=1)


class PaperActionOut(BaseModel):
    paper_id: uuid.UUID
    status: str
    replaced_by_paper_id: uuid.UUID | None = None
