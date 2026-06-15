from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.services.chat_tool_definitions import tools_for_agent
from app.services.chat_tool_executor import ChatToolExecutor
from app.services.model_gateway import ModelGateway, ModelCompletion, ToolCall

TOOL_CALLS_PREFIX = "__TOOL_CALLS__:"
MAX_TOOL_ITERATIONS = 5


@dataclass
class ChatTurnResult:
    assistant_message: str
    tools_used: list[str] = field(default_factory=list)
    api_messages: list[dict[str, Any]] = field(default_factory=list)


class ChatToolLoop:
    def __init__(
        self,
        model_gateway: ModelGateway | None = None,
        tool_executor: ChatToolExecutor | None = None,
    ) -> None:
        self._gateway = model_gateway or ModelGateway()
        self._executor = tool_executor or ChatToolExecutor()

    def run(
        self,
        db: Session,
        *,
        student_user_id: uuid.UUID,
        agent_type: str,
        subject_code: str | None,
        provider: str,
        model: str,
        params: dict | None,
        history_messages: list[dict[str, Any]],
        user_message: str,
    ) -> ChatTurnResult:
        tools = tools_for_agent(agent_type, subject_code)
        system = self._system_prompt(agent_type, subject_code, tools)
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        messages.extend(history_messages)
        messages.append({"role": "user", "content": user_message})

        tools_used: list[str] = []
        final_text = ""

        for _ in range(MAX_TOOL_ITERATIONS):
            try:
                completion = self._gateway.complete(
                    provider=provider,
                    model=model,
                    scene="chat",
                    messages=messages,
                    tools=tools if tools else None,
                    params=params,
                )
            except Exception as exc:
                return ChatTurnResult(
                    assistant_message=(
                        "模型调用失败，请检查模型策略中的 base_url、模型名与 api_key。"
                        f"（{type(exc).__name__}: {exc}）"
                    ),
                    tools_used=tools_used,
                    api_messages=[],
                )
            if not completion.tool_calls:
                final_text = completion.text or ""
                break

            # Record assistant tool-call turn for downstream providers / persistence.
            tool_calls_payload = [
                {
                    "id": tc.id,
                    "name": tc.name,
                    "arguments": tc.arguments,
                }
                for tc in completion.tool_calls
            ]
            messages.append(
                {
                    "role": "assistant",
                    "content": TOOL_CALLS_PREFIX + json.dumps(tool_calls_payload, ensure_ascii=False),
                }
            )

            for tc in completion.tool_calls:
                tools_used.append(tc.name)
                args = ChatToolExecutor.parse_arguments(tc.arguments)
                result = self._executor.execute(
                    db,
                    tool_name=tc.name,
                    arguments=args,
                    student_user_id=student_user_id,
                    default_subject_code=subject_code,
                    agent_type=agent_type,
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "name": tc.name,
                        "content": json.dumps(result, ensure_ascii=False),
                    }
                )

        if not final_text:
            final_text = "抱歉，我暂时无法完成这个请求，请稍后再试。"

        # Messages after history + user turn (tool-call rows and tool results only).
        persist_start = 1 + len(history_messages) + 1
        turn_messages = messages[persist_start:]

        return ChatTurnResult(
            assistant_message=final_text,
            tools_used=tools_used,
            api_messages=turn_messages,
        )

    @staticmethod
    def _system_prompt(agent_type: str, subject_code: str | None, tools: list[dict]) -> str:
        tool_names = [t["function"]["name"] for t in tools]
        lines = [
            "你是考研一对一 AI 老师，用简洁中文回答。",
            f"当前 Agent 类型：{agent_type}。",
        ]
        if subject_code:
            lines.append(f"当前科目：{subject_code}。")
        if tool_names:
            lines.append(
                "当学生询问学情、薄弱点、学习建议，或明确要求生成/安排明日任务时，"
                "请调用可用工具获取数据或生成任务，再基于工具结果给出可执行建议。"
            )
            lines.append(f"可用工具：{', '.join(tool_names)}。")
        else:
            lines.append("当前会话未绑定科目，无法调用学科任务工具。")
        return "\n".join(lines)

    @staticmethod
    def _tool_arguments_json(arguments: Any) -> str:
        if isinstance(arguments, str):
            return arguments
        return json.dumps(arguments or {}, ensure_ascii=False)

    @staticmethod
    def history_from_db_rows(rows: list[Any]) -> list[dict[str, Any]]:
        """Convert persisted ChatMessage rows to provider messages (no system)."""
        out: list[dict[str, Any]] = []
        for row in rows:
            if row.role == "user":
                out.append({"role": "user", "content": row.content})
            elif row.role == "assistant":
                if row.content.startswith(TOOL_CALLS_PREFIX):
                    payload = json.loads(row.content[len(TOOL_CALLS_PREFIX) :])
                    out.append(
                        {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": item["id"],
                                    "type": "function",
                                    "function": {
                                        "name": item["name"],
                                        "arguments": ChatToolLoop._tool_arguments_json(
                                            item.get("arguments")
                                        ),
                                    },
                                }
                                for item in payload
                            ],
                        }
                    )
                else:
                    out.append({"role": "assistant", "content": row.content})
            elif row.role == "tool":
                data = json.loads(row.content)
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": data.get("tool_call_id", ""),
                        "content": json.dumps(data.get("result", data), ensure_ascii=False),
                    }
                )
        return out
