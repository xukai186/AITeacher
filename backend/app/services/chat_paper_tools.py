from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    PlacementAnswer,
    PlacementPaper,
    PlacementQuestion,
    PlacementSubmission,
    SelfTestAnswer,
    SelfTestGrade,
    SelfTestPaper,
    SelfTestQuestion,
    SelfTestSubmission,
)


def explain_question(
    db: Session,
    *,
    student_user_id: uuid.UUID,
    subject_code: str,
    paper_type: str,
    paper_id: uuid.UUID,
    question_seq: int | None = None,
    question_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    if paper_type == "placement":
        paper = db.get(PlacementPaper, paper_id)
        if paper is None or paper.student_user_id != student_user_id or paper.subject_code != subject_code:
            return {"error": "paper not found"}
        q_query = select(PlacementQuestion).where(PlacementQuestion.paper_id == paper_id)
        if question_id is not None:
            q_query = q_query.where(PlacementQuestion.id == question_id)
        elif question_seq is not None:
            q_query = q_query.where(PlacementQuestion.seq == question_seq)
        else:
            return {"error": "question_seq or question_id is required"}
        question = db.execute(q_query).scalar_one_or_none()
        if question is None:
            return {"error": "question not found"}

        student_answer = None
        is_correct = None
        submission = db.execute(
            select(PlacementSubmission).where(
                PlacementSubmission.paper_id == paper_id,
                PlacementSubmission.student_user_id == student_user_id,
            )
        ).scalar_one_or_none()
        if submission is not None:
            answer = db.execute(
                select(PlacementAnswer).where(
                    PlacementAnswer.submission_id == submission.id,
                    PlacementAnswer.question_id == question.id,
                )
            ).scalar_one_or_none()
            if answer is not None:
                student_answer = answer.content
                is_correct = answer.is_correct

        return {
            "paper_type": "placement",
            "paper_id": str(paper.id),
            "question_seq": question.seq,
            "q_type": question.q_type,
            "stem": question.stem,
            "choices": question.choices_json or [],
            "correct_answer": question.answer_key,
            "student_answer": student_answer,
            "is_correct": is_correct,
            "knowledge_node_id": str(question.knowledge_node_id) if question.knowledge_node_id else None,
            "explanation_hint": (
                f"正确答案是 {question.answer_key}。"
                + (
                    "学生答对了。"
                    if is_correct
                    else "学生答错了，可结合考纲知识点讲解干扰项。"
                    if is_correct is False
                    else "学生尚未提交该卷，可先讲解思路与考点。"
                )
            ),
        }

    if paper_type == "self_test":
        paper = db.get(SelfTestPaper, paper_id)
        if paper is None or paper.student_user_id != student_user_id or paper.subject_code != subject_code:
            return {"error": "paper not found"}
        q_query = select(SelfTestQuestion).where(SelfTestQuestion.paper_id == paper_id)
        if question_id is not None:
            q_query = q_query.where(SelfTestQuestion.id == question_id)
        elif question_seq is not None:
            q_query = q_query.where(SelfTestQuestion.seq == question_seq)
        else:
            return {"error": "question_seq or question_id is required"}
        question = db.execute(q_query).scalar_one_or_none()
        if question is None:
            return {"error": "question not found"}

        student_answer = None
        score = None
        grading_detail = None
        submission = db.execute(
            select(SelfTestSubmission).where(
                SelfTestSubmission.paper_id == paper_id,
                SelfTestSubmission.student_user_id == student_user_id,
            )
        ).scalar_one_or_none()
        if submission is not None:
            answer = db.execute(
                select(SelfTestAnswer).where(
                    SelfTestAnswer.submission_id == submission.id,
                    SelfTestAnswer.question_id == question.id,
                )
            ).scalar_one_or_none()
            if answer is not None:
                student_answer = answer.content
            grade = db.execute(
                select(SelfTestGrade).where(SelfTestGrade.submission_id == submission.id)
            ).scalar_one_or_none()
            if grade is not None:
                for item in grade.detail_json.get("questions") or []:
                    if str(item.get("question_id")) == str(question.id):
                        score = item.get("score")
                        grading_detail = item.get("detail")
                        break

        correct = question.answer_key if question.q_type in ("single_choice", "multi_choice", "fill_blank") else None
        return {
            "paper_type": "self_test",
            "paper_id": str(paper.id),
            "question_seq": question.seq,
            "q_type": question.q_type,
            "stem": question.stem,
            "choices": question.choices_json or [],
            "points": question.points,
            "correct_answer": correct,
            "rubric": question.rubric_json,
            "student_answer": student_answer,
            "score": score,
            "grading_detail": grading_detail,
            "knowledge_node_id": str(question.knowledge_node_id) if question.knowledge_node_id else None,
            "explanation_hint": (
                "主观题请结合 rubric 与 grading_detail 组织讲评。"
                if question.q_type not in ("single_choice", "multi_choice", "fill_blank")
                else f"参考答案为 {correct}；得分 {score}/{question.points}。"
            ),
        }

    return {"error": "unsupported paper_type"}
