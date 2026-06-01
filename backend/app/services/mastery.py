import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    MasterySnapshot,
    SelfTestAnswer,
    SelfTestGrade,
    SelfTestPaper,
    SelfTestQuestion,
    SelfTestSubmission,
)
from app.services.grading import GradingService


class MasteryService:
    @staticmethod
    def placement_levels(correct_by_node: dict[uuid.UUID, tuple[int, int]]) -> dict[str, int]:
        """
        P3 rule: level 3 if all correct for a node, else level 1.
        Returns JSON-serializable mapping {knowledge_node_id: level}.
        """
        out: dict[str, int] = {}
        for node_id, (correct, total) in correct_by_node.items():
            if total <= 0:
                continue
            out[str(node_id)] = 3 if correct == total else 1
        return out

    @staticmethod
    def merge_self_test_levels(
        existing: dict[str, int],
        correct_by_node: dict[uuid.UUID, tuple[int, int]],
    ) -> dict[str, int]:
        out = dict(existing)
        for node_id, (correct, total) in correct_by_node.items():
            if total <= 0:
                continue
            key = str(node_id)
            prev = out.get(key, 1)
            if correct == total:
                out[key] = max(prev, 2)
            else:
                out[key] = min(prev, 1)
        return out

    @classmethod
    def update_from_self_test_submission(cls, db: Session, submission_id: uuid.UUID) -> bool:
        submission = db.get(SelfTestSubmission, submission_id)
        if submission is None:
            return False
        grade = db.execute(
            select(SelfTestGrade).where(SelfTestGrade.submission_id == submission_id)
        ).scalar_one_or_none()
        if grade is None:
            return False

        paper_id = submission.paper_id
        questions = {
            q.id: q
            for q in db.execute(
                select(SelfTestQuestion).where(SelfTestQuestion.paper_id == paper_id)
            )
            .scalars()
            .all()
        }
        answers = db.execute(
            select(SelfTestAnswer).where(SelfTestAnswer.submission_id == submission_id)
        ).scalars().all()

        correct_by_node: dict[uuid.UUID, tuple[int, int]] = {}
        for ans in answers:
            q = questions.get(ans.question_id)
            if q is None or q.knowledge_node_id is None:
                continue
            if q.q_type in ("single_choice", "multi_choice", "fill_blank"):
                _, is_correct = GradingService.grade_objective(q, ans.content)
            else:
                detail = (grade.detail_json.get("questions") or [])
                is_correct = False
                for item in detail:
                    if item.get("question_id") == str(q.id):
                        is_correct = bool(item.get("detail", {}).get("is_correct"))
                        break
            node_id = q.knowledge_node_id
            c, t = correct_by_node.get(node_id, (0, 0))
            correct_by_node[node_id] = (c + (1 if is_correct else 0), t + 1)

        if not correct_by_node:
            return False

        paper = db.get(SelfTestPaper, paper_id)
        if paper is None:
            return False

        snap = db.execute(
            select(MasterySnapshot).where(
                MasterySnapshot.student_user_id == submission.student_user_id,
                MasterySnapshot.subject_code == paper.subject_code,
                MasterySnapshot.version == 1,
            )
        ).scalar_one_or_none()
        if snap is None:
            levels = cls.placement_levels(correct_by_node)
            db.add(
                MasterySnapshot(
                    student_user_id=submission.student_user_id,
                    subject_code=paper.subject_code,
                    version=1,
                    mastery_json=levels,
                )
            )
        else:
            snap.mastery_json = cls.merge_self_test_levels(snap.mastery_json or {}, correct_by_node)

        db.flush()
        return True

