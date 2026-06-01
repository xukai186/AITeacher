# P11：机构后台干预（方案 B）

## 目标

管理员/员工可查看负责学员的学情与计划，并执行改计划、锁卷、换卷（写审计）。

## API（`/org/students/{student_id}`）

- `GET /overview` — 各科学情摘要、错题数、近期自测
- `GET /plans` — 当前总规划/分科计划版本
- `PATCH /plans/master` — 新 `MasterPlanVersion`，`source=admin`，立即 active
- `GET /papers` — 自测卷列表
- `POST /papers/{paper_id}/lock`
- `POST /papers/{paper_id}/replace` — 旧卷 `replaced`，生成新卷（跳过组卷规则）
- `GET /wrong-book` — 错题列表

权限：`org_admin` 本机构全部学员；`org_staff` 仅 `StaffStudent` 分配学员。

## 前端

- 学员详情页（管理员 `/admin/students/:id`，员工 `/staff/students/:id`）
- 概览 / 计划 / 试卷 / 错题 Tab；锁卷、换卷、保存预算

## 验收

- `pytest tests/test_org_student_intervention.py`
- 全量 `pytest` 通过
