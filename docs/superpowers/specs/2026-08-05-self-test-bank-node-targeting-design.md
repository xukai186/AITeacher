# 自测题库选题：薄弱点 + 本周知识点 — 产品设计规格

**日期：** 2026-08-05  
**状态：** 待实现  
**依赖：** 全局题库 `2026-08-04-global-question-bank-design.md`（`SelfTestAssembler`、`QuestionBankItem.knowledge_node_id`）、`ReportService.overview.weak_nodes`、总计划 `MasterPlanVersion.weekly_goals_json`（`kind=focus` + `syllabus_node_ids`）

---

## 1. 背景与目标

题库上线后，自测组卷已改为「优先抽库 → 不足再 AI」。但 `select_from_bank` 目前只按 **科目 + active + 机构优先**、按 `created_at` 平铺，**不读**薄弱点与本周 focus 节点。`target_nodes` 仅影响 AI 补题，导致库内题越积越多时，自测个性化反而变弱。

目标：在题库选题阶段引入与学习闭环一致的节点优先级，使抽到的库题优先对准薄弱点与本周推进，再兜底同科目其他题。

---

## 2. 已确认的产品决策

| 维度 | 决策 |
|------|------|
| 策略 | **混合**：L1 薄弱点 → L2 本周 focus → L3 同科目其他 |
| 层间分配 | **严格瀑布**：先尽量抽满上一层，不够再进下一层 |
| 层内范围 | 每层内仍 **org active 优先于 global active**；排除学生已提交卷中出现过的 `bank_item_id` |
| 无节点题 | `knowledge_node_id IS NULL` 的题**只出现在 L3** |
| AI 补题 | **不变**：仍用现有 `target_nodes`（薄弱 + 大纲叶子）驱动 `generate_prepared_self_test` |
| 配置入口 | 首期**无**机构/学生可选策略；固定为上述瀑布 |

---

## 3. 节点来源

### 3.1 L1 — 薄弱点

与现有自测 AI 组卷对齐：对当前 `student_user_id` + `subject_code` 调用 `ReportService.overview`（或等价路径）得到 `weak_nodes`，取其叶子 `syllabus_node_id`（或 overview 已解析的节点 ID 集合）作为 `weak_ids`。

- 无薄弱点 → 跳过 L1。
- 仅使用**本科目**节点。

### 3.2 L2 — 本周 focus

从学生当前生效总计划版本读取 `weekly_goals_json`：

- 取 `kind == "focus"` 且 `subject_code` 等于本组卷科目的条目；
- 合并其 `syllabus_node_ids` 为 `focus_ids`（字符串 UUID → UUID）。

- 无生效总计划 / 无 focus / ID 为空 → 跳过 L2。
- 若某 ID 已在 `weak_ids` 中：L1 已抽过的题不会再抽；L2 查询仍可用该 ID，但需排除本卷已选 `bank_item_id`，避免同题重复。

### 3.3 L3 — 兜底

同科目其余 `active` 题：

- 节点不在 `weak_ids ∪ focus_ids`，**或** `knowledge_node_id` 为空。

---

## 4. 选题算法（`select_from_bank`）

输入：与现接口一致（`org_id`、`student_user_id`、`subject_code`、`count`、可选 `exclude_bank_ids`），并在实现中读取 L1/L2 节点集合。

伪代码：

```
excluded = 学生已提交卷的 bank_item_id ∪ exclude_bank_ids
selected = []

for layer in [weak_ids, focus_ids, None]:  # None = L3
  remaining = count - len(selected)
  if remaining <= 0: break
  for scope in [org, global]:
    remaining = count - len(selected)
    if remaining <= 0: break
    query active items for subject + scope (+ org_id if org)
      where id not in excluded ∪ selected.ids
      and node filter for layer:
        L1/L2: knowledge_node_id IN layer_ids
        L3: knowledge_node_id IS NULL OR knowledge_node_id NOT IN (weak_ids ∪ focus_ids)
      order by created_at asc, id asc
      limit remaining
    append; set selection_source bank_org | bank_global
```

`assemble()`：先调用增强后的 `select_from_bank`，再对 gap 走现有 AI 回灌逻辑；**不改变** AI 入库与 `selection_source=ai_fallback` 语义。

可选增强（非必须）：在 `AssembledQuestion` 或调试字段增加 `selection_layer`（`weak` / `focus` / `other`），便于测试与排查。首期若不加字段，测试可通过「先 seed 各层题、断言前 N 道的 `bank_item_id`」验证顺序。

---

## 5. 失败与边界

| 情况 | 行为 |
|------|------|
| L1/L2 节点在库中无题 | 该层 0 题，继续下一层 |
| 有题但均被学生去重排除 | 同层视为抽不到，继续下一层 |
| 三层合计仍不足 `count` | 与现行为一致：进入 AI gap fill |
| overview / 总计划读取失败 | 将该层视为空集合，**不**导致整卷失败；仍可 L3 + AI |

历史卷面快照不受影响；仅改变**新生成**自测的抽题顺序。

---

## 6. 明确不在本规格范围

- 均衡配比 / 按节点数比例分配 slots
- 学生或机构可选组卷策略
- 按 `difficulty` 加权抽样
- 向量语义选题
- 改 AI `target_nodes` 算法本身（仅消费现有薄弱/叶子逻辑）
- 题目编辑、公共题管理、列表分页等其他题库 follow-up

---

## 7. 测试要点

- 薄弱节点有题时，成卷前若干道来自 weak 挂载题（org 优先于同层 global）。
- 薄弱抽不满时，后续来自 focus 挂载题。
- 无节点题不会出现在仅由 L1/L2 填满的卷面前部；仅当进入 L3 才可选中。
- 无 weak/focus 时退化为接近现状：L3 org→global + AI。
- 已提交过的 `bank_item_id` 仍被排除。
- 回归：`assemble` AI gap + pending 入库路径；`paper_gen_jobs` self_test 接线。

---

## 8. 成功标准

1. 题库选题顺序可解释：薄弱 → 本周 focus → 其他，层内 org → global。
2. 库内有足够挂载薄弱点的题时，自测不再「只按入库早晚」平铺。
3. AI 补题与回灌行为与题库上线时一致。
4. 无结构化周目标或无薄弱点时，组卷仍可成功。
