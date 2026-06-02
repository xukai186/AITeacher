# P13：LearningEvent + 错题掌握状态

## 目标

- `learning_events` 表记录 `wrong_added`、`paper_submitted`、`task_done`、`wrong_practice_*`、`wrong_mastered` 等。
- `WrongBookItem.status`：`active` → `mastered`（连续做对 2 次且间隔 ≥1 天）→ `archived`。
- 学生错题本可练习、归档；完成任务写入 `task_done`。

## API

- `POST /student/wrong-book/{id}/practice` — 提交重做答案
- `POST /student/wrong-book/{id}/archive` — 已掌握错题归档
- `GET /student/wrong-book?status=` — 默认 `active`+`mastered`
- `POST /student/tasks/{id}/complete` — 标记任务完成并记事件

## 验收

- `pytest tests/test_learning_events_wrong_mastery.py`
- 全量 `pytest` 通过
