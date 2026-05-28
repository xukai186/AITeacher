# P2 — Model Gateway + Agent Orchestration Skeleton + Chat Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a configurable (org-scoped) model gateway and a minimal agent/orchestrator-backed chat experience so students can chat with a “planner/subject tutor” in the right panel, with messages persisted server-side.

**Architecture:** Extend the P1 FastAPI app with new DB tables (`model_policies`, `chat_sessions`, `chat_messages`) and a `ModelGateway` service that routes by `(org_id, scene)` to either a deterministic mock provider or an OpenAI-compatible HTTP provider. Add a `ChatService` that loads/creates sessions, stores messages, invokes the gateway, and returns assistant responses. Frontend adds a `ChatPanel` component inside the student workspace with streaming-like UX (non-streaming backend in P2) and a simple “subject selector → agent_type + subject_code” binding.

**Tech Stack:** Existing P1 stack (FastAPI + SQLAlchemy + Alembic + pytest; React + Vite + TanStack Query + vitest). For OpenAI-compatible calls: `httpx`.

---

## Scope Check (P2)

P2 is intentionally **not** implementing planning, papers, grading, wrong-book, or analytics. It only adds:

- DB persistence for chat sessions + messages
- org-scoped model policy config (admin API)
- model gateway (mock + openai-compatible)
- orchestrator skeleton for “planner / subject” chat
- student workspace right-panel chat UI that hits the backend

---

## File Structure (P2)

Backend new/modified files:

- Create: `backend/app/services/model_gateway.py`
- Create: `backend/app/services/chat.py`
- Create: `backend/app/schemas/chat.py`
- Create: `backend/app/schemas/model_policy.py`
- Create: `backend/app/routers/admin_model_policy.py`
- Create: `backend/app/routers/chat.py`
- Modify: `backend/app/main.py` (include new routers)
- Modify: `backend/app/models/__init__.py` (if needed for imports)
- Modify: `backend/alembic/env.py` (import models if needed)
- Test: `backend/tests/test_model_policy_api.py`
- Test: `backend/tests/test_chat_api_mock.py`
- Test: `backend/tests/test_model_gateway_openai_compat.py` (unit, no network)

Frontend new/modified files:

- Create: `frontend/src/api/chat.ts`
- Create: `frontend/src/components/chat/ChatPanel.tsx`
- Create: `frontend/src/components/chat/ChatMessageList.tsx`
- Create: `frontend/src/components/chat/ChatComposer.tsx`
- Modify: `frontend/src/pages/student/Workspace.tsx`
- Test: `frontend/tests/ChatPanel.test.tsx`

---

## Task 1: Backend — schemas for model policy + chat

**Files:**
- Create: `backend/app/schemas/model_policy.py`
- Create: `backend/app/schemas/chat.py`
- Test: `backend/tests/test_chat_schemas.py`

- [ ] **Step 1: Write failing schema tests**

Create `backend/tests/test_chat_schemas.py`:

```python
from app.schemas.chat import ChatPostRequest
from app.schemas.model_policy import ModelPolicyUpsert


def test_model_policy_schema_roundtrip():
    obj = ModelPolicyUpsert(scene="chat", provider="mock", model="mock-v1", params={"x": 1})
    assert obj.scene == "chat"
    assert obj.params == {"x": 1}


def test_chat_post_request_validation():
    req = ChatPostRequest(agent_type="subject", subject_code="english", message="hi")
    assert req.agent_type == "subject"
    assert req.subject_code == "english"
```

- [ ] **Step 2: Run and confirm it fails**

Run: `cd backend && pytest tests/test_chat_schemas.py -v`  
Expected: ImportError (schemas missing).

- [ ] **Step 3: Implement `backend/app/schemas/model_policy.py`**

```python
from typing import Any

from pydantic import BaseModel, Field


class ModelPolicyUpsert(BaseModel):
    scene: str = Field(min_length=1, max_length=40)
    provider: str = Field(min_length=1, max_length=40)
    model: str = Field(min_length=1, max_length=120)
    params: dict[str, Any] = Field(default_factory=dict)


class ModelPolicyOut(ModelPolicyUpsert):
    id: str
    org_id: str
```

- [ ] **Step 4: Implement `backend/app/schemas/chat.py`**

```python
from pydantic import BaseModel, Field


class ChatPostRequest(BaseModel):
    agent_type: str = Field(pattern="^(planner|subject)$")
    subject_code: str | None = Field(default=None, max_length=40)
    message: str = Field(min_length=1, max_length=8000)


class ChatPostResponse(BaseModel):
    session_id: str
    assistant_message: str
```

- [ ] **Step 5: Run tests**

Run: `cd backend && pytest tests/test_chat_schemas.py -v`  
Expected: `2 passed`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/model_policy.py backend/app/schemas/chat.py backend/tests/test_chat_schemas.py
git commit -m "feat(p2): add chat and model policy schemas"
```

---

## Task 2: Backend — ModelGateway (mock provider)

**Files:**
- Create: `backend/app/services/model_gateway.py`
- Test: `backend/tests/test_model_gateway_mock.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_model_gateway_mock.py`:

```python
from app.services.model_gateway import ModelGateway, ModelGatewayRequest


def test_mock_provider_returns_deterministic_text():
    gw = ModelGateway()
    out1 = gw.generate(ModelGatewayRequest(provider="mock", model="mock-v1", scene="chat", prompt="hi"))
    out2 = gw.generate(ModelGatewayRequest(provider="mock", model="mock-v1", scene="chat", prompt="hi"))
    assert out1.text
    assert out1.text == out2.text
```

- [ ] **Step 2: Run and confirm it fails**

Run: `cd backend && pytest tests/test_model_gateway_mock.py -v`  
Expected: ImportError.

- [ ] **Step 3: Implement minimal gateway**

Create `backend/app/services/model_gateway.py`:

```python
from __future__ import annotations

import hashlib
from dataclasses import dataclass


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


class ModelGateway:
    def generate(self, req: ModelGatewayRequest) -> ModelGatewayResponse:
        if req.provider == "mock":
            digest = hashlib.sha256(f"{req.model}:{req.scene}:{req.prompt}".encode("utf-8")).hexdigest()[:8]
            return ModelGatewayResponse(text=f\"[mock:{req.scene}:{digest}] {req.prompt}\")
        raise ValueError(f\"unknown provider: {req.provider}\")
```

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_model_gateway_mock.py -v`  
Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/model_gateway.py backend/tests/test_model_gateway_mock.py
git commit -m "feat(p2): add deterministic mock model gateway"
```

---

## Task 3: Backend — OpenAI-compatible provider (unit tested, no real network)

**Files:**
- Modify: `backend/pyproject.toml` (add `httpx` to runtime deps if not already)
- Modify: `backend/app/services/model_gateway.py` (add `openai_compat` provider)
- Test: `backend/tests/test_model_gateway_openai_compat.py`

- [ ] **Step 1: Add dependency (if missing)**

Ensure `httpx>=0.27` is in `[project].dependencies` (runtime), not only dev.

- [ ] **Step 2: Write failing unit test (mock transport)**

Create `backend/tests/test_model_gateway_openai_compat.py`:

```python
import json

import httpx

from app.services.model_gateway import ModelGateway, ModelGatewayRequest


def test_openai_compat_posts_chat_completions_and_returns_text():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path.endswith("/v1/chat/completions")
        body = json.loads(request.content.decode())
        assert body["model"] == "gpt-test"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "hello from provider"}}]},
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="https://example.invalid")

    gw = ModelGateway(http_client=client)
    out = gw.generate(
        ModelGatewayRequest(
            provider="openai_compat",
            model="gpt-test",
            scene="chat",
            prompt="hi",
            params={"base_url": "https://example.invalid", "api_key": "k"},
        )
    )
    assert out.text == "hello from provider"
```

- [ ] **Step 3: Implement provider**

Update `ModelGateway` to accept an injected `http_client` and implement:
- url: `${base_url}/v1/chat/completions`
- headers: `Authorization: Bearer <api_key>`
- payload: `{ "model": model, "messages": [{"role":"user","content":prompt}] }`
- parse: `choices[0].message.content`

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_model_gateway_openai_compat.py -v`  
Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/app/services/model_gateway.py backend/tests/test_model_gateway_openai_compat.py
git commit -m "feat(p2): add openai-compatible model gateway provider"
```

---

## Task 4: Backend — Admin model policy API

**Files:**
- Create: `backend/app/routers/admin_model_policy.py`
- Create: `backend/app/schemas/model_policy.py` (already in Task 1; extend as needed)
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_model_policy_api.py`

- [ ] **Step 1: Write failing API test**

Create `backend/tests/test_model_policy_api.py`:

```python
from app.auth.security import hash_password
from app.models import ModelPolicy, UserRole
from tests.factories import make_org, make_user


def _seed_admin(db):
    org = make_org(db)
    make_user(
        db, org, role=UserRole.org_admin, email="admin@demo.example", password_hash=hash_password("pw")
    )
    db.commit()
    return org


def _token(client):
    return client.post("/auth/login", json={"email": "admin@demo.example", "password": "pw"}).json()[
        "access_token"
    ]


def test_admin_upserts_and_reads_model_policy(client, db_session):
    _seed_admin(db_session)
    token = _token(client)

    upsert = client.put(
        "/admin/model-policies/chat",
        json={"scene": "chat", "provider": "mock", "model": "mock-v1", "params": {"x": 1}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert upsert.status_code == 200
    assert upsert.json()["scene"] == "chat"
    assert upsert.json()["provider"] == "mock"

    get_resp = client.get(
        "/admin/model-policies",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == 200
    assert any(p["scene"] == "chat" for p in get_resp.json())
```

- [ ] **Step 2: Implement router**

Endpoints:
- `GET /admin/model-policies` → list org policies
- `PUT /admin/model-policies/{scene}` → upsert (org-scoped) and write `AuditLog` action `model_policy.upsert`

Use `require_admin()` and `admin.org_id`.

- [ ] **Step 3: Wire router**

Modify `backend/app/main.py` to include `admin_model_policy.router`.

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_model_policy_api.py -v`  
Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/admin_model_policy.py backend/app/main.py backend/tests/test_model_policy_api.py backend/app/schemas/model_policy.py
git commit -m "feat(p2): admin model policy api"
```

---

## Task 5: Backend — Chat service + chat API (mock end-to-end)

**Files:**
- Create: `backend/app/services/chat.py`
- Create: `backend/app/routers/chat.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_chat_api_mock.py`

- [ ] **Step 1: Write failing integration test**

Create `backend/tests/test_chat_api_mock.py`:

```python
from app.auth.security import hash_password
from app.models import ModelPolicy, UserRole
from tests.factories import make_org, make_user


def _seed_student_and_policy(db):
    org = make_org(db)
    admin = make_user(db, org, role=UserRole.org_admin, email="admin@demo.example", password_hash=hash_password("pw"))
    student = make_user(db, org, role=UserRole.student, email="student@demo.example", password_hash=hash_password("pw"))
    db.add(ModelPolicy(org_id=org.id, scene="chat", provider="mock", model="mock-v1", params={}))
    db.commit()
    return admin, student


def _token(client, email):
    return client.post("/auth/login", json={"email": email, "password": "pw"}).json()["access_token"]


def test_student_chat_creates_session_and_persists_messages(client, db_session):
    _, student = _seed_student_and_policy(db_session)
    token = _token(client, "student@demo.example")

    resp = client.post(
        "/chat",
        json={"agent_type": "subject", "subject_code": "english", "message": "hi"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"]
    assert "mock" in body["assistant_message"]

    # second message should reuse same session scope
    resp2 = client.post(
        "/chat",
        json={"agent_type": "subject", "subject_code": "english", "message": "again"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == 200
```

- [ ] **Step 2: Implement chat service**

`ChatService.post_message(db, student_user, agent_type, subject_code, message)`:\n
- upsert/find `ChatSession` by scope `(student_user_id, agent_type, subject_code)`\n
- insert `ChatMessage(role=\"user\")`\n
- load model policy for scene `chat` for org\n
- build a simple prompt like:\n
\n
```text\n
You are a helpful tutor.\n
Agent type: <planner|subject>\n
Subject: <subject_code or none>\n
User: <message>\n
```\n
- call `ModelGateway.generate(...)`\n
- insert `ChatMessage(role=\"assistant\")`\n
- return session_id + assistant_message\n
\n
If no model policy exists, default to provider `mock`.\n
\n
- [ ] **Step 3: Implement router `POST /chat`**\n
\n
- auth: `require_roles(UserRole.student)`\n
- response: `ChatPostResponse`\n
\n
- [ ] **Step 4: Wire router**\n
\n
Include `chat.router` in `backend/app/main.py`.\n
\n
- [ ] **Step 5: Run tests**\n
\n
Run: `cd backend && pytest tests/test_chat_api_mock.py -v`\n
Expected: `1 passed`.\n
\n
- [ ] **Step 6: Commit**\n
\n
```bash\n
git add backend/app/services/chat.py backend/app/routers/chat.py backend/app/main.py backend/tests/test_chat_api_mock.py\n
git commit -m \"feat(p2): chat api backed by model gateway\"\n
```\n+
---\n+
## Task 6: Frontend — ChatPanel UI in student workspace\n+
**Files:**\n+- Create: `frontend/src/api/chat.ts`\n+- Create: `frontend/src/components/chat/ChatPanel.tsx`\n+- Create: `frontend/src/components/chat/ChatMessageList.tsx`\n+- Create: `frontend/src/components/chat/ChatComposer.tsx`\n+- Modify: `frontend/src/pages/student/Workspace.tsx`\n+- Test: `frontend/tests/ChatPanel.test.tsx`\n+\n+- [ ] **Step 1: Write failing component test**\n+\n+Create `frontend/tests/ChatPanel.test.tsx`:\n+\n+```tsx\n+import { describe, it, expect, vi, beforeEach } from \"vitest\";\n+import { render, screen, fireEvent, waitFor } from \"@testing-library/react\";\n+import ChatPanel from \"../src/components/chat/ChatPanel\";\n+\n+beforeEach(() => {\n+  vi.restoreAllMocks();\n+});\n+\n+function mockFetchOnce(body: unknown) {\n+  vi.stubGlobal(\n+    \"fetch\",\n+    vi.fn(async () => new Response(JSON.stringify(body), { status: 200 })),\n+  );\n+}\n+\n+describe(\"ChatPanel\", () => {\n+  it(\"sends a message and renders assistant reply\", async () => {\n+    mockFetchOnce({ session_id: \"s1\", assistant_message: \"hello\" });\n+    render(<ChatPanel agentType=\"subject\" subjectCode=\"english\" />);\n+    fireEvent.change(screen.getByPlaceholderText(/输入/), { target: { value: \"hi\" } });\n+    fireEvent.click(screen.getByRole(\"button\", { name: /发送/ }));\n+    await waitFor(() => screen.getByText(\"hello\"));\n+  });\n+});\n+```\n+\n+- [ ] **Step 2: Implement API client**\n+\n+Create `frontend/src/api/chat.ts`:\n+\n+```ts\n+import { api } from \"./client\";\n+\n+export type ChatPostRequest = {\n+  agent_type: \"planner\" | \"subject\";\n+  subject_code?: string | null;\n+  message: string;\n+};\n+\n+export type ChatPostResponse = {\n+  session_id: string;\n+  assistant_message: string;\n+};\n+\n+export function postChat(body: ChatPostRequest) {\n+  return api<ChatPostResponse>(\"/chat\", { method: \"POST\", body: JSON.stringify(body) });\n+}\n+```\n+\n+- [ ] **Step 3: Implement `ChatPanel` and subcomponents**\n+\n+`ChatPanel` props: `{ agentType, subjectCode }`.\n+\n+Behavior:\n+- show messages list\n+- send message (optimistically append user message)\n+- call `postChat` and append assistant message\n+- disable send while pending\n+\n+- [ ] **Step 4: Mount ChatPanel in `Workspace.tsx`**\n+\n+Replace the placeholder text in the right-side panel with `<ChatPanel agentType=\"subject\" subjectCode={current} />` (if `current` exists; otherwise show “请先开通科目”).\n+\n+- [ ] **Step 5: Run tests and build**\n+\n+Run:\n+```bash\n+cd frontend\n+npm test -- --run\n+npm run build\n+```\n+\n+Expected: tests pass and build succeeds.\n+\n+- [ ] **Step 6: Commit**\n+\n+```bash\n+git add frontend/src/api/chat.ts frontend/src/components/chat frontend/src/pages/student/Workspace.tsx frontend/tests/ChatPanel.test.tsx\n+git commit -m \"feat(p2): add student chat panel\"\n+```\n+\n+---\n+\n+## Task 7: Final verification (P2)\n+\n+**Files:** none\n+\n+- [ ] **Step 1: Backend tests**\n+\n+Run: `cd backend && pytest -q`\n+\n+- [ ] **Step 2: Frontend tests**\n+\n+Run: `cd frontend && npm test -- --run`\n+\n+- [ ] **Step 3: Manual smoke**\n+\n+1) Ensure `docker compose up -d`.\n+\n+2) Seed DB (if needed): `cd backend && python -m app.seed`.\n+\n+3) Start backend: `uvicorn app.main:app --reload --port 8000`.\n+\n+4) Start frontend: `cd frontend && npm run dev`.\n+\n+5) Login as `student@demo.example` / `stud123` → `/student/workspace` → send a message in chat panel → should see assistant response.\n+\n+- [ ] **Step 4: Commit (no-op)**\n+\n+No commit needed.\n+\n---\n+\n## Self-Review (controller)\n+\n- Spec coverage: model gateway configurable + chat persistence + basic UI exists.\n+- Placeholder scan: no TBD/TODO.\n+- Naming: `model_policies.scene` matches `chat` usage.\n+\n---\n+\n## Execution Handoff\n+\n**Plan complete and saved to `docs/superpowers/plans/2026-05-27-p2-agent-gateway.md`. Two execution options:**\n+\n+**1. Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks\n+\n+**2. Inline Execution** - execute tasks in this session with checkpoints\n+\n+**Which approach?**\n+
