import { useEffect, useRef, useState } from "react";
import {
  createQuestion,
  enrichQuestion,
  Enrichment,
  QuestionBankRole,
  recognizeQuestions,
  uploadQuestionImage,
} from "@/api/questionBank";
import KnowledgeNodeSelect from "./KnowledgeNodeSelect";

type OcrWorkbenchProps = {
  role: QuestionBankRole;
  scope: "org" | "global";
  onSubmitted: () => void;
  onCancel: () => void;
  onSubmittingChange?: (submitting: boolean) => void;
};

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

const OBJECTIVE_TYPES = new Set(["single_choice", "multi_choice"]);

const SUBJECT_OPTIONS = [
  ["politics", "政治"],
  ["english", "英语"],
  ["math", "数学"],
] as const;

function parseChoices(value: string) {
  return value
    .split("\n")
    .map((line, index) => {
      const match = line.trim().match(/^([A-Za-z])[\s.、:：]+(.+)$/);
      return {
        key: match?.[1]?.toUpperCase() ?? String.fromCharCode(65 + index),
        text: match?.[2]?.trim() ?? line.trim(),
      };
    })
    .filter((choice) => choice.text);
}

function errorMessage(reason: unknown) {
  return reason instanceof Error ? reason.message : "操作失败";
}

function emptyDraft(localId: string): OcrDraftItem {
  return {
    localId,
    stem: "",
    qType: "short_answer",
    choicesText: "",
    answerKey: "",
    enrichment: null,
  };
}

function isEnrichmentReady(enrichment?: Enrichment | null) {
  return Boolean(
    enrichment?.subject_code &&
      typeof enrichment.difficulty === "number" &&
      enrichment.difficulty >= 1 &&
      enrichment.difficulty <= 5,
  );
}

function defaultEnrichment(partial?: Partial<Enrichment>): Enrichment {
  return {
    subject_code: "",
    knowledge_node_id: null,
    // 0 = unset; isEnrichmentReady requires 1–5
    difficulty: 0,
    analysis_text: null,
    q_type: null,
    ...partial,
  };
}

export default function QuestionBankOcrWorkbench({
  role: _role,
  scope,
  onSubmitted,
  onCancel,
  onSubmittingChange,
}: OcrWorkbenchProps) {
  const nextDraftId = useRef(0);
  const recognitionGeneration = useRef(0);
  const submissionGeneration = useRef(0);
  const mounted = useRef(true);
  const onSubmittingChangeRef = useRef(onSubmittingChange);
  onSubmittingChangeRef.current = onSubmittingChange;
  const [ocrMode, setOcrMode] = useState<
    "single_image_multi_question" | "multi_image_single_question"
  >("single_image_multi_question");
  const [files, setFiles] = useState<File[]>([]);
  const [sourceAssetId, setSourceAssetId] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<OcrDraftItem[]>([]);
  const [rawText, setRawText] = useState<string | null>(null);
  const [recognizing, setRecognizing] = useState(false);
  const [enriching, setEnriching] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [recognizeError, setRecognizeError] = useState<string | null>(null);
  const draftsRef = useRef(drafts);
  draftsRef.current = drafts;

  useEffect(
    () => () => {
      mounted.current = false;
      submissionGeneration.current += 1;
      onSubmittingChangeRef.current?.(false);
    },
    [],
  );

  const replaceDraft = (
    localId: string,
    update: Partial<OcrDraftItem>,
  ) => {
    setDrafts((current) =>
      current.map((draft) =>
        draft.localId === localId
          ? {
              ...draft,
              ...update,
              enrichError: null,
              submitError: null,
            }
          : draft,
      ),
    );
  };

  const patchEnrichment = (
    localId: string,
    patch: Partial<Enrichment>,
  ) => {
    setDrafts((current) =>
      current.map((draft) => {
        if (draft.localId !== localId) return draft;
        return {
          ...draft,
          enrichment: {
            ...(draft.enrichment ?? defaultEnrichment()),
            ...patch,
          },
          enrichError: null,
          submitError: null,
        };
      }),
    );
  };

  const recognize = async () => {
    if (!files.length) return;
    if (
      ocrMode === "multi_image_single_question" &&
      files.length < 2
    ) {
      setRecognizeError("多图一题至少需要两张图片");
      return;
    }
    const generation = ++recognitionGeneration.current;
    setRecognizing(true);
    setRecognizeError(null);
    setSourceAssetId(null);
    setDrafts([]);
    setRawText(null);
    try {
      const assetIds: string[] = [];
      for (const file of files) {
        const uploaded = await uploadQuestionImage(file);
        if (generation !== recognitionGeneration.current) return;
        assetIds.push(uploaded.asset_id);
      }
      const result = await recognizeQuestions(ocrMode, assetIds);
      if (generation !== recognitionGeneration.current) return;
      if (result.mode === "raw_text_fallback") {
        if (ocrMode !== "single_image_multi_question") {
          throw new Error("识别结果模式异常，请重试");
        }
        setSourceAssetId(assetIds[0]);
        setRawText(result.raw_text);
        return;
      }
      if (result.mode === "single_question") {
        if (ocrMode !== "multi_image_single_question") {
          throw new Error("识别结果模式异常，请重试");
        }
        const question = result.question;
        setSourceAssetId(assetIds[0]);
        setDrafts([
          {
            localId: "ocr-0",
            stem: question.stem,
            qType: question.q_type,
            choicesText:
              question.choices
                ?.map((choice) => `${choice.key}. ${choice.text}`)
                .join("\n") ?? "",
            answerKey: question.answer_key ?? "",
            enrichment: null,
          },
        ]);
        return;
      }
      if (
        result.mode !== "segmented" ||
        ocrMode !== "single_image_multi_question"
      ) {
        throw new Error("识别结果模式异常，请重试");
      }
      setSourceAssetId(assetIds[0]);
      setDrafts(
        result.questions.map((question, index) => ({
          localId: `ocr-${index}`,
          stem: question.stem,
          qType: question.q_type,
          choicesText:
            question.choices
              ?.map((choice) => `${choice.key}. ${choice.text}`)
              .join("\n") ?? "",
          answerKey: question.answer_key ?? "",
          enrichment: null,
        })),
      );
    } catch (error) {
      if (generation === recognitionGeneration.current) {
        setRecognizeError(errorMessage(error));
      }
    } finally {
      if (generation === recognitionGeneration.current) {
        setRecognizing(false);
      }
    }
  };

  const runEnrich = async (targets: OcrDraftItem[]) => {
    if (!targets.length) return;
    setEnriching(true);
    setDrafts((current) =>
      current.map((draft) =>
        targets.some((target) => target.localId === draft.localId)
          ? { ...draft, enrichError: null }
          : draft,
      ),
    );
    const results = await Promise.allSettled(
      targets.map((draft) =>
        enrichQuestion({
          stem: draft.stem.trim(),
          q_type: draft.qType,
          choices: OBJECTIVE_TYPES.has(draft.qType)
            ? parseChoices(draft.choicesText)
            : undefined,
          answer_key: draft.answerKey.trim() || undefined,
        }),
      ),
    );
    const resultById = new Map(
      targets.map((draft, index) => [draft.localId, results[index]]),
    );
    setDrafts((current) =>
      current.map((draft) => {
        const result = resultById.get(draft.localId);
        if (!result) return draft;
        if (result.status === "rejected") {
          return {
            ...draft,
            enrichError: errorMessage(result.reason),
          };
        }
        return {
          ...draft,
          qType: result.value.q_type ?? draft.qType,
          enrichment: result.value,
          enrichError: null,
        };
      }),
    );
    setEnriching(false);
  };

  const enrichAll = async () => {
    await runEnrich(drafts.filter((draft) => !draft.submitted));
  };

  const enrichOne = async (localId: string) => {
    const draft = drafts.find((item) => item.localId === localId);
    if (!draft || draft.submitted) return;
    await runEnrich([draft]);
  };

  const submitAll = async () => {
    if (!sourceAssetId) return;
    const targets = drafts.filter(
      (draft) =>
        !draft.submitted &&
        draft.stem.trim() &&
        isEnrichmentReady(draft.enrichment),
    );
    if (!targets.length) return;
    const generation = ++submissionGeneration.current;
    setSubmitting(true);
    onSubmittingChangeRef.current?.(true);
    const submittedIds = new Set<string>();
    const submitErrors = new Map<string, string>();
    for (const draft of targets) {
      try {
        const enrichment = draft.enrichment!;
        await createQuestion({
          stem: draft.stem.trim(),
          choices: OBJECTIVE_TYPES.has(
            enrichment.q_type ?? draft.qType,
          )
            ? parseChoices(draft.choicesText)
            : undefined,
          answer_key: draft.answerKey.trim() || undefined,
          ...enrichment,
          q_type: enrichment.q_type ?? draft.qType,
          scope,
          source_type: "ocr_import",
          source_image_asset_id: sourceAssetId,
        });
        if (
          !mounted.current ||
          generation !== submissionGeneration.current
        ) {
          return;
        }
        submittedIds.add(draft.localId);
      } catch (error) {
        if (
          !mounted.current ||
          generation !== submissionGeneration.current
        ) {
          return;
        }
        submitErrors.set(draft.localId, errorMessage(error));
      }
    }
    if (!mounted.current || generation !== submissionGeneration.current) {
      return;
    }
    setDrafts((current) =>
      current.map((draft) => ({
        ...draft,
        submitted: draft.submitted || submittedIds.has(draft.localId),
        submitError: submitErrors.get(draft.localId) ?? null,
      })),
    );
    setSubmitting(false);
    onSubmittingChangeRef.current?.(false);
    const allSnapshotDraftsSucceeded = targets.every((draft) =>
      submittedIds.has(draft.localId),
    );
    const currentDraftsAreComplete =
      draftsRef.current.length === drafts.length &&
      draftsRef.current.every(
        (draft) => draft.submitted || submittedIds.has(draft.localId),
      );
    if (
      mounted.current &&
      generation === submissionGeneration.current &&
      allSnapshotDraftsSucceeded &&
      currentDraftsAreComplete
    ) {
      onSubmitted();
    }
  };

  const pendingDrafts = drafts.filter((draft) => !draft.submitted);
  const canSubmit =
    Boolean(sourceAssetId) &&
    pendingDrafts.length > 0 &&
    pendingDrafts.every(
      (draft) => draft.stem.trim() && isEnrichmentReady(draft.enrichment),
    );
  const operationLocked = recognizing || enriching || submitting;

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <button
          type="button"
          disabled={operationLocked}
          onClick={() => {
            recognitionGeneration.current += 1;
            setRecognizing(false);
            setOcrMode("single_image_multi_question");
            setFiles([]);
            setSourceAssetId(null);
            setDrafts([]);
            setRawText(null);
            setRecognizeError(null);
          }}
          className={
            ocrMode === "single_image_multi_question"
              ? "rounded bg-slate-900 px-3 py-2 text-white"
              : "rounded bg-slate-100 px-3 py-2 text-slate-700"
          }
        >
          一图多题
        </button>
        <button
          type="button"
          disabled={operationLocked}
          onClick={() => {
            recognitionGeneration.current += 1;
            setRecognizing(false);
            setOcrMode("multi_image_single_question");
            setFiles([]);
            setSourceAssetId(null);
            setDrafts([]);
            setRawText(null);
            setRecognizeError(null);
          }}
          className={
            ocrMode === "multi_image_single_question"
              ? "rounded bg-slate-900 px-3 py-2 text-white"
              : "rounded bg-slate-100 px-3 py-2 text-slate-700"
          }
        >
          多图一题
        </button>
      </div>

      <div className="space-y-3 rounded border border-dashed p-4">
        <label className="block space-y-1">
          <span>题目图片</span>
          <input
            type="file"
            accept="image/*"
            multiple={ocrMode === "multi_image_single_question"}
            disabled={operationLocked}
            onChange={(event) => {
              recognitionGeneration.current += 1;
              setRecognizing(false);
              const selected = event.target.files
                ? Array.from(event.target.files)
                : [];
              setFiles(selected);
              setSourceAssetId(null);
              setDrafts([]);
              setRawText(null);
              setRecognizeError(null);
            }}
            className="block w-full text-sm"
          />
        </label>
        <button
          type="button"
          disabled={!files.length || operationLocked}
          onClick={recognize}
          className="rounded bg-slate-700 px-4 py-2 text-white disabled:opacity-50"
        >
          {recognizing ? "识别中…" : "开始识别"}
        </button>
        {recognizeError ? (
          <p role="alert" className="text-sm text-red-600">
            {recognizeError}
          </p>
        ) : null}
      </div>

      {rawText !== null ? (
        <section className="space-y-3 rounded border p-4">
          <label className="block space-y-1">
            <span>OCR 原始文本</span>
            <textarea
              readOnly
              value={rawText}
              rows={6}
              className="w-full rounded border bg-slate-50 px-3 py-2"
            />
          </label>
          <button
            type="button"
            disabled={enriching || submitting}
            onClick={() =>
              setDrafts((current) => [
                ...current,
                emptyDraft(`manual-${nextDraftId.current++}`),
              ])
            }
            className="rounded border px-3 py-2"
          >
            新增题目
          </button>
        </section>
      ) : null}

      {drafts.map((draft, index) => (
        <section
          key={draft.localId}
          className="space-y-3 rounded border p-4"
        >
          <div className="flex items-center justify-between">
            <h3 className="font-medium">题目 {index + 1}</h3>
            <button
              type="button"
              disabled={draft.submitted || enriching || submitting}
              onClick={() =>
                setDrafts((current) =>
                  current.filter((item) => item.localId !== draft.localId),
                )
              }
              className="text-sm text-red-700 underline disabled:opacity-50"
            >
              删除
            </button>
          </div>
          <label className="block space-y-1">
            <span>题型</span>
            <select
              value={draft.qType}
              disabled={draft.submitted || enriching || submitting}
              onChange={(event) =>
                replaceDraft(draft.localId, { qType: event.target.value })
              }
              className="w-full rounded border px-3 py-2"
            >
              <option value="short_answer">简答题</option>
              <option value="fill_blank">填空题</option>
              <option value="single_choice">单选题</option>
              <option value="multi_choice">多选题</option>
            </select>
          </label>
          <label className="block space-y-1">
            <span>题干</span>
            <textarea
              value={draft.stem}
              disabled={draft.submitted || enriching || submitting}
              onChange={(event) =>
                replaceDraft(draft.localId, { stem: event.target.value })
              }
              rows={3}
              className="w-full rounded border px-3 py-2"
            />
          </label>
          {OBJECTIVE_TYPES.has(draft.qType) ? (
            <label className="block space-y-1">
              <span>选项（每行一个）</span>
              <textarea
                value={draft.choicesText}
                disabled={draft.submitted || enriching || submitting}
                onChange={(event) =>
                  replaceDraft(draft.localId, {
                    choicesText: event.target.value,
                  })
                }
                rows={4}
                className="w-full rounded border px-3 py-2"
              />
            </label>
          ) : null}
          <label className="block space-y-1">
            <span>
              {OBJECTIVE_TYPES.has(draft.qType) ? "答案" : "参考答案"}
            </span>
            <input
              value={draft.answerKey}
              disabled={draft.submitted || enriching || submitting}
              onChange={(event) =>
                replaceDraft(draft.localId, {
                  answerKey: event.target.value,
                })
              }
              className="w-full rounded border px-3 py-2"
            />
          </label>
          <label className="block space-y-1">
            <span>科目</span>
            <select
              value={draft.enrichment?.subject_code ?? ""}
              disabled={draft.submitted || enriching || submitting}
              onChange={(event) =>
                patchEnrichment(draft.localId, {
                  subject_code: event.target.value,
                  knowledge_node_id: null,
                  knowledge_node_name: null,
                })
              }
              className="w-full rounded border px-3 py-2"
              aria-label="科目"
            >
              <option value="">请选择科目</option>
              {SUBJECT_OPTIONS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="block space-y-1">
            <span>知识点</span>
            <KnowledgeNodeSelect
              subjectCode={draft.enrichment?.subject_code ?? ""}
              value={draft.enrichment?.knowledge_node_id ?? null}
              disabled={draft.submitted || enriching || submitting}
              onChange={(id) =>
                patchEnrichment(draft.localId, {
                  knowledge_node_id: id,
                  knowledge_node_name: null,
                })
              }
            />
          </label>
          <label className="block space-y-1">
            <span>难度（1-5）</span>
            <input
              type="number"
              min={1}
              max={5}
              value={
                draft.enrichment &&
                draft.enrichment.difficulty >= 1 &&
                draft.enrichment.difficulty <= 5
                  ? draft.enrichment.difficulty
                  : ""
              }
              disabled={draft.submitted || enriching || submitting}
              onChange={(event) =>
                patchEnrichment(draft.localId, {
                  difficulty: Number(event.target.value),
                })
              }
              className="w-full rounded border px-3 py-2"
              aria-label="难度"
            />
          </label>
          <label className="block space-y-1">
            <span>解析</span>
            <textarea
              value={draft.enrichment?.analysis_text ?? ""}
              disabled={draft.submitted || enriching || submitting}
              onChange={(event) =>
                patchEnrichment(draft.localId, {
                  analysis_text: event.target.value || null,
                })
              }
              rows={3}
              className="w-full rounded border px-3 py-2"
              aria-label="解析"
            />
          </label>
          {draft.enrichError ? (
            <div className="space-y-2">
              <p role="alert" className="text-sm text-red-600">
                智能补全失败：{draft.enrichError}
              </p>
              <button
                type="button"
                disabled={enriching || submitting || draft.submitted}
                onClick={() => enrichOne(draft.localId)}
                className="rounded border px-3 py-1.5 text-sm disabled:opacity-50"
              >
                重试补全
              </button>
            </div>
          ) : null}
          {draft.submitError ? (
            <p role="alert" className="text-sm text-red-600">
              提交失败：{draft.submitError}
            </p>
          ) : null}
          {draft.submitted ? (
            <p className="text-sm text-green-700">已提交</p>
          ) : null}
        </section>
      ))}

      <div className="flex justify-end gap-3">
        <button
          type="button"
          disabled={submitting}
          onClick={onCancel}
          className="px-4 py-2 disabled:opacity-50"
        >
          取消
        </button>
        <button
          type="button"
          disabled={!pendingDrafts.length || enriching || submitting}
          onClick={enrichAll}
          className="rounded border px-4 py-2 disabled:opacity-50"
        >
          {enriching ? "补全中…" : "批量智能补全"}
        </button>
        <button
          type="button"
          disabled={!canSubmit || submitting || enriching}
          onClick={submitAll}
          className="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-50"
        >
          {submitting ? "提交中…" : "批量提交"}
        </button>
      </div>
    </div>
  );
}
