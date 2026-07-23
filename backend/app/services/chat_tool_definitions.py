from __future__ import annotations

from typing import Any

# OpenAI-compatible tool schemas exposed to the chat model.
SUBJECT_CHAT_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_subject_context",
            "description": "读取当前科目的学情摘要（错题来源统计、薄弱点数量、建议条数）。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_paper",
            "description": (
                "在规则允许时（间隔、周次数、无进行中卷等）为当前科目生成一份自测卷。"
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_daily_tasks",
            "description": (
                "根据学情建议为学生生成指定日期的每日学习任务（幂等）。"
                "默认生成明天的任务；包含错题复习、自测建议等。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target_date": {
                        "type": "string",
                        "description": "任务日期，ISO 格式 YYYY-MM-DD；省略则为明天。",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_papers",
            "description": "列出当前科目的摸底卷与自测卷（最近若干条），用于回顾进度或选择讲解题目。",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "返回条数上限；默认 5。",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_paper",
            "description": "读取一份试卷（摸底/自测）的题目内容，用于讲题或定位薄弱点。",
            "parameters": {
                "type": "object",
                "properties": {
                    "paper_type": {
                        "type": "string",
                        "description": "试卷类型：placement 或 self_test。",
                        "enum": ["placement", "self_test"],
                    },
                    "paper_id": {
                        "type": "string",
                        "description": "试卷 ID（UUID 字符串）。",
                    },
                },
                "required": ["paper_type", "paper_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "explain_question",
            "description": (
                "讲解某份试卷（摸底/自测）内的某一题。"
                "question_seq 是该卷内部题号，不是错题本列表序号。"
                "学生说「错题本第 N 题」时请改用 list_wrong_book / explain_wrong_book_item。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "paper_type": {
                        "type": "string",
                        "enum": ["placement", "self_test"],
                    },
                    "paper_id": {"type": "string"},
                    "question_seq": {
                        "type": "integer",
                        "description": "试卷内题号（从 1 开始）；与 question_id 二选一。不是错题本序号。",
                    },
                    "question_id": {"type": "string"},
                },
                "required": ["paper_type", "paper_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_wrong_book",
            "description": (
                "列出当前科目错题本条目（与学生端错题本同序：创建时间倒序）。"
                "返回 list_index（从 1 起），对应页面「错题 N」。"
                "学生提到错题本第几题时，先调用本工具或直接用 explain_wrong_book_item。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "筛选状态：active / mastered；省略则与页面默认一致（待掌握+已掌握）。",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回条数上限；默认 20。",
                    },
                    "offset": {
                        "type": "integer",
                        "description": "偏移量；默认 0。",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "explain_wrong_book_item",
            "description": (
                "讲解错题本中的某一题（按学生端列表序号 list_index，或 item_id）。"
                "用于「分析错题本第 N 题」；不要误用 explain_question 的试卷题号。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "list_index": {
                        "type": "integer",
                        "description": "错题本列表序号（从 1 开始），与页面「错题 N」一致。",
                    },
                    "item_id": {
                        "type": "string",
                        "description": "错题本条目 UUID；与 list_index 二选一。",
                    },
                    "status": {
                        "type": "string",
                        "description": "与 list_wrong_book 相同的状态筛选；省略则待掌握+已掌握。",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_subject_plan",
            "description": "为当前科目提议新的分科阶段计划（生成新版本并立即生效）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "phases": {
                        "type": "array",
                        "description": "阶段列表，每项含 title、days、notes。",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "days": {"type": "integer"},
                                "notes": {"type": "string"},
                            },
                            "required": ["title"],
                        },
                    },
                },
                "required": ["phases"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_plan_adjustment",
            "description": "学生请求调整学习计划：为指定日期入队计划复审任务。",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_date": {
                        "type": "string",
                        "description": "目标日期 ISO YYYY-MM-DD；省略则为明天。",
                    },
                    "reason": {
                        "type": "string",
                        "description": "调整原因摘要，供老师参考。",
                    },
                },
                "required": [],
            },
        },
    },
]

PLANNER_CHAT_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_student_overview",
            "description": "读取学生各启用科目的学情概览（错题来源、薄弱点、建议条数）。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_master_plan",
            "description": "读取当前总规划（周目标、每日时间预算等）。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "trigger_plan_review",
            "description": "触发计划复审：为指定科目或全部启用科目生成/更新每日任务（默认明天）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "subject_code": {
                        "type": "string",
                        "description": "可选；省略则处理全部启用科目。",
                    },
                    "target_date": {
                        "type": "string",
                        "description": "任务日期 ISO YYYY-MM-DD；省略则为明天。",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_subject_context",
            "description": "读取指定科目的学情摘要（需提供 subject_code）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "subject_code": {
                        "type": "string",
                        "description": "科目代码，如 english、math、politics。",
                    },
                },
                "required": ["subject_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weekly_calendar",
            "description": "读取未来 7 天的每日任务日历（按日期分组）。",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_master_plan",
            "description": (
                "提议调整总规划：可修改某日每日时长和/或周目标；"
                "变化超过 15% 时需学生确认。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target_date": {
                        "type": "string",
                        "description": "要调整的日期 ISO YYYY-MM-DD；省略则为明天。",
                    },
                    "daily_minutes": {
                        "type": "integer",
                        "description": "该日总学习时长（分钟）。",
                    },
                    "weekly_goals": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "description": {"type": "string"},
                            },
                            "required": ["title"],
                        },
                    },
                },
                "required": [],
            },
        },
    },
]


def tools_for_agent(agent_type: str, subject_code: str | None) -> list[dict[str, Any]]:
    if agent_type == "subject":
        if not subject_code:
            return []
        return SUBJECT_CHAT_TOOLS
    if agent_type == "planner":
        return PLANNER_CHAT_TOOLS
    return []
