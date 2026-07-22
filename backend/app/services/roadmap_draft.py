from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    MasterySnapshot,
    ModelPolicy,
    PlacementPaper,
    PlacementResult,
    PlacementSubmission,
    StudentProfile,
    StudentSubject,
    SyllabusNode,
    User,
)
from app.seed_syllabus import seed_minimal_syllabus
from app.services.exam_profile import ExamProfileService
from app.services.model_gateway import ModelGateway, ModelGatewayRequest
from app.services.placement_paper_context import (
    leaf_nodes_for_placement,
    resolve_placement_tracks,
    resolve_student_exam_year,
    syllabus_nodes_for_year,
)
from app.services.report import ReportQuery, ReportService

MAX_ROADMAP_MONTHS = 18
SUBJECT_LABELS = {"english": "英语", "math": "数学", "politics": "政治"}


@dataclass(frozen=True)
class RoadmapDraft:
    start_date: date
    end_date: date
    summary_json: dict | None
    months_json: dict
    source: str


class RoadmapDraftService:
    def __init__(self, model_gateway: ModelGateway | None = None) -> None:
        self._gateway = model_gateway or ModelGateway()

    def draft(
        self,
        db: Session,
        *,
        student_user_id: uuid.UUID,
        today: date | None = None,
    ) -> RoadmapDraft:
        day = today or date.today()
        start_date, end_date = self._resolve_date_range(db, student_user_id, day)
        subject_codes = self._enabled_subject_codes(db, student_user_id)
        student = db.get(User, student_user_id)
        org_id = student.org_id if student is not None else None
        policy = self._policy(db, org_id) if org_id is not None else None
        if policy is not None and policy.provider != "mock":
            try:
                drafted = self._draft_with_llm(
                    db,
                    policy=policy,
                    student_user_id=student_user_id,
                    subject_codes=subject_codes,
                    start_date=start_date,
                    end_date=end_date,
                )
                if drafted is not None:
                    return drafted
            except Exception:
                pass
        return self._draft_with_rules(
            db,
            student_user_id=student_user_id,
            subject_codes=subject_codes,
            start_date=start_date,
            end_date=end_date,
        )

    @staticmethod
    def _enabled_subject_codes(db: Session, student_user_id: uuid.UUID) -> list[str]:
        return list(
            db.execute(
                select(StudentSubject.subject_code).where(
                    StudentSubject.student_user_id == student_user_id,
                    StudentSubject.enabled.is_(True),
                )
            )
            .scalars()
            .all()
        )

    @staticmethod
    def _policy(db: Session, org_id: uuid.UUID) -> ModelPolicy | None:
        return db.execute(
            select(ModelPolicy).where(
                ModelPolicy.org_id == org_id,
                ModelPolicy.scene == "planning",
            )
        ).scalar_one_or_none()

    def _resolve_date_range(
        self, db: Session, student_user_id: uuid.UUID, today: date
    ) -> tuple[date, date]:
        profile = db.execute(
            select(StudentProfile).where(StudentProfile.user_id == student_user_id)
        ).scalar_one_or_none()
        if profile is not None and profile.exam_date is not None:
            end = profile.exam_date
            if end < today:
                end = today
            return today, end
        exam_year = profile.exam_year if profile is not None else resolve_student_exam_year(
            db, student_user_id
        )
        end = date(exam_year, 12, 20)
        if end < today:
            end = date(exam_year + 1, 12, 20)
        return today, end

    @staticmethod
    def _ensure_syllabus(db: Session) -> None:
        count = db.execute(select(SyllabusNode.id).limit(1)).scalar_one_or_none()
        if count is None:
            seed_minimal_syllabus(db)
            db.flush()

    def _build_context(
        self,
        db: Session,
        *,
        student_user_id: uuid.UUID,
        subject_codes: list[str],
    ) -> dict:
        self._ensure_syllabus(db)
        effective = ExamProfileService().get_effective(db, student_user_id)
        profile = db.execute(
            select(StudentProfile).where(StudentProfile.user_id == student_user_id)
        ).scalar_one_or_none()
        exam_year = resolve_student_exam_year(db, student_user_id)
        english_track, math_track = resolve_placement_tracks(db, student_user_id=student_user_id)
        codes = list(subject_codes)
        if effective is not None and effective.math_track == "none":
            codes = [c for c in codes if c != "math"]

        placement_by_subject: dict[str, dict] = {}
        for code in codes:
            paper = db.execute(
                select(PlacementPaper).where(
                    PlacementPaper.student_user_id == student_user_id,
                    PlacementPaper.subject_code == code,
                )
            ).scalar_one_or_none()
            if paper is None:
                continue
            submitted = db.execute(
                select(PlacementSubmission.id).where(
                    PlacementSubmission.paper_id == paper.id,
                    PlacementSubmission.student_user_id == student_user_id,
                )
            ).scalar_one_or_none()
            if submitted is None:
                continue
            result = db.execute(
                select(PlacementResult).where(PlacementResult.paper_id == paper.id)
            ).scalar_one_or_none()
            placement_by_subject[code] = {
                "total_score": result.total_score if result else None,
                "mastery_json": result.mastery_json if result else {},
            }

        syllabus_outline: dict[str, list[dict]] = {}
        for code in codes:
            leaves = leaf_nodes_for_placement(
                db,
                subject_code=code,
                exam_year=exam_year,
                english_track=english_track,
                math_track=math_track,
            )
            by_id = {
                n.id: n
                for n in syllabus_nodes_for_year(db, subject_code=code, exam_year=exam_year)
            }
            syllabus_outline[code] = []
            for n in leaves:
                parent = by_id.get(n.parent_id) if n.parent_id else None
                syllabus_outline[code].append(
                    {
                        "id": str(n.id),
                        "name": n.name,
                        "parent_name": parent.name if parent else None,
                    }
                )

        subjects_ctx: list[dict] = []
        for code in codes:
            overview = ReportService.overview(
                db, ReportQuery(student_user_id=student_user_id, subject_code=code)
            )
            mastery = db.execute(
                select(MasterySnapshot.mastery_json).where(
                    MasterySnapshot.student_user_id == student_user_id,
                    MasterySnapshot.subject_code == code,
                )
            ).scalar_one_or_none()
            subjects_ctx.append(
                {
                    "subject_code": code,
                    "weak_node_count": len(overview.weak_nodes),
                    "weak_nodes": [
                        {"name": w.knowledge_node_name, "wrong_count": w.wrong_count}
                        for w in overview.weak_nodes[:5]
                    ],
                    "placement": placement_by_subject.get(code),
                    "mastery_levels": len(mastery or {}),
                }
            )

        return {
            "exam_year": exam_year,
            "exam_date": profile.exam_date.isoformat() if profile and profile.exam_date else None,
            "major_name": effective.major_name if effective else None,
            "major_category_code": effective.major_category_code if effective else None,
            "english_track": english_track,
            "math_track": math_track,
            "cet_status": effective.cet_status if effective else None,
            "math_mastery_level": effective.math_mastery_level if effective else None,
            "subject_codes": codes,
            "syllabus_outline": syllabus_outline,
            "subjects": subjects_ctx,
        }

    def _month_keys(self, start_date: date, end_date: date) -> list[str]:
        keys: list[str] = []
        y, m = start_date.year, start_date.month
        end_y, end_m = end_date.year, end_date.month
        while (y < end_y or (y == end_y and m <= end_m)) and len(keys) < MAX_ROADMAP_MONTHS:
            keys.append(f"{y:04d}-{m:02d}")
            m += 1
            if m > 12:
                m = 1
                y += 1
        if not keys:
            keys.append(start_date.strftime("%Y-%m"))
        return keys

    def _draft_with_rules(
        self,
        db: Session,
        *,
        student_user_id: uuid.UUID,
        subject_codes: list[str],
        start_date: date,
        end_date: date,
    ) -> RoadmapDraft:
        context = self._build_context(
            db, student_user_id=student_user_id, subject_codes=subject_codes
        )
        codes = context["subject_codes"]
        month_keys = self._month_keys(start_date, end_date)
        months: list[dict] = []

        PER_MONTH = 2
        nodes_by_subject: dict[str, list[dict]] = {
            code: list(context["syllabus_outline"].get(code, []))
            for code in codes
        }
        offsets = {code: 0 for code in codes}
        for i, month_key in enumerate(month_keys):
            subjects_block: dict[str, dict] = {}
            for code in codes:
                names = nodes_by_subject[code]
                chunk: list[dict] = []
                if names:
                    start = offsets[code]
                    for _ in range(PER_MONTH):
                        pos = start + len(chunk)
                        if pos >= len(names):
                            break
                        chunk.append(names[pos])
                    offsets[code] = start + len(chunk)

                if not chunk:
                    continue

                ids: list[str] = []
                seen_local: set[str] = set()
                for item in chunk:
                    if item["id"] not in seen_local:
                        seen_local.add(item["id"])
                        ids.append(item["id"])
                if not ids:
                    continue
                label_names = "、".join(item["name"] for item in chunk)
                weekly_hours = self._default_weekly_hours(code, context)
                subjects_block[code] = {
                    "focus": f"{SUBJECT_LABELS.get(code, code)} · {label_names}",
                    "syllabus_node_ids": ids[:4],
                    "weekly_hours_hint": weekly_hours,
                    "notes": f"本月重点学习 {label_names}，按周完成系统任务。",
                }
            months.append(
                {
                    "month": month_key,
                    "label": "冲刺月" if i == len(month_keys) - 1 and len(month_keys) == 1 else f"第{i + 1}阶段",
                    "subjects": subjects_block,
                    "milestones": [],
                }
            )

        return RoadmapDraft(
            start_date=start_date,
            end_date=end_date,
            summary_json={"text": "按考纲叶子知识点逐月推进，薄弱科目在战术层自动加权。"},
            months_json={"months": months},
            source="rule",
        )

    @staticmethod
    def _default_weekly_hours(code: str, context: dict) -> int:
        if code == "english":
            cet = context.get("cet_status")
            if cet == "not_taken":
                return 14
            if cet == "cet6":
                return 10
            return 12
        if code == "math":
            level = context.get("math_mastery_level")
            if level == "zero":
                return 16
            if level == "strong":
                return 10
            return 14
        return 8

    def _draft_with_llm(
        self,
        db: Session,
        *,
        policy: ModelPolicy,
        student_user_id: uuid.UUID,
        subject_codes: list[str],
        start_date: date,
        end_date: date,
    ) -> RoadmapDraft | None:
        context = self._build_context(
            db, student_user_id=student_user_id, subject_codes=subject_codes
        )
        month_keys = self._month_keys(start_date, end_date)
        prompt = "\n".join(
            [
                "你是考研机构总规划老师。根据学生档案、摸底与考纲，起草从今天到考试日的全年学习路线图。",
                f"备考区间：{start_date.isoformat()} 至 {end_date.isoformat()}",
                f"月份列表：{json.dumps(month_keys, ensure_ascii=False)}",
                f"报考专业：{context.get('major_name') or '未设置'}",
                f"英语卷种：{context.get('english_track')}",
                f"数学卷种：{context.get('math_track')}",
                f"CET：{context.get('cet_status')}",
                f"数学基础：{context.get('math_mastery_level')}",
                f"科目：{json.dumps(context.get('subject_codes'), ensure_ascii=False)}",
                "考纲叶子知识点（syllabus_node_ids 只能从中选取 id，含 parent_name 便于分组）：",
                json.dumps(context.get("syllabus_outline"), ensure_ascii=False),
                "学情与摸底：",
                json.dumps(context.get("subjects"), ensure_ascii=False),
                "规则：math_track=none 禁止 math；每月每科 2-4 个 syllabus_node_ids（来自 outline 的 id）；"
                "同一叶子 id 不可跨月重复；含 weekly_hours_hint；不要输出 syllabus_nodes。",
                "只输出 STRICT JSON：",
                json.dumps(
                    {
                        "summary": {"text": "整体策略"},
                        "months": [
                            {
                                "month": month_keys[0],
                                "label": "基础月",
                                "subjects": {
                                    context["subject_codes"][0]: {
                                        "focus": "学习重点",
                                        "syllabus_node_ids": ["uuid-from-outline"],
                                        "weekly_hours_hint": 12,
                                        "notes": "说明",
                                    }
                                },
                                "milestones": ["里程碑"],
                            }
                        ],
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
        return self._parse_llm_draft(
            resp.text,
            subject_codes=context["subject_codes"],
            start_date=start_date,
            end_date=end_date,
            month_keys=month_keys,
            allowed_ids_by_subject={
                code: {n["id"] for n in context["syllabus_outline"].get(code, [])}
                for code in context["subject_codes"]
            },
        )

    def _parse_llm_draft(
        self,
        raw: str,
        *,
        subject_codes: list[str],
        start_date: date,
        end_date: date,
        month_keys: list[str],
        allowed_ids_by_subject: dict[str, set[str]],
    ) -> RoadmapDraft | None:
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        data = json.loads(text)
        if not isinstance(data, dict):
            return None
        months_raw = data.get("months") or []
        if not isinstance(months_raw, list) or not months_raw:
            return None
        months: list[dict] = []
        seen_ids: set[str] = set()
        for item in months_raw[:MAX_ROADMAP_MONTHS]:
            if not isinstance(item, dict):
                continue
            month = str(item.get("month") or "").strip()
            if not month:
                continue
            label = str(item.get("label") or month).strip()
            subjects_raw = item.get("subjects") or {}
            subjects_out: dict[str, dict] = {}
            if isinstance(subjects_raw, dict):
                for code in subject_codes:
                    block = subjects_raw.get(code)
                    if not isinstance(block, dict):
                        continue
                    focus = str(block.get("focus") or "").strip()
                    allowed = allowed_ids_by_subject.get(code, set())
                    ids_raw = block.get("syllabus_node_ids") or []
                    ids: list[str] = []
                    for raw_id in ids_raw:
                        nid = str(raw_id).strip()
                        if not nid:
                            continue
                        if nid not in allowed:
                            return None
                        ids.append(nid)
                    ids = ids[:4]
                    if not ids:
                        return None
                    for nid in ids:
                        if nid in seen_ids:
                            return None
                        seen_ids.add(nid)
                    if not focus:
                        focus = "、".join(ids)
                    subjects_out[code] = {
                        "focus": focus,
                        "syllabus_node_ids": ids,
                        "weekly_hours_hint": int(block.get("weekly_hours_hint") or 12),
                        "notes": str(block.get("notes") or "").strip(),
                    }
            if subjects_out:
                milestones = item.get("milestones") or []
                months.append(
                    {
                        "month": month,
                        "label": label,
                        "subjects": subjects_out,
                        "milestones": [str(m) for m in milestones if str(m).strip()][:3],
                    }
                )
        if not months:
            return None
        summary = data.get("summary")
        summary_json = summary if isinstance(summary, dict) else None
        return RoadmapDraft(
            start_date=start_date,
            end_date=end_date,
            summary_json=summary_json,
            months_json={"months": months},
            source="ai",
        )
