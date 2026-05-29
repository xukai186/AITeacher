from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.services.agent_context import SubjectContext, get_subject_context
from app.services.subject_agent import ApplyRecommendationsResult, SubjectAgentService

ToolHandler = Callable[..., Any]


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    handler: ToolHandler


class AgentToolRegistry:
    """学科 / 总规划 Agent 可调用的内部工具（学生不可直接调用）。"""

    def __init__(self) -> None:
        self._tools: dict[str, AgentTool] = {
            "get_subject_context": AgentTool(
                name="get_subject_context",
                description="读取本科目学情摘要（错题来源、薄弱点、建议条数）",
                handler=self._get_subject_context,
            ),
            "generate_daily_tasks": AgentTool(
                name="generate_daily_tasks",
                description="根据学情建议为指定日期生成每日任务（幂等）",
                handler=self._generate_daily_tasks,
            ),
        }

    def names(self) -> list[str]:
        return list(self._tools.keys())

    def call(self, db: Session, name: str, **kwargs: Any) -> Any:
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"unknown tool: {name}")
        return tool.handler(db, **kwargs)

    @staticmethod
    def _get_subject_context(
        db: Session,
        *,
        student_user_id: uuid.UUID,
        subject_code: str,
    ) -> SubjectContext:
        return get_subject_context(db, student_user_id=student_user_id, subject_code=subject_code)

    @staticmethod
    def _generate_daily_tasks(
        db: Session,
        *,
        student_user_id: uuid.UUID,
        subject_code: str,
        target_date: date | None = None,
    ) -> ApplyRecommendationsResult:
        return SubjectAgentService().apply_report_recommendations(
            db,
            student_user_id=student_user_id,
            subject_code=subject_code,
            target_date=target_date,
        )


default_tool_registry = AgentToolRegistry()
