from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MasterySnapshot, ModelPolicy, StudentProfile, StudentSubject, User
from app.services.exam_profile import ExamProfileService
from app.services.model_gateway import ModelGateway, ModelGatewayRequest
from app.services.report import ReportQuery, ReportService
from app.services.roadmap_context import MonthSlice, RoadmapContextService

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
        month_slice = RoadmapContextService().current_month_slice(
            db, student_user_id=student_user_id, today=day
        )
        policy = self._policy(db, org_id)
        if policy is not None and policy.provider != "mock":
            try:
                drafted = self._draft_with_llm(
                    db,
                    policy=policy,
                    student_user_id=student_user_id,
                    subject_codes=subject_codes,
                    today=day,
                    month_slice=month_slice,
                )
                if drafted is not None:
                    return self._apply_month_slice(drafted, month_slice, day, db=db)
            except Exception:
                pass
        return self._apply_month_slice(
            self._draft_with_rules(
            db,
            student_user_id=student_user_id,
            subject_codes=subject_codes,
            today=day,
        ),
            month_slice,
            day,
            db=db,
        )

    def light_revise_draft(
        self,
        db: Session,
        *,
        student_user_id: uuid.UUID,
        today: date | None = None,
    ) -> PlanDraft:
        day = today or date.today()
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
        context = self._build_context(
            db, student_user_id=student_user_id, subject_codes=subject_codes
        )
        revise_codes = [
            code
            for code in ("english", "math")
            if code in self._effective_subject_codes(subject_codes, context)
        ]
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
        if context.get("cet_status") == "not_taken":
            weekly_goals.insert(
                0,
                {
                    "title": "强化英语基础",
                    "description": "结合四六级水平，优先词汇语法与基础阅读训练。",
                },
            )
        if context.get("math_mastery_level") == "zero":
            weekly_goals.insert(
                0,
                {
                    "title": "夯实数学基础",
                    "description": "从核心概念与基础题型起步，稳步提升解题能力。",
                },
            )
        extra_minutes = 0
        if context.get("cet_status") == "not_taken":
            extra_minutes += 10
        if context.get("math_mastery_level") == "zero":
            extra_minutes += 10
        daily_time_budget_json = [
            {
                "date": budget_day.isoformat(),
                "minutes": DEFAULT_DAILY_MINUTES + extra_minutes,
            }
            for budget_day in self._budget_dates(day)
        ]
        subject_phases_json = {
            code: self.phases_for_subject(code, context) for code in revise_codes
        }
        draft = PlanDraft(
            weekly_goals_json=weekly_goals,
            daily_time_budget_json=daily_time_budget_json,
            subject_phases_json=subject_phases_json,
        )
        month_slice = RoadmapContextService().current_month_slice(
            db, student_user_id=student_user_id, today=day
        )
        return self._apply_month_slice(draft, month_slice, day, db=db)

    def phases_for_subject(self, code: str, context: dict) -> list[dict]:
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
        if code == "english":
            cet_status = context.get("cet_status")
            if cet_status == "not_taken":
                notes = f"{notes} CET 未通过，强化词汇语法与基础阅读。"
            elif cet_status == "cet4":
                notes = f"{notes} CET4 已通过，重点提升阅读速度与写作结构。"
            elif cet_status == "cet6":
                notes = f"{notes} CET6 已通过，增加高阶阅读、翻译与表达训练。"
        if code == "math":
            mastery = context.get("math_mastery_level")
            if mastery == "zero":
                notes = f"{notes} 数学基础为 zero，从核心概念和基础题型起步。"
            elif mastery == "basic":
                notes = f"{notes} 数学基础为 basic，先稳固公式再推进综合题。"
            elif mastery == "good":
                notes = f"{notes} 数学基础为 good，增加中高难度综合训练。"
            elif mastery == "strong":
                notes = f"{notes} 数学基础为 strong，重点攻克压轴题与限时训练。"
        return [{"title": f"{label}起步阶段", "days": 7, "notes": notes}]

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
        month_slice: MonthSlice | None = None,
    ) -> PlanDraft | None:
        context = self._build_context(db, student_user_id=student_user_id, subject_codes=subject_codes)
        effective_subject_codes = self._effective_subject_codes(subject_codes, context)
        if not effective_subject_codes:
            return None
        budget_dates = [day.isoformat() for day in self._budget_dates(today)]
        current_month_leaves = self._month_leaves_by_subject(db, month_slice)
        prompt_lines = [
            "你是考研机构总规划老师。根据学生摸底与学情，起草首版学习计划。",
            f"考试年份：{context.get('exam_year') or '未设置'}",
            f"报考专业：{context.get('major_name') or '未设置'}",
            f"英语科目：{context.get('english_track') or '未设置'}",
            f"数学科目：{context.get('math_track') or '未设置'}",
            f"CET状态：{context.get('cet_status') or '未填写'}",
            f"数学基础：{context.get('math_mastery_level') or '未填写'}",
            f"启用科目：{json.dumps(effective_subject_codes, ensure_ascii=False)}",
            "学情摘要：",
            json.dumps(context.get("subjects") or [], ensure_ascii=False),
        ]
        if current_month_leaves:
            prompt_lines.append(
                f"当月路线图叶子 current_month_leaves：{json.dumps(current_month_leaves, ensure_ascii=False)}"
            )
        prompt_lines.extend(
            [
                "",
                "规则约束：若数学科目为 none，严禁输出 math 科目阶段。",
                "阶段备注建议：英语结合 CET 状态给出重点；数学结合数学基础给出难度梯度。",
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
                            effective_subject_codes[0]: {
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
        prompt = "\n".join(prompt_lines)
        resp = self._gateway.generate(
            ModelGatewayRequest(
                provider=policy.provider,
                model=policy.model,
                scene="planning",
                prompt=prompt,
                params=policy.params or {},
            )
        )
        return self._parse_llm_draft(
            resp.text, subject_codes=effective_subject_codes, today=today
        )

    def _apply_month_slice(
        self,
        draft: PlanDraft,
        month_slice: MonthSlice | None,
        today: date,
        db: Session | None = None,
    ) -> PlanDraft:
        if month_slice is None:
            return draft
        weekly_goals = list(draft.weekly_goals_json)
        weekly_goals.insert(
            0,
            {
                "title": f"本月：{month_slice.label}",
                "description": "按全年路线图执行本月各科重点。",
            },
        )
        daily_budget: list[dict] = []
        total_weekly_minutes = 0
        for code, block in month_slice.subjects.items():
            if isinstance(block, dict):
                total_weekly_minutes += int(block.get("weekly_hours_hint") or 0) * 60
        daily_minutes = self._clamp_minutes(
            total_weekly_minutes // 7 if total_weekly_minutes else DEFAULT_DAILY_MINUTES
        )
        for budget_day in self._budget_dates(today):
            daily_budget.append({"date": budget_day.isoformat(), "minutes": daily_minutes})
        subject_phases = dict(draft.subject_phases_json)
        for code, block in month_slice.subjects.items():
            if not isinstance(block, dict):
                continue
            focus = str(block.get("focus") or "").strip()
            notes = str(block.get("notes") or "").strip()
            leaf_names: list[str] = []
            ids = block.get("syllabus_node_ids") or []
            if ids and db is not None:
                from app.services.roadmap_resolve import resolve_syllabus_nodes

                leaf_names = [r["name"] for r in resolve_syllabus_nodes(db, list(ids))]
            if not leaf_names:
                leaf_names = [str(n) for n in (block.get("syllabus_nodes") or []) if n]
            leaf_line = f"本月叶子：{'、'.join(leaf_names)}" if leaf_names else ""
            label = SUBJECT_LABELS.get(code, code)
            primary = notes or (f"本月重点：{focus}" if focus else leaf_line)
            if leaf_line and leaf_line not in primary:
                primary = f"{primary}\n{leaf_line}" if primary else leaf_line
            subject_phases[code] = [
                {
                    "title": f"{label} · {month_slice.label}",
                    "days": 7,
                    "notes": primary,
                }
            ]
        return PlanDraft(
            weekly_goals_json=weekly_goals,
            daily_time_budget_json=daily_budget,
            subject_phases_json=subject_phases,
        )

    @staticmethod
    def _month_leaves_by_subject(
        db: Session, month_slice: MonthSlice | None
    ) -> dict[str, list[str]]:
        if month_slice is None:
            return {}
        leaves: dict[str, list[str]] = {}
        for code, block in month_slice.subjects.items():
            if not isinstance(block, dict):
                continue
            ids = block.get("syllabus_node_ids") or []
            if ids:
                from app.services.roadmap_resolve import resolve_syllabus_nodes

                leaves[code] = [r["name"] for r in resolve_syllabus_nodes(db, list(ids))]
            elif block.get("syllabus_nodes"):
                leaves[code] = [str(n) for n in block.get("syllabus_nodes") or [] if n]
        return leaves

    def _draft_with_rules(
        self,
        db: Session,
        *,
        student_user_id: uuid.UUID,
        subject_codes: list[str],
        today: date,
    ) -> PlanDraft:
        context = self._build_context(db, student_user_id=student_user_id, subject_codes=subject_codes)
        effective_subject_codes = self._effective_subject_codes(subject_codes, context)
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
        for code in effective_subject_codes:
            subject_phases_json[code] = self.phases_for_subject(code, context)
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
        effective_profile = ExamProfileService().get_effective(db, student_user_id)
        profile = db.execute(
            select(StudentProfile).where(StudentProfile.user_id == student_user_id)
        ).scalar_one_or_none()
        effective_codes = list(dict.fromkeys(subject_codes))
        if effective_profile is not None and effective_profile.math_track == "none":
            effective_codes = [code for code in effective_codes if code != "math"]
        subjects: list[dict] = []
        for code in effective_codes:
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
                        {
                            "name": w.knowledge_node_name,
                            "wrong_count": w.wrong_count,
                        }
                        for w in overview.weak_nodes[:5]
                    ],
                    "recommendations": overview.recommendations[:3],
                    "mastery_levels": len(mastery or {}),
                }
            )
        return {
            "exam_year": profile.exam_year if profile else None,
            "major_name": effective_profile.major_name if effective_profile else None,
            "english_track": effective_profile.english_track if effective_profile else None,
            "math_track": effective_profile.math_track if effective_profile else None,
            "cet_status": effective_profile.cet_status if effective_profile else None,
            "math_mastery_level": (
                effective_profile.math_mastery_level if effective_profile else None
            ),
            "subjects": subjects,
        }

    @staticmethod
    def _effective_subject_codes(subject_codes: list[str], context: dict) -> list[str]:
        codes = list(dict.fromkeys(subject_codes))
        if context.get("math_track") == "none":
            codes = [code for code in codes if code != "math"]
        return codes

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
