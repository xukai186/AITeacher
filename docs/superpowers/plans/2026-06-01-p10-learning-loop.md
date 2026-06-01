# P10：学习闭环（方案 A）

## 目标

补齐规格 §6.4 / §6.5 / §5.3 的最小闭环：自测可生成规则、批阅后掌握度更新、未来 3 天错题复习任务、`generate_paper` 工具。

## 范围

- `SelfTestEligibilityService`：硬规则（间隔≥5 天、无进行中卷、无 locked、本周≤2 次）
- `SelfTestService.generate` / Agent `generate_paper`：生成前校验
- `MasteryService.update_from_self_test`：批阅后合并 `MasterySnapshot`
- `WrongBookFollowUpService`：批阅后为未来 3 天插入 `review_wrong` 任务（幂等）
- `CompletionRateReviewService`：连续 3 天单科完成率 < 60% 时入队 `PlanReviewJob`（每日调度时检查）

## 非本期

- `LearningEvent` 表、错题 `mastered` 状态机、LLM 组卷、机构锁卷 UI

## 验收

- `pytest tests/test_self_test_eligibility.py tests/test_learning_loop.py` 通过
- 全量 `pytest` 通过
