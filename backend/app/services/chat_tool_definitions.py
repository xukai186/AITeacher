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
]


def tools_for_agent(agent_type: str, subject_code: str | None) -> list[dict[str, Any]]:
    if agent_type == "subject":
        if not subject_code:
            return []
        return SUBJECT_CHAT_TOOLS
    if agent_type == "planner":
        return PLANNER_CHAT_TOOLS
    return []
