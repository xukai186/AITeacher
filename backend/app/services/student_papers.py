from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    PlacementPaper,
    PlacementResult,
    SelfTestGrade,
    SelfTestPaper,
    SelfTestSubmission,
)
from app.schemas.student_paper import StudentPaperSummaryOut
from app.services.placement import PlacementService

SUBJECT_TITLES = {
    "politics": "政治摸底",
    "english": "英语摸底",
    "math": "数学摸底",
}


class StudentPaperService:
    def list_papers(
        self,
        db: Session,
        *,
        student_user_id: uuid.UUID,
        subject_code: str | None = None,
        paper_type: str | None = None,
        status: str | None = None,
    ) -> list[StudentPaperSummaryOut]:
        rows: list[StudentPaperSummaryOut] = []

        if paper_type in (None, "placement"):
            placement_query = select(PlacementPaper).where(
                PlacementPaper.student_user_id == student_user_id
            )
            if subject_code:
                placement_query = placement_query.where(
                    PlacementPaper.subject_code == subject_code
                )
            placement_papers = (
                db.execute(placement_query.order_by(PlacementPaper.created_at.desc()))
                .scalars()
                .all()
            )
            placement_ids = [p.id for p in placement_papers]
            results_by_paper = {
                row.paper_id: row
                for row in db.execute(
                    select(PlacementResult).where(PlacementResult.paper_id.in_(placement_ids))
                ).scalars()
            } if placement_ids else {}

            for paper in placement_papers:
                effective_status = (
                    "submitted"
                    if PlacementService._is_submitted(db, paper.id, student_user_id)
                    else paper.status
                )
                if status and effective_status != status:
                    continue
                result = results_by_paper.get(paper.id)
                rows.append(
                    StudentPaperSummaryOut(
                        id=paper.id,
                        paper_type="placement",
                        subject_code=paper.subject_code,
                        status=effective_status,
                        title=SUBJECT_TITLES.get(paper.subject_code, f"{paper.subject_code}摸底"),
                        created_at=paper.created_at,
                        total_score=result.total_score if result else None,
                    )
                )

        if paper_type in (None, "self_test"):
            self_test_query = select(SelfTestPaper).where(
                SelfTestPaper.student_user_id == student_user_id
            )
            if subject_code:
                self_test_query = self_test_query.where(
                    SelfTestPaper.subject_code == subject_code
                )
            self_test_papers = (
                db.execute(self_test_query.order_by(SelfTestPaper.created_at.desc()))
                .scalars()
                .all()
            )
            paper_ids = [p.id for p in self_test_papers]
            submissions_by_paper: dict[uuid.UUID, SelfTestSubmission] = {}
            grades_by_submission: dict[uuid.UUID, SelfTestGrade] = {}
            if paper_ids:
                submissions = db.execute(
                    select(SelfTestSubmission).where(
                        SelfTestSubmission.paper_id.in_(paper_ids),
                        SelfTestSubmission.student_user_id == student_user_id,
                    )
                ).scalars()
                submissions_by_paper = {s.paper_id: s for s in submissions}
                submission_ids = [s.id for s in submissions_by_paper.values()]
                if submission_ids:
                    grades_by_submission = {
                        g.submission_id: g
                        for g in db.execute(
                            select(SelfTestGrade).where(
                                SelfTestGrade.submission_id.in_(submission_ids)
                            )
                        ).scalars()
                    }

            for paper in self_test_papers:
                submission = submissions_by_paper.get(paper.id)
                grade = (
                    grades_by_submission.get(submission.id) if submission is not None else None
                )
                if submission is not None and grade is not None:
                    effective_status = "graded"
                elif submission is not None:
                    effective_status = "submitted"
                else:
                    effective_status = paper.status
                if status and effective_status != status:
                    continue
                rows.append(
                    StudentPaperSummaryOut(
                        id=paper.id,
                        paper_type="self_test",
                        subject_code=paper.subject_code,
                        status=effective_status,
                        title=f"{paper.subject_code} 自测",
                        created_at=paper.created_at,
                        submission_id=submission.id if submission else None,
                        total_score=grade.total_score if grade else None,
                    )
                )

        rows.sort(key=lambda row: row.created_at, reverse=True)
        return rows
