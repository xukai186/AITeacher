# Question Bank Multi-Image OCR Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade question-bank OCR into a unified workbench supporting single-image multi-question segmentation (with raw-text manual split fallback) and multi-image single-question merge recognition, with per-question edit/delete, batch enrich, and batch submit reusing existing create/enrich semantics.

**Architecture:** Extend `POST /org/question-bank/ocr` with `mode` + `asset_ids` and a discriminated response (`segmented` | `raw_text_fallback` | `single_question`). `QuestionOCRService` gains mode-specific prompts and parsers. Frontend replaces the single-draft OCR block with an OCR workbench component that holds a draft list, batch-enriches, and loops create calls. Legacy `{ asset_id }` OCR requests remain supported for backward compatibility.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy, pytest; React, TanStack Query, Vitest

**Spec:** `docs/superpowers/specs/2026-08-20-question-bank-multi-image-ocr-design.md`

## Global Constraints

- Phase order: **Phase A (single_image_multi_question) first**, then **Phase B (multi_image_single_question)**
- One-image-multi-question confirm: edit/delete per draft, then **batch submit** (frontend loops existing create)
- Segmentation failure: return `raw_text_fallback` with `raw_text`; **do not** fall back to single-question auto-parse
- Multi-image-single-question: merge images **in upload order**; `source_image_asset_id` = **first** asset id
- All created items: `source_type = ocr_import`, same org asset validation as PR #53
- No new DB columns (`source_image_asset_ids`, `ocr_batch_id`, slice assets)
- No backend batch-create transaction API
- Keep existing enrich / create / dedupe / review semantics unchanged
- Python tests: `/Users/bytedance/cursor/AITeacher/backend/.venv/bin/python -m pytest …`
- Frontend tests: `npm test -- QuestionBankOcr` from `frontend/`

## File map

| File | Responsibility |
|------|----------------|
| `backend/app/schemas/question_bank.py` | OCR mode request + discriminated OCR response models |
| `backend/app/services/question_ocr.py` | Mode-specific extract/segment/merge + JSON parsing |
| `backend/app/routers/org_question_bank.py` | Extended `/ocr` handler + validation |
| `backend/tests/test_question_ocr.py` | Service + API tests for all OCR modes |
| `frontend/src/api/questionBank.ts` | OCR mode types + `recognizeQuestions()` |
| `frontend/src/components/questionBank/QuestionBankOcrWorkbench.tsx` | Draft list, raw-text fallback, batch enrich/submit |
| `frontend/src/components/questionBank/QuestionBankPage.tsx` | Wire workbench into create flow |
| `frontend/tests/QuestionBankOcr.test.tsx` | Segmented, fallback, batch submit, multi-image |
| `docs/superpowers/specs/2026-08-20-question-bank-multi-image-ocr-design.md` | Mark 已实现 when done |

---

## Phase A — Single-image multi-question

### Task 1: Backend schemas — OCR modes + discriminated response

**Files:**
- Modify: `backend/app/schemas/question_bank.py`

**Interfaces:**
- Consumes: existing `QuestionOCROut` fields (`q_type`, `stem`, `choices`, `answer_key`)
- Produces:
  - `QuestionOCRMode = Literal["single_image_single_question", "single_image_multi_question", "multi_image_single_question"]`
  - `QuestionOCRRequest` with `mode`, `asset_id` (legacy), `asset_ids`
  - `QuestionDraftOut` (reuse OCR question shape)
  - `QuestionOCROut` kept for legacy single-question flat response OR replaced by union — see router Task 2
  - `QuestionOCRSegmentedOut`, `QuestionOCRRawTextFallbackOut`, `QuestionOCRSingleQuestionOut`
  - `QuestionOCRResponse` = Annotated union discriminated by `mode`

- [ ] **Step 1: Add OCR schema types**

In `backend/app/schemas/question_bank.py`, replace/extend OCR section:

```python
from typing import Annotated, Literal, Self
from pydantic import Field, model_validator

QuestionOCRMode = Literal[
    "single_image_single_question",
    "single_image_multi_question",
    "multi_image_single_question",
]

class QuestionDraftOut(BaseModel):
    q_type: str
    stem: str
    choices: list[dict] | None
    answer_key: str | None


class QuestionOCRRequest(BaseModel):
    mode: QuestionOCRMode | None = None
    asset_id: uuid.UUID | None = None
    asset_ids: list[uuid.UUID] | None = None

    @model_validator(mode="after")
    def normalize_assets(self) -> Self:
        if self.mode is None and self.asset_id is not None:
            self.mode = "single_image_single_question"
            self.asset_ids = [self.asset_id]
            return self
        if self.mode is None:
            raise ValueError("mode or asset_id is required")
        if not self.asset_ids:
            raise ValueError("asset_ids is required")
        if self.mode == "single_image_multi_question" and len(self.asset_ids) != 1:
            raise ValueError("single_image_multi_question requires exactly one asset")
        if self.mode == "multi_image_single_question" and len(self.asset_ids) < 2:
            raise ValueError("multi_image_single_question requires at least two assets")
        if self.mode == "single_image_single_question" and len(self.asset_ids) != 1:
            raise ValueError("single_image_single_question requires exactly one asset")
        return self


class QuestionOCRSegmentedOut(BaseModel):
    mode: Literal["segmented"] = "segmented"
    questions: list[QuestionDraftOut]


class QuestionOCRRawTextFallbackOut(BaseModel):
    mode: Literal["raw_text_fallback"] = "raw_text_fallback"
    raw_text: str


class QuestionOCRSingleQuestionOut(BaseModel):
    mode: Literal["single_question"] = "single_question"
    question: QuestionDraftOut


QuestionOCRResponse = Annotated[
    QuestionOCRSegmentedOut | QuestionOCRRawTextFallbackOut | QuestionOCRSingleQuestionOut,
    Field(discriminator="mode"),
]

# Keep legacy flat shape alias for tests that assert old response during transition:
class QuestionOCROut(QuestionDraftOut):
    pass
```

- [ ] **Step 2: Verify import**

Run:

```bash
cd /Users/bytedance/cursor/AITeacher/backend
.venv/bin/python -c "from app.schemas.question_bank import QuestionOCRRequest, QuestionOCRResponse"
```

Expected: no import error.

---

### Task 2: Backend service — segmentation + legacy single extract

**Files:**
- Modify: `backend/app/services/question_ocr.py`
- Test: `backend/tests/test_question_ocr.py`

**Interfaces:**
- Consumes: `QuestionOCRMode`, org-owned `MediaAsset` rows, `ModelPolicy` scene `paper_gen`
- Produces:
  - `QuestionOCRService.extract_legacy(db, *, org_id, asset_id) -> OCRQuestion` (rename current `extract`)
  - `QuestionOCRService.extract_segmented(db, *, org_id, asset_id) -> SegmentedOCRResult`
  - `SegmentedOCRResult = SegmentedQuestions | RawTextFallback` (dataclasses)

- [ ] **Step 1: Write failing segmentation tests**

Add to `backend/tests/test_question_ocr.py`:

```python
from app.services.question_ocr import QuestionOCRService, SegmentedOCRResult


def test_extract_segmented_returns_multiple_questions(db_session, monkeypatch, tmp_path):
    org = make_org(db_session)
    staff = make_user(db_session, org, role=UserRole.org_staff)
    image_path = tmp_path / "sheet.png"
    image_path.write_bytes(b"fake sheet")
    asset = MediaAsset(
        org_id=org.id,
        created_by=staff.id,
        content_type="image/png",
        storage_path=str(image_path),
    )
    db_session.add(asset)
    db_session.commit()

    monkeypatch.setattr(
        QuestionOCRService,
        "_extract_segmented",
        lambda self, path, content_type, policy: {
            "kind": "segmented",
            "questions": [
                {
                    "q_type": "single_choice",
                    "stem": "Q1",
                    "choices": [{"key": "A", "text": "1"}],
                    "answer_key": "A",
                },
                {
                    "q_type": "short_answer",
                    "stem": "Q2",
                    "choices": None,
                    "answer_key": "open",
                },
            ],
        },
    )

    result = QuestionOCRService().extract_segmented(
        db_session, org_id=org.id, asset_id=asset.id
    )
    assert result.kind == "segmented"
    assert len(result.questions) == 2
    assert result.questions[0].stem == "Q1"


def test_extract_segmented_raw_text_fallback(db_session, monkeypatch, tmp_path):
    org = make_org(db_session)
    staff = make_user(db_session, org, role=UserRole.org_staff)
    image_path = tmp_path / "sheet.png"
    image_path.write_bytes(b"fake sheet")
    asset = MediaAsset(
        org_id=org.id,
        created_by=staff.id,
        content_type="image/png",
        storage_path=str(image_path),
    )
    db_session.add(asset)
    db_session.commit()

    monkeypatch.setattr(
        QuestionOCRService,
        "_extract_segmented",
        lambda self, path, content_type, policy: {
            "kind": "raw_text_fallback",
            "raw_text": "1. First question ... 2. Second question ...",
        },
    )

    result = QuestionOCRService().extract_segmented(
        db_session, org_id=org.id, asset_id=asset.id
    )
    assert result.kind == "raw_text_fallback"
    assert "First question" in result.raw_text
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
/Users/bytedance/cursor/AITeacher/backend/.venv/bin/python -m pytest backend/tests/test_question_ocr.py::test_extract_segmented_returns_multiple_questions backend/tests/test_question_ocr.py::test_extract_segmented_raw_text_fallback -v
```

Expected: FAIL (`extract_segmented` not defined).

- [ ] **Step 3: Implement segmentation service**

In `question_ocr.py`, add dataclasses and methods. Keep existing `extract()` as thin wrapper calling legacy single-image path.

```python
@dataclass(frozen=True)
class SegmentedQuestions:
    kind: Literal["segmented"]
    questions: list[OCRQuestion]


@dataclass(frozen=True)
class RawTextFallback:
    kind: Literal["raw_text_fallback"]
    raw_text: str


SegmentedOCRResult = SegmentedQuestions | RawTextFallback


class QuestionOCRService:
    def extract_segmented(
        self,
        db: Session,
        *,
        org_id: uuid.UUID,
        asset_id: uuid.UUID,
    ) -> SegmentedOCRResult:
        asset = self._load_asset(db, org_id=org_id, asset_id=asset_id)
        policy = self._load_policy(db, org_id=org_id)
        data = self._extract_segmented(
            Path(asset.storage_path), asset.content_type, policy
        )
        return self._validate_segmented(data)

    def _extract_segmented(self, path: Path, content_type: str, policy: ModelPolicy | None) -> dict:
        if policy is None:
            raise RuntimeError("paper_gen model policy is not configured")
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        completion = self._gateway.complete(
            provider=policy.provider,
            model=policy.model,
            scene="paper_gen",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "This image may contain multiple independent exam questions. "
                                "If you can reliably split them, return strict JSON: "
                                '{"kind":"segmented","questions":[{q_type,stem,choices,answer_key},...]} '
                                "where choices is a list of {key,text} or null. "
                                "If you cannot reliably split, do NOT invent questions; "
                                'return {"kind":"raw_text_fallback","raw_text":"..."} with the best OCR text.'
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{content_type};base64,{encoded}"},
                        },
                    ],
                }
            ],
            tools=None,
            params=policy.params or {},
        )
        return self._parse_json(completion.text or "")

    @staticmethod
    def _validate_segmented(data: dict) -> SegmentedOCRResult:
        kind = str(data.get("kind") or "").strip()
        if kind == "raw_text_fallback":
            raw_text = str(data.get("raw_text") or "").strip()
            if not raw_text:
                raise ValueError("raw_text_fallback requires raw_text")
            return RawTextFallback(kind="raw_text_fallback", raw_text=raw_text)
        if kind != "segmented":
            raise ValueError("segmented OCR response requires kind segmented or raw_text_fallback")
        questions_raw = data.get("questions")
        if not isinstance(questions_raw, list) or not questions_raw:
            raise ValueError("segmented OCR response requires non-empty questions")
        questions = [QuestionOCRService._validate(q) for q in questions_raw]
        return SegmentedQuestions(kind="segmented", questions=questions)

    def _load_asset(self, db, *, org_id, asset_id) -> MediaAsset:
        asset = db.execute(
            select(MediaAsset).where(
                MediaAsset.id == asset_id,
                MediaAsset.org_id == org_id,
            )
        ).scalar_one_or_none()
        if asset is None:
            raise LookupError("media asset not found")
        return asset

    def _load_policy(self, db, *, org_id) -> ModelPolicy | None:
        return db.execute(
            select(ModelPolicy).where(
                ModelPolicy.org_id == org_id,
                ModelPolicy.scene == "paper_gen",
            )
        ).scalar_one_or_none()
```

Refactor existing `extract()` to use `_load_asset` / `_load_policy` helpers (DRY).

- [ ] **Step 4: Run OCR service tests**

Run:

```bash
/Users/bytedance/cursor/AITeacher/backend/.venv/bin/python -m pytest backend/tests/test_question_ocr.py -v
```

Expected: all PASS (legacy test still passes).

---

### Task 3: Backend router — extended `/ocr` with mode dispatch

**Files:**
- Modify: `backend/app/routers/org_question_bank.py`
- Test: `backend/tests/test_question_ocr.py`

**Interfaces:**
- Consumes: `QuestionOCRRequest`, service methods from Task 2
- Produces: `QuestionOCRResponse` JSON; legacy `{ asset_id }` → flat single question compatible response OR `single_question` wrapper — **choose flat for legacy** to avoid breaking existing frontend until Task 5 updates client

- [ ] **Step 1: Write failing API tests**

```python
def test_ocr_single_image_multi_question_segmented(client, db_session, monkeypatch, tmp_path):
    headers, staff = _staff_headers(client, db_session)
    monkeypatch.setattr("app.services.media_assets.MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(
        QuestionOCRService,
        "_extract_segmented",
        lambda self, path, content_type, policy: {
            "kind": "segmented",
            "questions": [
                {"q_type": "single_choice", "stem": "Q1", "choices": None, "answer_key": "A"},
                {"q_type": "short_answer", "stem": "Q2", "choices": None, "answer_key": "x"},
            ],
        },
    )
    uploaded = client.post(
        "/org/question-bank/upload-image",
        files={"file": ("sheet.png", PNG_BYTES, "image/png")},
        headers=headers,
    )
    asset_id = uploaded.json()["asset_id"]
    resp = client.post(
        "/org/question-bank/ocr",
        json={"mode": "single_image_multi_question", "asset_ids": [asset_id]},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "segmented"
    assert len(body["questions"]) == 2


def test_ocr_single_image_multi_question_raw_fallback(client, db_session, monkeypatch, tmp_path):
    headers, _ = _staff_headers(client, db_session)
    monkeypatch.setattr("app.services.media_assets.MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(
        QuestionOCRService,
        "_extract_segmented",
        lambda self, path, content_type, policy: {
            "kind": "raw_text_fallback",
            "raw_text": "raw sheet text",
        },
    )
    uploaded = client.post(
        "/org/question-bank/upload-image",
        files={"file": ("sheet.png", PNG_BYTES, "image/png")},
        headers=headers,
    )
    asset_id = uploaded.json()["asset_id"]
    resp = client.post(
        "/org/question-bank/ocr",
        json={"mode": "single_image_multi_question", "asset_ids": [asset_id]},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {"mode": "raw_text_fallback", "raw_text": "raw sheet text"}


def test_legacy_asset_id_ocr_still_works(client, db_session, monkeypatch, tmp_path):
    headers, _ = _staff_headers(client, db_session)
    monkeypatch.setattr("app.services.media_assets.MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(
        QuestionOCRService,
        "_extract",
        lambda self, path, content_type, policy: {
            "q_type": "short_answer",
            "stem": "Explain the result.",
            "choices": None,
            "answer_key": "Because it follows.",
        },
    )
    uploaded = client.post(
        "/org/question-bank/upload-image",
        files={"file": ("question.png", PNG_BYTES, "image/png")},
        headers=headers,
    )
    asset_id = uploaded.json()["asset_id"]
    resp = client.post(
        "/org/question-bank/ocr",
        json={"asset_id": asset_id},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["stem"] == "Explain the result."
    assert "mode" not in resp.json()
```

- [ ] **Step 2: Implement router dispatch**

Update `extract_question` in `org_question_bank.py`:

```python
@router.post("/ocr")
def extract_question(
    payload: QuestionOCRRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(staff_or_admin),
) -> QuestionOCRResponse | QuestionOCROut:
    svc = QuestionOCRService()
    try:
        if payload.mode == "single_image_multi_question":
            result = svc.extract_segmented(
                db, org_id=actor.org_id, asset_id=payload.asset_ids[0]
            )
            if result.kind == "raw_text_fallback":
                return QuestionOCRRawTextFallbackOut(raw_text=result.raw_text)
            return QuestionOCRSegmentedOut(
                questions=[
                    QuestionDraftOut(
                        q_type=q.q_type,
                        stem=q.stem,
                        choices=q.choices,
                        answer_key=q.answer_key,
                    )
                    for q in result.questions
                ]
            )
        # legacy + single_image_single_question (+ Phase B multi_image_single_question)
        asset_ids = payload.asset_ids
        if payload.mode == "multi_image_single_question":
            question = svc.extract_merged(
                db, org_id=actor.org_id, asset_ids=asset_ids
            )
            return QuestionOCRSingleQuestionOut(
                question=QuestionDraftOut(
                    q_type=question.q_type,
                    stem=question.stem,
                    choices=question.choices,
                    answer_key=question.answer_key,
                )
            )
        question = svc.extract(db, org_id=actor.org_id, asset_id=asset_ids[0])
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except (ValueError, OSError) as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="OCR extraction failed") from exc
    return QuestionOCROut(
        q_type=question.q_type,
        stem=question.stem,
        choices=question.choices,
        answer_key=question.answer_key,
    )
```

Note: `extract_merged` stub raises `NotImplementedError` until Phase B Task 7 — router branch can be added in Task 7 instead; for Task 3 only wire `single_image_multi_question` + legacy.

- [ ] **Step 3: Run OCR tests**

Run:

```bash
/Users/bytedance/cursor/AITeacher/backend/.venv/bin/python -m pytest backend/tests/test_question_ocr.py -v
```

Expected: all PASS.

---

### Task 4: Frontend API — OCR mode types + recognize helper

**Files:**
- Modify: `frontend/src/api/questionBank.ts`

**Interfaces:**
- Consumes: backend discriminated OCR response
- Produces:
  - `QuestionOcrMode` type
  - `RecognizeQuestionsResult` union
  - `recognizeQuestions(mode, assetIds)` function
  - Keep `recognizeQuestion(assetId)` as legacy wrapper

- [ ] **Step 1: Add types and function**

```typescript
export type QuestionOcrMode =
  | "single_image_single_question"
  | "single_image_multi_question"
  | "multi_image_single_question";

export type RecognizedQuestionDraft = QuestionDraft & {
  choices?: Array<{ key: string; text: string }>;
};

export type RecognizeQuestionsResult =
  | { mode: "segmented"; questions: RecognizedQuestionDraft[] }
  | { mode: "raw_text_fallback"; raw_text: string }
  | { mode: "single_question"; question: RecognizedQuestionDraft };

export function recognizeQuestions(
  mode: QuestionOcrMode,
  assetIds: string[],
): Promise<RecognizeQuestionsResult> {
  return api<RecognizeQuestionsResult>("/org/question-bank/ocr", {
    method: "POST",
    body: JSON.stringify({ mode, asset_ids: assetIds }),
  });
}

export function recognizeQuestion(assetId: string) {
  return api<RecognizedQuestion>("/org/question-bank/ocr", {
    method: "POST",
    body: JSON.stringify({ asset_id: assetId }),
  });
}
```

- [ ] **Step 2: Typecheck**

Run:

```bash
cd /Users/bytedance/cursor/AITeacher/frontend
npm run build 2>&1 | tail -5
```

Expected: build succeeds (or only unrelated warnings).

---

### Task 5: Frontend workbench component — Phase A (segmented + fallback + batch)

**Files:**
- Create: `frontend/src/components/questionBank/QuestionBankOcrWorkbench.tsx`
- Modify: `frontend/src/components/questionBank/QuestionBankPage.tsx`
- Test: `frontend/tests/QuestionBankOcr.test.tsx`

**Interfaces:**
- Consumes: `uploadQuestionImage`, `recognizeQuestions`, `enrichQuestion`, `createQuestion`
- Produces: React component props:

```typescript
type OcrWorkbenchProps = {
  role: QuestionBankRole;
  scope: "org" | "global";
  onSubmitted: () => void;
  onCancel: () => void;
};
```

Internal draft shape:

```typescript
type OcrDraftItem = {
  localId: string;
  stem: string;
  qType: string;
  choicesText: string;
  answerKey: string;
  enrichment?: Enrichment | null;
  enrichError?: string | null;
  submitError?: string | null;
  submitted?: boolean;
};
```

- [ ] **Step 1: Write failing test — segmented batch flow**

Add to `QuestionBankOcr.test.tsx`:

```typescript
it("segments one image into multiple drafts and batch submits", async () => {
  const fetchMock = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith("/org/question-bank/upload-image")) {
      return new Response(JSON.stringify({ asset_id: "asset-sheet", storage_key: "k" }), { status: 201 });
    }
    if (url.endsWith("/org/question-bank/ocr")) {
      expect(JSON.parse(String(init?.body))).toEqual({
        mode: "single_image_multi_question",
        asset_ids: ["asset-sheet"],
      });
      return new Response(
        JSON.stringify({
          mode: "segmented",
          questions: [
            { q_type: "single_choice", stem: "Q1", choices: [{ key: "A", text: "1" }], answer_key: "A" },
            { q_type: "short_answer", stem: "Q2", choices: null, answer_key: "x" },
          ],
        }),
        { status: 200 },
      );
    }
    if (url.endsWith("/org/question-bank/enrich")) {
      return new Response(
        JSON.stringify({
          subject_code: "english",
          knowledge_node_id: null,
          difficulty: 2,
          analysis_text: "analysis",
          q_type: null,
        }),
        { status: 200 },
      );
    }
    if (url.endsWith("/org/question-bank") && init?.method === "POST") {
      const body = JSON.parse(String(init?.body));
      return new Response(
        JSON.stringify({ id: `q-${body.stem}`, stem: body.stem, status: "pending_review" }),
        { status: 201 },
      );
    }
    if (url.includes("/org/question-bank")) {
      return new Response(JSON.stringify([]), { status: 200 });
    }
    return new Response("not found", { status: 404 });
  });
  vi.stubGlobal("fetch", fetchMock);

  renderPage();
  fireEvent.click(screen.getByRole("button", { name: "新建题目" }));
  fireEvent.click(screen.getByRole("button", { name: "图片识别添加" }));
  fireEvent.click(screen.getByRole("button", { name: "一图多题" }));
  fireEvent.change(screen.getByLabelText("题目图片"), {
    target: { files: [new File(["img"], "sheet.png", { type: "image/png" })] },
  });
  fireEvent.click(screen.getByRole("button", { name: "开始识别" }));

  await waitFor(() => {
    expect(screen.getByDisplayValue("Q1")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Q2")).toBeInTheDocument();
  });

  fireEvent.click(screen.getByRole("button", { name: "批量智能补全" }));
  await waitFor(() => expect(screen.getAllByText("english").length).toBeGreaterThan(0));

  fireEvent.click(screen.getByRole("button", { name: "批量提交" }));
  await waitFor(() => {
    const creates = fetchMock.mock.calls.filter(
      ([, init]) => String(init?.method) === "POST" && String(fetchMock.mock.calls[0]).includes("question-bank"),
    );
    expect(creates.length).toBeGreaterThanOrEqual(2);
  });
});
```

Adjust selectors to match implementation labels.

- [ ] **Step 2: Implement `QuestionBankOcrWorkbench.tsx`**

Key behaviors:
- Sub-mode toggle: **一图多题** | **多图一题** (multi-image disabled/hidden until Phase B, or show disabled with tooltip)
- Upload → `recognizeQuestions("single_image_multi_question", [assetId])`
- `segmented`: map to `drafts[]` state
- `raw_text_fallback`: show read-only `raw_text` + 「新增题目」 button creating blank drafts
- Per-draft edit fields + delete button
- 「批量智能补全」: `Promise.allSettled` over drafts calling `enrichQuestion`
- 「批量提交」: loop `createQuestion` with `source_type: "ocr_import"`, `source_image_asset_id: sourceAssetId`, per-draft enrichment; mark successes, keep failures

- [ ] **Step 3: Wire into `QuestionBankPage.tsx`**

Replace inline OCR single-draft block when `createMode === "ocr"` with:

```tsx
<QuestionBankOcrWorkbench
  role={role}
  scope={scope}
  onSubmitted={() => { closeCreate(); resetList(); queryClient.invalidateQueries({ queryKey: ["question-bank"] }); }}
  onCancel={closeCreate}
/>
```

Remove now-unused single-draft OCR state (`ocrFile`, `ocrMutation`, `ocrReady` gate on enrich) from page-level create flow for OCR mode.

Keep **手工添加** path unchanged.

- [ ] **Step 4: Add raw-text fallback test**

```typescript
it("shows raw OCR text and lets user manually add drafts", async () => {
  // mock OCR returns raw_text_fallback
  // assert raw text visible
  // click 新增题目
  // fill stem, batch submit
});
```

- [ ] **Step 5: Run frontend tests**

Run:

```bash
cd /Users/bytedance/cursor/AITeacher/frontend
npm test -- QuestionBankOcr.test.tsx
```

Expected: all PASS.

---

## Phase B — Multi-image single-question

### Task 6: Backend service — merge multi-image extract

**Files:**
- Modify: `backend/app/services/question_ocr.py`
- Test: `backend/tests/test_question_ocr.py`

**Interfaces:**
- Produces: `QuestionOCRService.extract_merged(db, *, org_id, asset_ids: list[uuid.UUID]) -> OCRQuestion`

- [ ] **Step 1: Write failing merged extract test**

```python
def test_extract_merged_reads_assets_in_order(db_session, monkeypatch, tmp_path):
    org = make_org(db_session)
    staff = make_user(db_session, org, role=UserRole.org_staff)
    paths = []
    assets = []
    for idx in range(2):
        path = tmp_path / f"part{idx}.png"
        path.write_bytes(f"part{idx}".encode())
        paths.append(path)
        asset = MediaAsset(
            org_id=org.id,
            created_by=staff.id,
            content_type="image/png",
            storage_path=str(path),
        )
        db_session.add(asset)
        assets.append(asset)
    db_session.commit()

    seen_paths = []

    def fake_extract_merged(self, paths_and_types, policy):
        seen_paths.extend([str(p) for p, _ in paths_and_types])
        return {
            "q_type": "single_choice",
            "stem": "Merged question",
            "choices": [{"key": "A", "text": "Yes"}],
            "answer_key": "A",
        }

    monkeypatch.setattr(QuestionOCRService, "_extract_merged", fake_extract_merged)

    result = QuestionOCRService().extract_merged(
        db_session, org_id=org.id, asset_ids=[a.id for a in assets]
    )
    assert result.stem == "Merged question"
    assert seen_paths == [str(paths[0]), str(paths[1])]
```

- [ ] **Step 2: Implement `_extract_merged`**

Load assets in `asset_ids` order; build message content with ordered images; prompt:

```text
These images describe one single exam question in upload order.
Return strict JSON with q_type, stem, choices, answer_key.
```

- [ ] **Step 3: Run tests**

Run:

```bash
/Users/bytedance/cursor/AITeacher/backend/.venv/bin/python -m pytest backend/tests/test_question_ocr.py -v
```

Expected: all PASS.

---

### Task 7: Backend router + frontend — multi-image single-question mode

**Files:**
- Modify: `backend/app/routers/org_question_bank.py` (wire `extract_merged` — if stubbed in Task 3)
- Modify: `frontend/src/components/questionBank/QuestionBankOcrWorkbench.tsx`
- Test: `backend/tests/test_question_ocr.py`, `frontend/tests/QuestionBankOcr.test.tsx`

- [ ] **Step 1: API test for multi-image mode**

```python
def test_ocr_multi_image_single_question(client, db_session, monkeypatch, tmp_path):
    headers, _ = _staff_headers(client, db_session)
    monkeypatch.setattr("app.services.media_assets.MEDIA_ROOT", tmp_path)
    asset_ids = []
    for name in ("a.png", "b.png"):
        uploaded = client.post(
            "/org/question-bank/upload-image",
            files={"file": (name, PNG_BYTES, "image/png")},
            headers=headers,
        )
        asset_ids.append(uploaded.json()["asset_id"])
    monkeypatch.setattr(
        QuestionOCRService,
        "_extract_merged",
        lambda self, paths_and_types, policy: {
            "q_type": "single_choice",
            "stem": "Merged",
            "choices": None,
            "answer_key": "A",
        },
    )
    resp = client.post(
        "/org/question-bank/ocr",
        json={"mode": "multi_image_single_question", "asset_ids": asset_ids},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["mode"] == "single_question"
    assert body["question"]["stem"] == "Merged"
```

- [ ] **Step 2: Enable multi-image upload in workbench**

- Sub-mode **多图一题**: `<input multiple accept="image/*">`
- Upload files sequentially, preserve order, collect `asset_ids`
- Call `recognizeQuestions("multi_image_single_question", assetIds)`
- Map `single_question` → drafts list of length 1
- On create, set `source_image_asset_id` to `assetIds[0]`

- [ ] **Step 3: Frontend test**

Add test uploading two files, asserting OCR request uses both asset ids and one draft appears.

- [ ] **Step 4: Run full test suites**

Run:

```bash
/Users/bytedance/cursor/AITeacher/backend/.venv/bin/python -m pytest backend/tests/test_question_ocr.py backend/tests/test_question_bank_api.py -v
cd /Users/bytedance/cursor/AITeacher/frontend && npm test -- QuestionBankOcr.test.tsx
```

Expected: all PASS.

---

### Task 8: Final verification + spec status

**Files:**
- Modify: `docs/superpowers/specs/2026-08-20-question-bank-multi-image-ocr-design.md`

- [ ] **Step 1: Run regression**

```bash
/Users/bytedance/cursor/AITeacher/backend/.venv/bin/python -m pytest \
  backend/tests/test_question_ocr.py \
  backend/tests/test_question_bank_service.py \
  backend/tests/test_question_bank_api.py -v

cd /Users/bytedance/cursor/AITeacher/frontend
npm test -- QuestionBankOcr.test.tsx QuestionBank.test.tsx
```

Expected: all PASS.

- [ ] **Step 2: Mark spec implemented**

Change spec status to **已实现**.

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/question_bank.py backend/app/services/question_ocr.py \
  backend/app/routers/org_question_bank.py backend/tests/test_question_ocr.py \
  frontend/src/api/questionBank.ts \
  frontend/src/components/questionBank/QuestionBankOcrWorkbench.tsx \
  frontend/src/components/questionBank/QuestionBankPage.tsx \
  frontend/tests/QuestionBankOcr.test.tsx \
  docs/superpowers/specs/2026-08-20-question-bank-multi-image-ocr-design.md \
  docs/superpowers/plans/2026-08-20-question-bank-multi-image-ocr.md

git commit -m "$(cat <<'EOF'
feat(question-bank): add multi-image OCR workbench

Support single-image multi-question segmentation with raw-text fallback,
multi-image single-question merge, batch enrich/submit, and legacy OCR compat.
EOF
)"
```

---

## Spec coverage checklist

| Spec section | Task |
|--------------|------|
| §3 OCR 工作台 | 5, 7 |
| §3.2 一图多题流程 | 2, 3, 5 |
| §3.3 多图一题流程 | 6, 7 |
| §4 API mode + asset_ids | 1, 3, 4, 7 |
| §4.3 discriminated response | 1, 3 |
| §5 source_image_asset_id rules | 5, 7 |
| §6 工作台 UI | 5, 7 |
| §7 OCR prompts | 2, 6 |
| §8 兼容 legacy OCR | 3, 4 |
| §10 成功标准 | 8 |

## Spec → plan traceability

| Spec § | Task |
|--------|------|
| §3 产品形态 | 5, 7 |
| §4 API | 1–4, 7 |
| §5 数据模型 | 5, 7 |
| §6 前端工作台 | 5, 7 |
| §7 后端 OCR | 2, 6 |
| §8 兼容与分期 | Phase A/B tasks |
| §10 成功标准 | 8 |
