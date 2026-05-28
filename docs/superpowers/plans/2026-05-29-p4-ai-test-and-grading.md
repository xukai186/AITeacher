# P4 — AI Self-Test + Grading + Wrong Book (錯題集) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the “生成自测卷 → 学生作答提交 → 自动批改（含主观题）→ 结果落库 → 错题入库（錯題集）→ 基于错题的薄弱点聚合”闭环，并在学生工作台能完成一套自测与查看结果（最小可用）。

**Architecture:** Extend P3 with new DB entities for tests, submissions, grading artifacts, and wrong-book items. Implement a grading pipeline that can grade objective questions deterministically and subjective questions via `ModelGateway` (scene: `grading`), with rubric + structured JSON output enforced server-side. Persist all raw grading evidence and normalized scores to support auditing and later analytics.

**Tech Stack:** Existing stack (FastAPI + SQLAlchemy + Alembic + pytest; React + TanStack Query + vitest). Reuse `ModelGateway` with org-scoped policy for grading.

---

## Scope Check (P4)

P4 **要做**：
- 自测卷（按科目）生成（P4 可先用 deterministic/mock + 最小 LLM 参与）
- 作答提交（支持客观 + 主观）
- 自动批改与得分（客观：规则；主观：`ModelGateway`）
- 错题入库：按题目维度保存错误答案、正确答案/解析、关联知识点
- 薄弱点聚合（最小：按知识点计数/正确率）
- 学生端：入口、做题、提交、看到得分与错题列表（MVP）
- 后台：查看某学生的错题概览（只读 MVP）

P4 **不做**（留到后续）：
- 高质量题库、复杂题型（材料题、多小问等）
- 复杂学习计划重排、调度器、精细化学情图表
- 多次重做/对比分析（先支持最小的多次提交版本化）

---

## Domain Model (P4)

### Test paper (self-test)
- `SelfTestPaper(id, student_user_id, subject_code, source, status, created_at)`
- `SelfTestQuestion(id, paper_id, seq, knowledge_node_id, q_type, stem, choices_json, answer_key, points, rubric_json)`

### Submission + grading
- `SelfTestSubmission(id, paper_id, student_user_id, status, submitted_at, created_at)`
- `SelfTestAnswer(id, submission_id, question_id, content, created_at)`
- `SelfTestGrade(id, submission_id, total_score, detail_json, created_at)`
  - `detail_json` stores per-question grading: score, is_correct, feedback, extracted key points, etc.

### Wrong book (錯題集)
- `WrongBookItem(id, student_user_id, subject_code, knowledge_node_id, source_type, source_id, question_snapshot_json, answer_snapshot_json, correct_snapshot_json, created_at)`
  - `source_type`: `"placement" | "self_test"`
  - `source_id`: paper/question/submission linkage ids

### Weakness aggregation (minimal)
- `WeaknessStat(id, student_user_id, subject_code, knowledge_node_id, window, stats_json, created_at)`
  - P4 MVP: can compute on the fly; table optional (decide in Task 1).

---

## API (P4) — Proposed

Student:
- `POST /student/self-tests/generate` → create paper (per subject or all enabled)
- `GET /student/self-tests` → list papers
- `GET /student/self-tests/{paper_id}` → paper detail
- `POST /student/self-tests/{paper_id}/submit` → submit answers, grade, return summary
- `GET /student/wrong-book` → list wrong items (filters: subject_code)

Admin/staff (MVP read-only):
- `GET /admin/students/{student_user_id}/wrong-book/summary`

---

## Task 1: Models + migration (P4 test + grading + wrong book)

**Files:**
- Create: `backend/app/models/self_test.py`
- Create: `backend/app/models/wrong_book.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/alembic/env.py`
- Migration: `backend/alembic/versions/*_p4_self_test_and_wrong_book.py`
- Test: `backend/tests/test_p4_models_smoke.py`

- [ ] **Step 1: Write failing smoke test**
- [ ] **Step 2: Implement models with constraints**
- [ ] **Step 3: Autogenerate migration + apply**
- [ ] **Step 4: Run tests**
- [ ] **Step 5: Commit**

---

## Task 2: Self-test generation service + student APIs

**Files:**
- Create: `backend/app/schemas/self_test.py`
- Create: `backend/app/services/self_test.py`
- Create: `backend/app/routers/student_self_test.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_self_test_flow.py`

- [ ] **Step 1: Write failing integration tests**
- [ ] **Step 2: Implement deterministic question generation (MVP)**
- [ ] **Step 3: Implement APIs**
- [ ] **Step 4: Commit**

---

## Task 3: Grading pipeline (objective + subjective via ModelGateway)

**Rules (MVP):**
- objective: `content == answer_key` → full points else 0
- subjective: call `ModelGateway` with scene `grading` and enforce JSON output schema server-side (retry/repair on invalid JSON)

**Files:**
- Create: `backend/app/services/grading.py`
- Modify: `backend/app/services/self_test.py` (submit triggers grading)
- Tests: `backend/tests/test_grading_objective.py`, `backend/tests/test_grading_subjective_mock.py`

- [ ] **Step 1: Objective grading tests + impl**
- [ ] **Step 2: Subjective grading contract tests + impl (mock gateway)**
- [ ] **Step 3: Commit**

---

## Task 4: Wrong-book ingestion + weakness aggregation (MVP)

**Files:**
- Create: `backend/app/services/wrong_book.py`
- Create: `backend/app/routers/student_wrong_book.py`
- Modify: `backend/app/main.py`
- Tests: `backend/tests/test_wrong_book.py`

- [ ] **Step 1: Failing tests**
- [ ] **Step 2: Ingest wrong items from grading results**
- [ ] **Step 3: Provide list API**
- [ ] **Step 4: Commit**

---

## Task 5: Frontend — self-test flow + wrong book list (MVP)

**Files:**
- Create: `frontend/src/api/selfTests.ts`
- Create: `frontend/src/api/wrongBook.ts`
- Create: `frontend/src/pages/student/SelfTests.tsx`
- Create: `frontend/src/pages/student/SelfTestPaper.tsx`
- Create: `frontend/src/pages/student/WrongBook.tsx`
- Modify: `frontend/src/App.tsx` (routes)
- Modify: `frontend/src/pages/student/Workspace.tsx` (entry)
- Tests: `frontend/tests/SelfTests.test.tsx`, `frontend/tests/WrongBook.test.tsx`

- [ ] **Step 1: APIs**
- [ ] **Step 2: Pages**
- [ ] **Step 3: Tests + build**
- [ ] **Step 4: Commit**

---

## Task 6: Final verification (P4)

- [ ] Backend: `cd backend && pytest -q`
- [ ] Frontend: `cd frontend && npm test -- --run && npm run build`
- [ ] Manual smoke: login student → generate self-test → submit → see score → wrong book list contains wrong items

