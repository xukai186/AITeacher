# Annual Study Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** After all placement exams are submitted, generate a student-confirmed annual study roadmap that drives weekly tactical plans.

**Architecture:** `StudyRoadmap` + `RoadmapGenerationJob` async pipeline; `RoadmapDraftService` builds months from exam profile, placement, syllabus; `PlanDraftService` consumes `RoadmapContextService.current_month_slice` on tactical refresh after confirm.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pytest, React

**Spec:** `docs/superpowers/specs/2026-06-25-annual-study-roadmap-design.md`

---

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/models/study_roadmap.py` | Roadmap + version tables |
| `backend/app/models/roadmap_generation_job.py` | Async job |
| `backend/app/services/roadmap_draft.py` | LLM + rule annual draft |
| `backend/app/services/roadmap_context.py` | Current month slice |
| `backend/app/services/roadmap_activation.py` | Confirm/reject + tactical refresh |
| `backend/app/services/roadmap_generation_jobs.py` | Enqueue/run worker |
| `backend/app/services/placement.py` | `all_subjects_completed`, enqueue on last submit |
| `backend/app/services/plan_draft.py` | Apply month slice to 7-day draft |
| `backend/app/routers/student_roadmap.py` | Student API |
| `frontend/src/pages/student/MasterPlan.tsx` | Roadmap timeline UI |

## Key behavior changes

- Exam profile confirm: no longer calls `create_initial_plans`
- Placement submit: no longer creates master plan per subject; last subject enqueues roadmap job
- Roadmap confirm: creates master/subject plans + daily tasks using month slice
