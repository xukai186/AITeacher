from __future__ import annotations

import hashlib
import json
import os
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
    DEFAULT_TIMEOUT = httpx.Timeout(60.0, connect=10.0)

    def __init__(self, http_client: httpx.Client | None = None) -> None:
        self._http_client = http_client or httpx.Client(timeout=self.DEFAULT_TIMEOUT)

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
                    text = f"已提交 {len(reviews)} 个科目的计划复审任务，后台 worker 将生成明日任务。"
                elif name == "explain_question":
                    text = (
                        f"已获取第 {data.get('question_seq')} 题讲评材料："
                        f"{data.get('explanation_hint', '')}"
                    )
                elif name == "propose_subject_plan":
                    text = (
                        f"已为 {data.get('subject_code')} 更新分科计划至 v{data.get('version')}。"
                        if data.get("ok")
                        else "分科计划更新失败。"
                    )
                elif name == "request_plan_adjustment":
                    text = (
                        f"已提交计划调整请求（{data.get('target_date')}），"
                        "后台将复审并更新任务。"
                        if data.get("ok")
                        else "计划调整请求失败。"
                    )
                elif name == "get_weekly_calendar":
                    days = data.get("days") or []
                    pending = sum(d.get("pending_count", 0) for d in days)
                    text = f"已读取未来 7 天日历，共 {pending} 项待办任务。"
                elif name == "propose_master_plan":
                    if data.get("ok"):
                        text = (
                            "总规划调整已提交。"
                            + (
                                "需学生在总计划页确认后生效。"
                                if data.get("requires_student_confirmation")
                                else "已自动生效。"
                            )
                        )
                    else:
                        text = "总规划调整失败。"
                elif name in ("list_papers", "get_paper", "generate_paper"):
                    text = f"试卷工具 {name} 已完成，请根据返回数据继续讲解或建议。"
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

        if "explain_question" in tool_names and re.search(r"讲|讲解|解释|为什么|第.?题", last_user):
            return ModelCompletion(
                tool_calls=(
                    ToolCall(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        name="explain_question",
                        arguments='{"paper_type":"self_test","paper_id":"00000000-0000-0000-0000-000000000001","question_seq":1}',
                    ),
                )
            )

        if "request_plan_adjustment" in tool_names and re.search(
            r"调整|改计划|太慢|太快|跟不上", last_user
        ):
            return ModelCompletion(
                tool_calls=(
                    ToolCall(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        name="request_plan_adjustment",
                        arguments='{"reason":"学生请求调整"}',
                    ),
                )
            )

        if "get_weekly_calendar" in tool_names and re.search(
            r"日历|本周|一周|7天|七天|任务安排", last_user
        ):
            return ModelCompletion(
                tool_calls=(
                    ToolCall(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        name="get_weekly_calendar",
                        arguments="{}",
                    ),
                )
            )

        if "propose_master_plan" in tool_names and re.search(
            r"总规划|总计划|每日时长|时间预算|周目标", last_user
        ) and re.search(r"调整|增加|减少|改成|改为", last_user):
            return ModelCompletion(
                tool_calls=(
                    ToolCall(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        name="propose_master_plan",
                        arguments='{"daily_minutes":150}',
                    ),
                )
            )

        digest = hashlib.sha256(f"{model}:{scene}:{last_user}".encode("utf-8")).hexdigest()[:8]
        return ModelCompletion(text=f"[mock:{scene}:{digest}] 收到：{last_user}")

    @staticmethod
    def _chat_completions_url(base_url: str, params: dict) -> str:
        base = base_url.rstrip("/")
        custom = params.get("chat_completions_path")
        if custom:
            path = str(custom)
            if not path.startswith("/"):
                path = "/" + path
            return f"{base}{path}"
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"

    def _complete_openai_compat(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        params: dict,
    ) -> ModelCompletion:
        base_url = params.get("base_url") or os.getenv("AIT_LLM_BASE_URL") or ""
        api_key = params.get("api_key") or os.getenv("AIT_LLM_API_KEY") or ""
        if not base_url or not api_key:
            raise ValueError(
                "openai_compat requires base_url/api_key in ModelPolicy.params "
                "or env vars AIT_LLM_BASE_URL / AIT_LLM_API_KEY"
            )

        url = self._chat_completions_url(base_url, params)
        headers = {"Authorization": f"Bearer {api_key}"}
        payload: dict[str, Any] = {"model": model, "messages": messages}
        if tools:
            payload["tools"] = tools

        resp = self._http_client.post(url, headers=headers, json=payload)
        if resp.is_error:
            detail = resp.text[:500]
            raise RuntimeError(f"LLM HTTP {resp.status_code}: {detail}") from None
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
