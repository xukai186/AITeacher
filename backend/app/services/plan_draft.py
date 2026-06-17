from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MasterySnapshot, ModelPolicy, StudentProfile, User
from app.services.model_gateway import ModelGateway, ModelGatewayRequest
from app.services.report import ReportQuery, ReportService

SUBJECT_LABELS: dict[str, str] = {
    "english": "英语",
    "math": "数学",
    "politics": "政治",
}

DEFAULT_DAILY_MINUTES = 180
MIN_DAILY_MINUTES = 60
MAX_DAILY_MINUTES = 360


@dataclass(frozen=True)
class PlanDraft:
    weekly_goals_json: list[dict]
    daily_time_budget_json: list[dict]
    subject_phases_json: dict[str, list[dict]]


class PlanDraftService:
    def __init__(self, model_gateway: ModelGateway | None = None) -> None:
        self._gateway = model_gateway or ModelGateway()

    def draft_initial_plans(
        self,
        db: Session,
        *,
        student_user_id: uuid.UUID,
        org_id: uuid.UUID,
        subject_codes: list[str],
        today: date | None = None,
    ) -> PlanDraft:
        day = today or date.today()
        policy = self._policy(db, org_id)
        if policy is not None and policy.provider != "mock":
            try:
                drafted = self._draft_with_llm(
                    db,
                    policy=policy,
                    student_user_id=student_user_id,
                    subject_codes=subject_codes,
                    today=day,
                )
                if drafted is not None:
                    return drafted
            except Exception:
                pass
        return self._draft_with_rules(
            db,
            student_user_id=student_user_id,
            subject_codes=subject_codes,
            today=day,
        )

    @staticmethod
    def _policy(db: Session, org_id: uuid.UUID) -> ModelPolicy | None:
        return db.execute(
            select(ModelPolicy).where(
                ModelPolicy.org_id == org_id,
                ModelPolicy.scene == "planning",
            )
        ).scalar_one_or_none()

    def _draft_with_llm(
        self,
        db: Session,
        *,
        policy: ModelPolicy,
        student_user_id: uuid.UUID,
        subject_codes: list[str],
        today: date,
    ) -> PlanDraft | None:
        context = self._build_context(db, student_user_id=student_user_id, subject_codes=subject_codes)
        budget_dates = [day.isoformat() for day in self._budget_dates(today)]
        prompt = "\n".join(
            [
                "你是考研机构总规划老师。根据学生摸底与学情，起草首版学习计划。",
                f"考试年份：{context.get('exam_year') or '未设置'}",
                f"启用科目：{json.dumps(subject_codes, ensure_ascii=False)}",
                "学情摘要：",
                json.dumps(context.get("subjects") or [], ensure_ascii=False),
                "",
                f"请为接下来 7 天（{budget_dates[0]} 至 {budget_dates[-1]}）生成计划。",
                "只输出 STRICT JSON，不要 markdown：",
                json.dumps(
                    {
                        "weekly_goals": [
                            {"title": "周目标标题", "description": "1-2 句说明"}
                        ],
                        "daily_time_budget": [
                            {"date": budget_dates[0], "minutes": DEFAULT_DAILY_MINUTES}
                        ],
                        "subjects": {
                            subject_codes[0] if subject_codes else "english": {
                                "phases": [
                                    {
                                        "title": "阶段名称",
                                        "days": 7,
                                        "notes": "本阶段学习重点",
                                    }
                                ]
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
            ]
        )
        resp = self._gateway.generate(
            ModelGatewayRequest(
                provider=policy.provider,
                model=policy.model,
                scene="planning",
                prompt=prompt,
                params=policy.params or {},
            )
        )
        return self._parse_llm_draft(resp.text, subject_codes=subject_codes, today=today)

    def _draft_with_rules(
        self,
        db: Session,
        *,
        student_user_id: uuid.UUID,
        subject_codes: list[str],
        today: date,
    ) -> PlanDraft:
        context = self._build_context(db, student_user_id=student_user_id, subject_codes=subject_codes)
        weak_subjects = [
            s["subject_code"]
            for s in context.get("subjects", [])
            if int(s.get("weak_node_count") or 0) > 0
        ]
        focus = "、".join(SUBJECT_LABELS.get(c, c) for c in weak_subjects[:2]) or "各科基础"
        weekly_goals = [
            {
                "title": "夯实薄弱知识点",
                "description": f"本周优先巩固 {focus}，按每日任务完成学习与错题复习。",
            },
            {
                "title": "保持稳定学习节奏",
                "description": "每日完成系统安排的学习与自测任务，及时查看学情反馈。",
            },
        ]
        daily_time_budget_json = [
            {"date": day.isoformat(), "minutes": DEFAULT_DAILY_MINUTES}
            for day in self._budget_dates(today)
        ]
        subject_phases_json: dict[str, list[dict]] = {}
        for code in subject_codes:
            label = SUBJECT_LABELS.get(code, code)
            weak = next(
                (s for s in context.get("subjects", []) if s["subject_code"] == code),
                None,
            )
            weak_count = int(weak.get("weak_node_count") or 0) if weak else 0
            notes = (
                f"针对 {weak_count} 个薄弱知识点安排基础练习与回顾。"
                if weak_count
                else f"{label} 基础巩固与题型熟悉。"
            )
            subject_phases_json[code] = [
                {"title": f"{label}起步阶段", "days": 7, "notes": notes}
            ]
        return PlanDraft(
            weekly_goals_json=weekly_goals,
            daily_time_budget_json=daily_time_budget_json,
            subject_phases_json=subject_phases_json,
        )

    def _build_context(
        self,
        db: Session,
        *,
        student_user_id: uuid.UUID,
        subject_codes: list[str],
    ) -> dict:
        profile = db.execute(
            select(StudentProfile).where(StudentProfile.user_id == student_user_id)
        ).scalar_one_or_none()
        subjects: list[dict] = []
        for code in subject_codes:
            overview = ReportService.overview(
                db,
                ReportQuery(student_user_id=student_user_id, subject_code=code),
            )
            mastery = db.execute(
                select(MasterySnapshot.mastery_json).where(
                    MasterySnapshot.student_user_id == student_user_id,
                    MasterySnapshot.subject_code == code,
                )
            ).scalar_one_or_none()
            subjects.append(
                {
                    "subject_code": code,
                    "label": SUBJECT_LABELS.get(code, code),
                    "weak_node_count": len(overview.weak_nodes),
                    "weak_nodes": [
                        {"name": w.name, "level": w.level} for w in overview.weak_nodes[:5]
                    ],
                    "recommendations": overview.recommendations[:3],
                    "mastery_levels": len(mastery or {}),
                }
            )
        return {
            "exam_year": profile.exam_year if profile else None,
            "subjects": subjects,
        }

    @staticmethod
    def _budget_dates(today: date) -> list[date]:
        return [today + timedelta(days=i) for i in range(7)]

    def _parse_llm_draft(
        self,
        raw: str,
        *,
        subject_codes: list[str],
        today: date,
    ) -> PlanDraft | None:
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        data = json.loads(text)
        if not isinstance(data, dict):
            return None

        weekly_raw = data.get("weekly_goals") or []
        weekly_goals_json: list[dict] = []
        if isinstance(weekly_raw, list):
            for item in weekly_raw[:5]:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "").strip()
                if not title:
                    continue
                weekly_goals_json.append(
                    {
                        "title": title,
                        "description": str(item.get("description") or "").strip(),
                    }
                )

        budget_dates = [d.isoformat() for d in self._budget_dates(today)]
        budget_by_date = {
            str(entry.get("date")): self._clamp_minutes(entry.get("minutes"))
            for entry in (data.get("daily_time_budget") or [])
            if isinstance(entry, dict) and entry.get("date")
        }
        daily_time_budget_json = [
            {
                "date": day,
                "minutes": budget_by_date.get(day, DEFAULT_DAILY_MINUTES),
            }
            for day in budget_dates
        ]

        subjects_raw = data.get("subjects") or {}
        subject_phases_json: dict[str, list[dict]] = {}
        if isinstance(subjects_raw, dict):
            for code in subject_codes:
                block = subjects_raw.get(code) or {}
                phases_raw = block.get("phases") if isinstance(block, dict) else []
                phases: list[dict] = []
                if isinstance(phases_raw, list):
                    for phase in phases_raw[:4]:
                        if not isinstance(phase, dict):
                            continue
                        title = str(phase.get("title") or "").strip()
                        if not title:
                            continue
                        days = int(phase.get("days") or 7)
                        phases.append(
                            {
                                "title": title,
                                "days": max(1, min(days, 30)),
                                "notes": str(phase.get("notes") or "").strip(),
                            }
                        )
                if phases:
                    subject_phases_json[code] = phases

        if not weekly_goals_json or not subject_phases_json:
            return None

        for code in subject_codes:
            if code not in subject_phases_json:
                label = SUBJECT_LABELS.get(code, code)
                subject_phases_json[code] = [
                    {"title": f"{label}基础阶段", "days": 7, "notes": f"{label} 按计划推进"}
                ]

        return PlanDraft(
            weekly_goals_json=weekly_goals_json,
            daily_time_budget_json=daily_time_budget_json,
            subject_phases_json=subject_phases_json,
        )

    @staticmethod
    def _clamp_minutes(value: object) -> int:
        try:
            minutes = int(value)
        except (TypeError, ValueError):
            minutes = DEFAULT_DAILY_MINUTES
        return max(MIN_DAILY_MINUTES, min(MAX_DAILY_MINUTES, minutes))
