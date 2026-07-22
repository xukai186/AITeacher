# 路线图叶子节点排期 — 产品设计规格

**日期：** 2026-07-22  
**状态：** 待实现  
**依赖：** 全年学习路线图（已实现）、`SyllabusNode` 考纲树、摸底叶子选择（`leaf_nodes_for_placement`）、7 天战术计划 / P12

---

## 1. 背景与目标

当前全年路线图按月分配的是考纲 **一级章节**（科目根的直接子节点）。种子考纲几乎都是两层树，一级 ≈ 叶子，排期粒度粗，学生只能看到「7 月学阅读」，看不到「细节题 / 主旨题」等具体知识点。

本期目标：

1. **加深种子考纲**到三级（科目根 → 一级章节 → 叶子知识点），每科每个一级章节 **≥ 8** 个叶子；
2. 路线图生成与校验改为按 **真正叶子节点**排期，`months_json` 存叶子 **UUID**；
3. 战术层（7 天计划）注入当月叶子列表，phase notes / LLM prompt 引用叶子名；
4. 学生总计划页按一级章节 **分组展示**叶子。

---

## 2. 已确认的产品决策

| 维度 | 决策 |
|------|------|
| 范围 | **A**：算法按叶子排期 + 加深种子考纲 + 路线图展示叶子名 |
| 战术层 | **注入当月叶子**：`PlanDraftService` / LLM / 规则引用当月叶子（非仅路线图展示） |
| 种子粒度 | 每科每个一级章节 **8+** 叶子 |
| 数据格式 | 存 **`syllabus_node_ids: uuid[]`**；API 附带 resolve 后的 name / parent 供展示 |
| 实现结构 | **扩展现有路线图**（方案 1），不引入「月 → 章 → 叶子」双层 schema |
| 月内周级排期 | **本期不做**（不排「第几周学哪个叶子」） |
| 旧路线图兼容 | 仅含 `syllabus_nodes`（name）的版本 **GET 仍可读**；新生成一律用 ID |

---

## 3. 考纲种子加深

### 3.1 树形结构（三级）

```
英语（根）
├── 阅读
│   ├── 细节题
│   ├── 主旨题
│   ├── 推断题
│   ├── …（≥ 8 叶子）
├── 翻译
│   └── …（≥ 8）
└── 写作
    └── …（≥ 8）

数学（根）
├── 高数（meta.tracks 含 math_1 等，与现网一致）
│   └── …（≥ 8）
├── 线代
└── 概率

政治（根）
├── 马原 / 毛中特 / 史纲 / 思修
│   └── 各 ≥ 8 叶子
```

### 3.2 约束

- 叶子定义与摸底一致：`id` 不作为任何节点的 `parent_id`（`leaf_nodes_for_placement`）
- `exam_year` 过滤不变。**Track：** 叶子节点必须复制所属一级章节的 `meta_json.tracks`（若一级有 tracks），以便现有 `filter_nodes_for_track` 按节点自身 meta 过滤后，不会把「高数」下叶子留给 `math_2` 学生
- `seed_syllabus.py`（及任何 demo seed）升级为三级；开发环境以 re-seed 为主；生产用幂等 seed 脚本**追加**叶子（不删一级、不改已有 UUID）

### 3.3 对摸底的影响

- 摸底组卷已用叶子；加深后题目覆盖更细知识点，**期望行为**，无需改 placement 核心逻辑
- 回归：`test_placement_paper_context` / 摸底 flow 仍绿

---

## 4. `months_json` Schema 变更

### 4.1 每科每月块（新）

```json
{
  "focus": "阅读强化",
  "syllabus_node_ids": ["uuid-1", "uuid-2", "uuid-3"],
  "weekly_hours_hint": 12,
  "notes": "优先细节题与推断题"
}
```

| 字段 | 说明 |
|------|------|
| `syllabus_node_ids` | 叶子 UUID 列表；每月每科 **2–4** 个 |
| `focus` / `notes` / `weekly_hours_hint` | 语义不变 |
| ~~`syllabus_nodes`~~ | **新版本不再写入**；读旧版本时仍可展示 |

### 4.2 API 响应 enrich

学生 / 机构 GET roadmap 时，服务端对每个月块 resolve：

```json
"syllabus_nodes_resolved": [
  { "id": "uuid-1", "name": "细节题", "parent_name": "阅读" }
]
```

- 前端只读 `syllabus_nodes_resolved`（若缺则回退旧 `syllabus_nodes` name 列表）
- 不把完整考纲树塞进 months_json 持久化字段

### 4.3 覆盖与去重规则

- 同一叶子 **不得**出现在两个月
- 全部启用科目的叶子在 `start_date`–`end_date` 内 **至少覆盖一次**（备考月数不足时可每月接近上限 4，仍无法覆盖则优先薄弱 L1 下叶子，未排到的记审计日志，不 fail Job）
- `math_track=none`：禁止 `math` 键与任何 math 叶子

---

## 5. 生成逻辑（`RoadmapDraftService`）

### 5.1 Outline 构建

替换现有「L1 = parent 为科目根」逻辑：

1. `syllabus_nodes_for_year` + `filter_nodes_for_track`
2. `leaf_nodes_for_placement`（或等价：无子节点的节点）
3. `syllabus_outline[subject] = [{ "id", "name", "parent_name" }, …]`

### 5.2 Prompt

- 任务改为：按月分配 **叶子 ID**，输出 `syllabus_node_ids`
- 只能从 outline 的 `id` 选取；跨月不重复；弱项科目（摸底低分 / weak_nodes）多月占比更高
- 英语结合 CET；数学结合 `math_mastery_level`
- 场景仍为 `planning`；mock → 规则降级

### 5.3 解析与校验

`_parse_llm_draft()`：

- 校验每个 ID ∈ 该科 outline 白名单
- 去重；每月每科 cap **4**
- 任一非法 ID、跨月重复、或某启用科某月空列表 → **整稿放弃 LLM 结果，改用规则完整稿**（与现网 LLM 失败策略一致）

`RoadmapActivationService.confirm_pending()`：

- 若 pending 含 `syllabus_node_ids`：**再次**白名单校验；失败 → 400，detail 说明非法节点，不激活
- 若仅为旧版 `syllabus_nodes`（name）：跳过 ID 校验（见 §8）

### 5.4 规则降级

- 将各科叶子按一级章节分组；备考月数 N 内轮转分配，每月每科 2–4 个
- `weekly_hours_hint` 仍按 CET / 数学水平 ±20%
- `source=rule`

---

## 6. 战术层消费

### 6.1 `RoadmapContextService.current_month_slice`

- `MonthSlice` 携带 `syllabus_node_ids`
- Resolve 抽共享 helper（GET enrich 与战术层共用）：输入 IDs → `[{ id, name, parent_name }]`；旧版仅 name 时返回扁平 `{ id: null, name, parent_name: null }`

### 6.2 `PlanDraftService`

- `_apply_month_slice()`：`subject_phases_json[].notes` 写入 `本月叶子：细节题、主旨题、…`（有 focus 时 focus 优先，叶子作补充行）
- `draft_initial_plans()` LLM prompt 注入 `current_month_leaves[subject] = [{ name, parent_name }]`
- 规则路径：按当月叶子顺序轮转写入 phase notes
- `light_revise_draft()`：**不**重算路线图；若存在 MonthSlice，同样把当月叶子写入 notes

### 6.3 刷新节奏

不变：confirm 后立即刷新；每月 1 日 cron 战术刷新；轻量修订不重生成全年路线图。

---

## 7. 界面

### 7.1 学生总计划 — 全年路线图 Tab

「考纲：」由逗号拼接改为 **按 `parent_name` 分组**：

```
阅读：细节题、主旨题、推断题
翻译：词义选择、…
```

pending 确认页同样使用 `syllabus_nodes_resolved`。

### 7.2 工作台横幅

文案不变（生成中 / 待确认）。

### 7.3 机构只读

`GET /org/students/{id}/roadmap` 同样返回 resolved 列表。

---

## 8. 兼容与迁移

| 场景 | 处理 |
|------|------|
| 旧 `months_json` 仅有 `syllabus_nodes`（name） | GET enrich：无 ID 时用 name 列表扁平展示（无 parent 分组） |
| 旧 pending 待 confirm | **允许 confirm**；跳过 ID 白名单；战术层用 name 字符串注入 |
| 新 Job 输出 | 必须含合法 `syllabus_node_ids` |
| 种子加深后已有学生路线图 | 旧 ID/name 可能失效；结构变更仍作废路线图；纯加深不触发作废——老师可 regenerate |

---

## 9. 实现要点（文件级）

| 文件 | 变更 |
|------|------|
| `backend/app/seed_syllabus.py` | 三级树；每 L1 ≥ 8 叶子 |
| `backend/app/services/roadmap_draft.py` | leaf outline；ID 输出；校验；规则分配 |
| `backend/app/schemas/roadmap.py` | `syllabus_node_ids`；`syllabus_nodes_resolved` |
| `backend/app/services/roadmap_context.py` | MonthSlice 带叶子 |
| `backend/app/services/roadmap_activation.py` | confirm 白名单 |
| `backend/app/services/plan_draft.py` | 注入叶子 |
| `backend/app/routers/student_roadmap.py`（及 org） | GET enrich |
| `frontend/src/api/roadmap.ts` | 类型 |
| `frontend/src/pages/student/MasterPlan.tsx` | 分组展示 |
| `backend/tests/test_roadmap_*.py`、`test_seed` / placement context | 覆盖 §10 |

---

## 10. 测试要点

- 种子：每科每 L1 ≥ 8 叶子；`leaf_nodes_for_placement` 数量符合预期；track 过滤仍正确
- 末科摸底交卷 enqueue；生成结果 `syllabus_node_ids` 均在白名单；跨月无重复
- 非法 ID → 解析拒绝或规则降级；confirm 非法 → 400
- confirm 后战术 phase notes 含当月叶子名
- `math_track=none`：无 math 键 / 叶子
- 旧路线图（仅 name）GET 可读；新生成用 ID
- 前端：按 parent 分组展示叶子

---

## 11. OUT OF SCOPE

- 月内「第几周学哪个叶子」周级排期
- 学生 / 老师直接编辑路线图 JSON
- 路线图每月 LLM 全量重算
- 机构自定义考纲树
- 专业课（自命题）叶子排期
- 运营「重开摸底」等非路线图入口

---

## 12. 与现有 spec 关系

| 模块 | 关系 |
|------|------|
| `2026-06-25-annual-study-roadmap-design.md` | 阶段粒度从「一级章节」升级为「叶子」；其余触发 / confirm / Job 不变。该 spec §2「一级章节」与 §14「叶子 OUT OF SCOPE」由本 spec 覆盖修订 |
| `2026-06-25-exam-profile-light-revise-and-task-weights-design.md` | 轻量修订仍不重算全年路线图；战术 notes 可读当月叶子 |
| 摸底 / `placement_paper_context` | 叶子定义与过滤共用；种子加深后摸底覆盖更细 |
| 摸底一科一遍 | 无关；末科交卷仍触发路线图 Job |

**对旧路线图 spec 的修订声明：** 实现本功能后，以本文件为准；旧文件状态保持「已实现」，不改写全文，仅在本文件声明覆盖。
