# Wrong-Book Inline Explain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-item「错题讲解」control on the student Wrong Book page that calls subject `/chat` with `item_id` and shows the assistant reply under the card.

**Architecture:** Reuse existing `postChat` + `explain_wrong_book_item`. Frontend keeps per-item explain state on the card; mock gateway parses `item_id=<uuid>` so local/demo routing matches production tool args.

**Tech Stack:** FastAPI, ModelGateway mock, React, Vitest, Testing Library, `ChatRichText`

**Spec:** `docs/superpowers/specs/2026-07-23-wrong-book-inline-explain-design.md`

## Global Constraints

- Stay on Wrong Book page (no Workspace navigation / ChatPanel deep-link)
- Explanation may include correct answers (does not change practice conceal UI)
- Prefer `item_id` in chat message; include page「错题 N」only as human-readable fallback
- Use each item’s own `subject_code` (works under「全部科目」)
- Session-memory only for explain text; no backend persistence of explanations
- No new REST explain endpoint; no streaming

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/services/model_gateway.py` | Mock: parse `item_id=` for `explain_wrong_book_item` |
| `backend/tests/test_chat_tools_extended.py` | Mock chat regression for `item_id` message |
| `frontend/src/pages/student/WrongBook.tsx` |「错题讲解」button, loading/error/ready panel, `postChat` |
| `frontend/src/components/chat/ChatRichText.tsx` | Reuse for assistant markdown/math (no change expected) |
| `frontend/src/api/chat.ts` | Existing `postChat` (no change expected) |
| `frontend/tests/WrongBook.test.tsx` | UI tests for explain flow |

---

### Task 1: Mock gateway routes explain by `item_id`

**Files:**
- Modify: `backend/app/services/model_gateway.py` (mock `explain_wrong_book_item` branch ~253–266)
- Modify: `backend/tests/test_chat_tools_extended.py`
- Test: `backend/tests/test_chat_tools_extended.py`

**Interfaces:**
- Consumes: existing `explain_wrong_book_item` tool + `ModelGateway` mock completion path
- Produces: when `last_user` matches wrong-book explain intent and contains `item_id=<uuid>`, tool arguments are `{"item_id": "<uuid>"}`; otherwise keep list_index from「第 N 题」(default 1)

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_chat_tools_extended.py` (reuse `_seed_student` and patterns from `test_mock_chat_wrong_book_uses_explain_wrong_book_item`):

```python
def test_mock_chat_wrong_book_explain_uses_item_id(db_session):
    from app.models import WrongBookItem

    student = _seed_student(db_session)
    older = WrongBookItem(
        student_user_id=student.id,
        subject_code="english",
        source_type="placement",
        question_snapshot_json={"stem": "OLDER_STEM", "seq": 1, "q_type": "single_choice"},
        answer_snapshot_json={"content": "A"},
        correct_snapshot_json={"answer_key": "B"},
        status="active",
    )
    newer = WrongBookItem(
        student_user_id=student.id,
        subject_code="english",
        source_type="self_test",
        question_snapshot_json={"stem": "NEWER_STEM", "seq": 2, "q_type": "single_choice"},
        answer_snapshot_json={"content": "C"},
        correct_snapshot_json={"answer_key": "D"},
        status="active",
    )
    db_session.add_all([older, newer])
    db_session.commit()
    db_session.refresh(older)

    # List order is created_at desc → newer is list_index 1. Point at older via item_id.
    turn = ChatToolLoop(model_gateway=ModelGateway()).run(
        db_session,
        student_user_id=student.id,
        agent_type="subject",
        subject_code="english",
        provider="mock",
        model="mock-v1",
        params={},
        history_messages=[],
        user_message=(
            f"请讲解错题本条目 item_id={older.id}（页面错题 2）。"
            "结合我的当时作答说明错因与正确思路。"
        ),
    )
    assert "explain_wrong_book_item" in turn.tools_used
    assert "explain_question" not in turn.tools_used
    assert "OLDER_STEM" in turn.assistant_message
    assert "NEWER_STEM" not in turn.assistant_message
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend && python -m pytest tests/test_chat_tools_extended.py::test_mock_chat_wrong_book_explain_uses_item_id -v
```

Expected: FAIL — mock uses `list_index: 1` (or default) and message mentions newer stem / wrong item.

- [ ] **Step 3: Implement mock `item_id` parsing**

In `backend/app/services/model_gateway.py`, replace the `explain_wrong_book_item` mock block with:

```python
        if "explain_wrong_book_item" in tool_names and re.search(
            r"错题本", last_user
        ) and re.search(r"讲|讲解|解释|分析|为什么|第.?题|item_id", last_user):
            item_m = re.search(
                r"item_id\s*=\s*([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
                last_user,
            )
            if item_m:
                args = {"item_id": item_m.group(1)}
            else:
                m = re.search(r"第\s*(\d+)\s*题", last_user)
                idx = int(m.group(1)) if m else 1
                args = {"list_index": idx}
            return ModelCompletion(
                tool_calls=(
                    ToolCall(
                        id=f"call_{uuid.uuid4().hex[:8]}",
                        name="explain_wrong_book_item",
                        arguments=json.dumps(args, ensure_ascii=False),
                    ),
                )
            )
```

Keep the existing `list_wrong_book` / `explain_question` blocks unchanged and ordered after this block.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
cd backend && python -m pytest tests/test_chat_tools_extended.py::test_mock_chat_wrong_book_explain_uses_item_id tests/test_chat_tools_extended.py::test_mock_chat_wrong_book_uses_explain_wrong_book_item -v
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/model_gateway.py backend/tests/test_chat_tools_extended.py
git commit -m "$(cat <<'EOF'
fix(chat): mock explain_wrong_book_item honors item_id in message

EOF
)"
```

---

### Task 2: Wrong Book card「错题讲解」UI

**Files:**
- Modify: `frontend/src/pages/student/WrongBook.tsx`
- Modify: `frontend/tests/WrongBook.test.tsx`
- Test: `frontend/tests/WrongBook.test.tsx`

**Interfaces:**
- Consumes: `postChat({ agent_type, subject_code, message })` → `{ assistant_message }`; `ChatRichText`; `WrongBookItemOut.id`, `.subject_code`; card `index`
- Produces: per-card explain UX: idle / loading / ready / error; message shape  
  `请讲解错题本条目 item_id=${item.id}（页面错题 ${index}）。结合我的当时作答说明错因与正确思路。`

- [ ] **Step 1: Write the failing tests**

Extend `frontend/tests/WrongBook.test.tsx`. Update `mockFetchWrongBook` so `/api/chat` (or whatever `api` prefixes — match existing client, typically path containing `/chat`) returns a fixed assistant message. Keep existing wrong-book fixtures.

Add:

```tsx
  it("explains a wrong-book item inline via chat", async () => {
    const fetchMock = vi.fn(async (input: any, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/api/student/me")) {
        return new Response(
          JSON.stringify({
            id: "u1",
            email: "s@example.com",
            name: "s",
            exam_year: 2027,
            subject_codes: ["english"],
          }),
          { status: 200 },
        );
      }
      if (url.includes("/api/chat") && init?.method === "POST") {
        const body = JSON.parse(String(init.body));
        expect(body.agent_type).toBe("subject");
        expect(body.subject_code).toBe("english");
        expect(body.message).toContain("item_id=w1");
        expect(body.message).toContain("错题 1");
        return new Response(
          JSON.stringify({
            session_id: "sess1",
            assistant_message: "这是讲解：正确答案是 A。",
            tools_used: ["explain_wrong_book_item"],
          }),
          { status: 200 },
        );
      }
      if (url.includes("/api/student/wrong-book")) {
        return new Response(
          JSON.stringify([
            {
              id: "w1",
              subject_code: "english",
              knowledge_node_id: null,
              source_type: "self_test",
              source_id: "s1",
              question_snapshot_json: {
                stem: "题干",
                q_type: "single_choice",
                choices: [
                  { key: "A", text: "选项甲" },
                  { key: "B", text: "选项乙" },
                ],
              },
              answer_snapshot_json: { content: "B" },
              correct_snapshot_json: { answer_key: "A" },
              status: "active",
              wrong_count: 1,
              consecutive_correct_count: 0,
              mastered_at: null,
              last_practice_at: null,
              created_at: "2026-05-28T00:00:00Z",
            },
          ]),
          { status: 200 },
        );
      }
      return new Response(JSON.stringify({ detail: "not found" }), { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();
    await waitFor(() => expect(screen.getByText("题干")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /错题讲解/ }));
    await waitFor(() => expect(screen.getByText(/这是讲解：正确答案是 A/)).toBeTruthy());
  });

  it("shows explain error and allows retry", async () => {
    let chatCalls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: any, init?: RequestInit) => {
        const url = String(input);
        if (url.includes("/api/student/me")) {
          return new Response(
            JSON.stringify({
              id: "u1",
              email: "s@example.com",
              name: "s",
              exam_year: 2027,
              subject_codes: ["english"],
            }),
            { status: 200 },
          );
        }
        if (url.includes("/api/chat") && init?.method === "POST") {
          chatCalls += 1;
          if (chatCalls === 1) {
            return new Response(JSON.stringify({ detail: "boom" }), { status: 500 });
          }
          return new Response(
            JSON.stringify({
              session_id: "sess2",
              assistant_message: "重试成功讲解",
              tools_used: ["explain_wrong_book_item"],
            }),
            { status: 200 },
          );
        }
        if (url.includes("/api/student/wrong-book")) {
          return new Response(
            JSON.stringify([
              {
                id: "w1",
                subject_code: "english",
                knowledge_node_id: null,
                source_type: "self_test",
                source_id: "s1",
                question_snapshot_json: {
                  stem: "题干",
                  q_type: "single_choice",
                  choices: [{ key: "A", text: "选项甲" }],
                },
                answer_snapshot_json: { content: "B" },
                correct_snapshot_json: { answer_key: "A" },
                status: "active",
                wrong_count: 1,
                consecutive_correct_count: 0,
                mastered_at: null,
                last_practice_at: null,
                created_at: "2026-05-28T00:00:00Z",
              },
            ]),
            { status: 200 },
          );
        }
        return new Response(JSON.stringify({ detail: "not found" }), { status: 404 });
      }),
    );

    renderPage();
    await waitFor(() => expect(screen.getByText("题干")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /错题讲解/ }));
    await waitFor(() => expect(screen.getByText(/讲解失败|请求失败/)).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /重试/ }));
    await waitFor(() => expect(screen.getByText(/重试成功讲解/)).toBeTruthy());
  });
```

If the shared `api` client uses a different path than `/api/chat`, align the URL matcher with `frontend/src/api/client.ts` / `chat.ts` (inspect once before writing the test).

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd frontend && npm test -- --run tests/WrongBook.test.tsx
```

Expected: FAIL — no「错题讲解」button / no chat call.

- [ ] **Step 3: Implement card explain UI**

In `frontend/src/pages/student/WrongBook.tsx`:

1. Import `postChat` from `@/api/chat` and `ChatRichText` from `@/components/chat/ChatRichText`.

2. Inside `WrongBookItemCard`, add local state:

```tsx
  const [explainOpen, setExplainOpen] = useState(false);
  const [explainLoading, setExplainLoading] = useState(false);
  const [explainText, setExplainText] = useState<string | null>(null);
  const [explainError, setExplainError] = useState<string | null>(null);

  async function runExplain() {
    if (explainLoading) return;
    setExplainOpen(true);
    setExplainLoading(true);
    setExplainError(null);
    try {
      const resp = await postChat({
        agent_type: "subject",
        subject_code: item.subject_code,
        message:
          `请讲解错题本条目 item_id=${item.id}（页面错题 ${index}）。` +
          "结合我的当时作答说明错因与正确思路。",
      });
      setExplainText(resp.assistant_message);
    } catch (err) {
      setExplainError((err as Error).message || "讲解失败");
    } finally {
      setExplainLoading(false);
    }
  }
```

3. After practice / archive controls, add actions + panel:

```tsx
      <div className="flex flex-wrap gap-3 items-center">
        <button
          type="button"
          className="text-sm text-slate-900 underline disabled:opacity-50"
          disabled={explainLoading}
          onClick={() => void runExplain()}
        >
          {explainLoading ? "讲解中…" : "错题讲解"}
        </button>
        {explainOpen && explainText ? (
          <button
            type="button"
            className="text-sm text-slate-500 underline"
            onClick={() => setExplainOpen((v) => !v)}
          >
            {explainOpen ? "收起讲解" : "展开讲解"}
          </button>
        ) : null}
      </div>

      {explainOpen ? (
        <div className="rounded border border-slate-200 bg-slate-50 p-3 text-sm space-y-2">
          {explainLoading && !explainText ? <p className="text-slate-500">正在生成讲解…</p> : null}
          {explainError ? (
            <div className="space-y-2">
              <p className="text-red-600">讲解失败：{explainError}</p>
              <button
                type="button"
                className="text-sm text-slate-900 underline"
                disabled={explainLoading}
                onClick={() => void runExplain()}
              >
                重试
              </button>
            </div>
          ) : null}
          {explainText && !explainError ? <ChatRichText text={explainText} /> : null}
        </div>
      ) : null}
```

Fix the collapse control so when `explainOpen` is false but `explainText` exists, show「展开讲解」that only sets `explainOpen` true without re-fetching (split “重新讲解” vs “展开” if needed: primary button always re-fetches; secondary toggles open when cached text exists).

Recommended final behavior matching the spec:

- Primary「错题讲解」/「讲解中…」always calls `runExplain` (re-fetch / overwrite)
- If `explainText` and panel closed: show「展开讲解」→ `setExplainOpen(true)` only
- If panel open and has text: show「收起讲解」→ `setExplainOpen(false)`

Do **not** toggle `showAnswers` / practice reveal when explaining.

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
cd frontend && npm test -- --run tests/WrongBook.test.tsx
```

Expected: all tests in the file PASS (including existing conceal/practice test).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/student/WrongBook.tsx frontend/tests/WrongBook.test.tsx
git commit -m "$(cat <<'EOF'
feat(wrong-book): add inline AI explain per item

EOF
)"
```

---

### Task 3: Spec status + smoke checklist

**Files:**
- Modify: `docs/superpowers/specs/2026-07-23-wrong-book-inline-explain-design.md` (status → 已实现)

**Interfaces:**
- Consumes: Tasks 1–2 complete
- Produces: spec marked done; manual smoke notes below

- [ ] **Step 1: Update spec status**

Change header `**状态：** 待实现` → `**状态：** 已实现`.

- [ ] **Step 2: Manual smoke (local)**

With backend + frontend running and a demo student logged in:

1. Open `/student/wrong-book`, pick any active item  
2. Click「错题讲解」→ panel shows loading then explanation text  
3. Confirm「当时答案」still visible; reference answer may stay hidden until practice  
4. Collapse / expand without re-request; click「错题讲解」again to refresh  
5. Force chat failure (optional) and confirm「重试」works  

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-07-23-wrong-book-inline-explain-design.md
git commit -m "$(cat <<'EOF'
docs: mark wrong-book inline explain spec implemented

EOF
)"
```

---

## Spec coverage self-review

| Spec requirement | Task |
|------------------|------|
| Button on each card, all statuses | Task 2 |
| Stay on page, expand under card | Task 2 |
| `postChat` subject + `item_id` message | Task 2 |
| Own `subject_code` | Task 2 |
| ChatRichText rendering | Task 2 |
| loading / error+retry / re-fetch overwrite / collapse cache | Task 2 |
| Explain may leak answers; practice conceal unchanged | Task 2 (explicit non-touch) |
| Mock `item_id` routing | Task 1 |
| FE + BE tests | Tasks 1–2 |
| No new REST / no Workspace deep-link / no persistence | Global + Tasks 1–2 |

Placeholder scan: none. Message string and mock regex are identical across tasks.
