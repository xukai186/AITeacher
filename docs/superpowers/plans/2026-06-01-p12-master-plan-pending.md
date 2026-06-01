# P12：学生总计划页 + 待确认（方案 C）

## 目标

规格 §4.4：跨科总计划每日时长变化 >15% 时 `auto_activate=false`，学生在总计划页确认后生效。

## 实现

- `MasterPlan.pending_version_id` 指向待确认版本
- `MasterPlanActivationService`：`propose` / `confirm` / `reject`，按总预算变化比例判定
- 跨科削减取消任务后，若当日预算需调整且变化 >15%，写入 pending
- `GET/POST /student/master-plan`（查看、确认、拒绝）
- 前端 `/student/master-plan` 总计划页

## 验收

- `pytest tests/test_master_plan_pending.py`
- 全量 `pytest` 通过
