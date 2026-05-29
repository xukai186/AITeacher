from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class ModelGatewayRequest:
    provider: str
    model: str
    scene: str
    prompt: str
    params: dict | None = None


@dataclass(frozen=True)
class ModelGatewayResponse:
    text: str


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class ModelCompletion:
    text: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()


class ModelGateway:
    def __init__(self, http_client: httpx.Client | None = None) -> None:
        self._http_client = http_client or httpx.Client()

    def generate(self, req: ModelGatewayRequest) -> ModelGatewayResponse:
        completion = self.complete(
            provider=req.provider,
            model=req.model,
            scene=req.scene,
            messages=[{"role": "user", "content": req.prompt}],
            tools=None,
            params=req.params,
        )
        return ModelGatewayResponse(text=completion.text or "")

    def complete(
        self,
        *,
        provider: str,
        model: str,
        scene: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        params: dict | None = None,
    ) -> ModelCompletion:
        if provider == "mock":
            return self._complete_mock(model=model, scene=scene, messages=messages, tools=tools)
        if provider == "openai_compat":
            return self._complete_openai_compat(
                model=model, messages=messages, tools=tools, params=params or {}
            )
        raise ValueError(f"unknown provider: {provider}")

    def _complete_mock(
        self,
        *,
        model: str,
        scene: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
    ) -> ModelCompletion:
        tool_names = {t["function"]["name"] for t in (tools or [])}

        # Summarize after tool results are present.
        for msg in reversed(messages):
            if msg.get("role") == "tool":
                try:
                    data = json.loads(msg.get("content") or "{}")
                except json.JSONDecodeError:
                    data = {}
                name = msg.get("name") or ""
                if name == "get_subject_context":
                    weak = data.get("weak_node_count", 0)
                    recs = data.get("recommendation_count", 0)
                    text = (
                        f"已查询学情：薄弱点 {weak} 个，系统建议 {recs} 条。"
                        "你可以优先按建议复习错题，再安排自测巩固。"
                    )
                elif name == "generate_daily_tasks":
                    created = data.get("created_count", 0)
                    skipped = data.get("skipped_count", 0)
                    day = data.get("target_date", "")
                    text = (
                        f"已为 {day} 生成 {created} 项每日任务"
                        f"（跳过重复 {skipped} 项）。请到「今日计划」查看。"
                    )
                    warnings = data.get("warnings") or []
                    if warnings:
                        text += " " + " ".join(warnings)
                elif name == "get_master_plan":
                    text = (
                        "已读取总规划（含每日时间预算）。"
                        if data.get("exists")
                        else "尚未创建总规划，完成摸底后会自动生成。"
                    )
                elif name == "get_student_overview":
                    n = len(data.get("subjects") or [])
                    text = f"已汇总 {n} 个科目的学情概览，可针对薄弱科目安排复习。"
                elif name == "trigger_plan_review":
                    reviews = data.get("reviews") or []
                    total = sum(int(r.get("created_count", 0)) for r in reviews)
                    text = f"已为 {len(reviews)} 个科目完成计划复审，新生成 {total} 项任务。"
                else:
                    text = f"[mock:{scene}] 工具 {name} 已完成。"
                digest = hashlib.sha256(f"{model}:{text}".encode()).hexdigest()[:6]
                return ModelCompletion(text=f"[mock:{scene}:{digest}] {text}")

        last_user = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user = str(msg.get("content") or "")
                break

        if "get_master_plan" in tool_names and re.search(
            r"总规划|总计划|时间预算|每日时长", last_user
        ):
            return ModelCompletion(
                tool_calls=(
                    ToolCall(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        name="get_master_plan",
                        arguments="{}",
                    ),
                )
            )

        if "get_student_overview" in tool_names and re.search(
            r"概览|全科|整体学情|所有科目", last_user
        ):
            return ModelCompletion(
                tool_calls=(
                    ToolCall(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        name="get_student_overview",
                        arguments="{}",
                    ),
                )
            )

        if "trigger_plan_review" in tool_names and re.search(
            r"生成|安排|明日|明天|复审|任务", last_user
        ):
            return ModelCompletion(
                tool_calls=(
                    ToolCall(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        name="trigger_plan_review",
                        arguments="{}",
                    ),
                )
            )

        if "get_subject_context" in tool_names and re.search(
            r"学情|薄弱|报告|掌握|错题情况", last_user
        ):
            args = "{}"
            if "英语" in last_user or "english" in last_user.lower():
                args = '{"subject_code":"english"}'
            return ModelCompletion(
                tool_calls=(
                    ToolCall(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        name="get_subject_context",
                        arguments=args,
                    ),
                )
            )

        if "generate_daily_tasks" in tool_names and re.search(
            r"生成|安排|明日|明天|任务|计划", last_user
        ):
            return ModelCompletion(
                tool_calls=(
                    ToolCall(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        name="generate_daily_tasks",
                        arguments="{}",
                    ),
                )
            )

        digest = hashlib.sha256(f"{model}:{scene}:{last_user}".encode("utf-8")).hexdigest()[:8]
        return ModelCompletion(text=f"[mock:{scene}:{digest}] 收到：{last_user}")

    def _complete_openai_compat(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        params: dict,
    ) -> ModelCompletion:
        base_url = params.get("base_url")
        api_key = params.get("api_key")
        if not base_url or not api_key:
            raise ValueError("openai_compat requires params.base_url and params.api_key")

        url = f"{base_url.rstrip('/')}/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}"}
        payload: dict[str, Any] = {"model": model, "messages": messages}
        if tools:
            payload["tools"] = tools

        resp = self._http_client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        message = data["choices"][0]["message"]

        raw_calls = message.get("tool_calls") or []
        if raw_calls:
            parsed = tuple(
                ToolCall(
                    id=str(tc.get("id") or f"call_{uuid.uuid4().hex[:8]}"),
                    name=str(tc["function"]["name"]),
                    arguments=str(tc["function"].get("arguments") or "{}"),
                )
                for tc in raw_calls
            )
            return ModelCompletion(tool_calls=parsed)

        return ModelCompletion(text=str(message.get("content") or ""))
