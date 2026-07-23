import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class SyllabusNodeResolvedOut(BaseModel):
    id: str | None = None
    name: str
    parent_name: str | None = None


class RoadmapMonthSubjectOut(BaseModel):
    focus: str = ""
    syllabus_nodes: list[str] = Field(default_factory=list)
    syllabus_node_ids: list[str] = Field(default_factory=list)
    syllabus_nodes_resolved: list[SyllabusNodeResolvedOut] = Field(default_factory=list)
    weekly_hours_hint: int | None = None
    notes: str = ""


class RoadmapMonthOut(BaseModel):
    month: str
    label: str = ""
    subjects: dict[str, RoadmapMonthSubjectOut] = Field(default_factory=dict)
    milestones: list[str] = Field(default_factory=list)


class StudyRoadmapVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    source: str
    start_date: date
    end_date: date
    summary_json: dict | None = None
    months_json: dict
    created_at: datetime


class RoadmapGenerationJobOut(BaseModel):
    id: str
    status: str
    error_message: str | None = None
    roadmap_version_id: str | None = None


class StudyRoadmapStateOut(BaseModel):
    roadmap_id: uuid.UUID | None = None
    status: str | None = None
    active_version: StudyRoadmapVersionOut | None = None
    pending_version: StudyRoadmapVersionOut | None = None
    generation_job: RoadmapGenerationJobOut | None = None


class RoadmapConfirmOut(BaseModel):
    active_version: StudyRoadmapVersionOut
    message: str = "全年计划已生效"


class RoadmapRegenerateOut(BaseModel):
    job_id: uuid.UUID
    created: bool
