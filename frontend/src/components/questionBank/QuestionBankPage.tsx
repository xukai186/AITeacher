import { FormEvent, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createQuestion,
  CreateQuestion,
  enrichQuestion,
  Enrichment,
  listQuestions,
  QuestionBankItem,
  QuestionBankRole,
  reviewQuestion,
} from "@/api/questionBank";
import MathText from "@/components/MathText";
import KnowledgeNodeSelect from "./KnowledgeNodeSelect";
import QuestionBankEditForm from "./QuestionBankEditForm";
import QuestionBankOcrWorkbench from "./QuestionBankOcrWorkbench";

const SUBJECTS = [
  ["", "全部科目"],
  ["politics", "政治"],
  ["english", "英语"],
  ["math", "数学"],
] as const;

const STATUSES = [
  ["", "全部状态"],
  ["pending_review", "待审核"],
  ["active", "已启用"],
  ["rejected", "已驳回"],
  ["disabled", "已禁用"],
] as const;

const STATUS_LABELS: Record<string, string> = Object.fromEntries(STATUSES);
const SUBJECT_LABELS: Record<string, string> = Object.fromEntries(SUBJECTS);
const Q_TYPE_LABELS: Record<string, string> = {
  single_choice: "单选题",
  multi_choice: "多选题",
  fill_blank: "填空题",
  short_answer: "简答题",
};
const SOURCE_LABELS: Record<string, string> = {
  admin_manual: "管理员录入",
  staff_manual: "老师录入",
  ocr_import: "图片识别",
  ai_generated: "AI 生成",
};
const SCOPE_LABELS: Record<string, string> = {
  org: "本机构",
  global: "平台公共",
};
const OBJECTIVE_TYPES = new Set(["single_choice", "multi_choice"]);
const DELETABLE = new Set(["pending_review", "rejected", "disabled"]);

type Draft = {
  stem: string;
  qType: string;
  choicesText: string;
  answerKey: string;
};

const EMPTY_DRAFT: Draft = {
  stem: "",
  qType: "short_answer",
  choicesText: "",
  answerKey: "",
};

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

function formatChoices(
  choices: QuestionBankItem["choices"],
): Array<{ key: string; text: string }> {
  if (!choices?.length) return [];
  return choices
    .map((choice, index) => {
      const key = String(choice.key ?? "").trim() || String.fromCharCode(65 + index);
      const text = String(choice.text ?? "").trim();
      if (!text) return null;
      return { key, text };
    })
    .filter((choice): choice is { key: string; text: string } => choice != null);
}

function QuestionBankItemDetail({
  item,
  onClose,
  onEdit,
  canEdit,
  onDelete,
  canDelete,
}: {
  item: QuestionBankItem;
  onClose: () => void;
  onEdit?: () => void;
  canEdit?: boolean;
  onDelete?: () => void;
  canDelete?: boolean;
}) {
  const choices = formatChoices(item.choices);

  return (
    <div className="fixed inset-0 z-10 flex items-start justify-center overflow-auto bg-black/40 p-8">
      <div className="w-full max-w-2xl rounded bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-start justify-between gap-4">
          <h2 className="text-lg font-semibold">题目详情</h2>
          <div className="flex items-center gap-3">
            {canEdit && onEdit ? (
              <button type="button" onClick={onEdit} className="text-sm text-slate-900 underline">
                编辑
              </button>
            ) : null}
            {canDelete && onDelete ? (
              <button type="button" onClick={onDelete} className="text-sm text-red-700 underline">
                删除
              </button>
            ) : null}
            <button type="button" onClick={onClose} className="text-sm text-slate-600 underline">
              关闭
            </button>
          </div>
        </div>

        <dl className="space-y-4 text-sm">
          <div>
            <dt className="mb-1 text-slate-600">题干</dt>
            <dd className="rounded bg-slate-50 p-3">
              <MathText text={item.stem} />
            </dd>
          </div>

          {choices.length > 0 && (
            <div>
              <dt className="mb-1 text-slate-600">选项</dt>
              <dd className="space-y-2 rounded bg-slate-50 p-3">
                {choices.map((choice) => (
                  <div key={choice.key}>
                    <span className="font-medium">{choice.key}.</span>{" "}
                    <MathText text={choice.text} />
                  </div>
                ))}
              </dd>
            </div>
          )}

          {item.answer_key ? (
            <div>
              <dt className="mb-1 text-slate-600">答案</dt>
              <dd className="rounded bg-slate-50 p-3">
                <MathText text={item.answer_key} />
              </dd>
            </div>
          ) : null}

          {item.analysis_text ? (
            <div>
              <dt className="mb-1 text-slate-600">解析</dt>
              <dd className="rounded bg-slate-50 p-3">
                <MathText text={item.analysis_text} />
              </dd>
            </div>
          ) : null}

          <div className="grid grid-cols-2 gap-3 border-t pt-4">
            <div>
              <dt className="text-slate-600">题型</dt>
              <dd>{Q_TYPE_LABELS[item.q_type] ?? item.q_type}</dd>
            </div>
            <div>
              <dt className="text-slate-600">科目</dt>
              <dd>{SUBJECT_LABELS[item.subject_code] ?? item.subject_code}</dd>
            </div>
            <div>
              <dt className="text-slate-600">难度</dt>
              <dd>{item.difficulty ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-slate-600">状态</dt>
              <dd>{STATUS_LABELS[item.status] ?? item.status}</dd>
            </div>
            <div>
              <dt className="text-slate-600">归属</dt>
              <dd>{SCOPE_LABELS[item.scope] ?? item.scope}</dd>
            </div>
            <div>
              <dt className="text-slate-600">来源</dt>
              <dd>{SOURCE_LABELS[item.source_type] ?? item.source_type}</dd>
            </div>
            {item.knowledge_node_id ? (
              <div className="col-span-2">
                <dt className="text-slate-600">知识点</dt>
                <dd>{item.knowledge_node_name ?? "（未标注知识点）"}</dd>
              </div>
            ) : null}
            <div className="col-span-2">
              <dt className="text-slate-600">入库时间</dt>
              <dd>{new Date(item.created_at).toLocaleString()}</dd>
            </div>
          </div>
        </dl>
      </div>
    </div>
  );
}

export default function QuestionBankPage({ role }: { role: QuestionBankRole }) {
  const queryClient = useQueryClient();
  const [subject, setSubject] = useState("");
  const [status, setStatus] = useState("");
  const [pendingOnly, setPendingOnly] = useState(false);
  const [offset, setOffset] = useState(0);
  const limit = 20;
  const [allItems, setAllItems] = useState<QuestionBankItem[]>([]);
  const [hasMore, setHasMore] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [createMode, setCreateMode] = useState<"manual" | "ocr">("manual");
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [confirmation, setConfirmation] = useState<Enrichment | null>(null);
  const [scope, setScope] = useState<"org" | "global">("org");
  const [detailItem, setDetailItem] = useState<QuestionBankItem | null>(null);
  const [editItem, setEditItem] = useState<QuestionBankItem | null>(null);

  const filters = { subject_code: subject, status, pending: pendingOnly, limit, offset };
  const questions = useQuery({
    queryKey: ["question-bank", filters],
    queryFn: () => listQuestions(filters),
  });

  useEffect(() => {
    setOffset(0);
    setAllItems([]);
    setHasMore(true);
  }, [subject, status, pendingOnly]);

  useEffect(() => {
    if (!questions.data) return;
    setAllItems((prev) => {
      const existing = new Set(prev.map((item) => item.id));
      const next = [...prev];
      for (const item of questions.data) {
        if (!existing.has(item.id)) next.push(item);
      }
      return next;
    });
    setHasMore(questions.data.length === limit);
  }, [questions.data, limit]);

  const resetList = () => {
    setOffset(0);
    setAllItems([]);
    setHasMore(true);
  };

  const enrichMutation = useMutation({
    mutationFn: enrichQuestion,
    onSuccess: (suggestion) => {
      setConfirmation(suggestion);
      if (suggestion.q_type) {
        setDraft((current) => ({ ...current, qType: suggestion.q_type! }));
      }
    },
  });
  const createMutation = useMutation({
    mutationFn: createQuestion,
    onSuccess: () => {
      setShowCreate(false);
      setDraft(EMPTY_DRAFT);
      setConfirmation(null);
      setScope("org");
      setCreateMode("manual");
      resetList();
      queryClient.invalidateQueries({ queryKey: ["question-bank"] });
    },
  });
  const reviewMutation = useMutation({
    mutationFn: ({
      id,
      action,
    }: {
      id: string;
      action: "approve" | "reject" | "disable" | "delete";
    }) => reviewQuestion(id, action),
    onSuccess: () => {
      resetList();
      queryClient.invalidateQueries({ queryKey: ["question-bank"] });
    },
  });

  const requestDelete = (id: string) => {
    if (!window.confirm("删除后列表不再显示，确认删除？")) return false;
    reviewMutation.mutate({ id, action: "delete" });
    return true;
  };

  const questionDraft = () => ({
    stem: draft.stem.trim(),
    q_type: draft.qType,
    choices: OBJECTIVE_TYPES.has(draft.qType)
      ? parseChoices(draft.choicesText)
      : undefined,
    answer_key: draft.answerKey.trim() || undefined,
  });

  const onEnrich = (event: FormEvent) => {
    event.preventDefault();
    enrichMutation.mutate(questionDraft());
  };

  const onCreate = (event: FormEvent) => {
    event.preventDefault();
    if (!confirmation) return;
    const body: CreateQuestion = {
      ...questionDraft(),
      ...confirmation,
      q_type: confirmation.q_type ?? draft.qType,
      scope,
      source_type:
        role === "org_admin" ? "admin_manual" : "staff_manual",
    };
    createMutation.mutate(body);
  };

  const closeCreate = () => {
    setShowCreate(false);
    setCreateMode("manual");
    setDraft(EMPTY_DRAFT);
    setConfirmation(null);
    enrichMutation.reset();
    createMutation.reset();
  };

  const selectCreateMode = (mode: "manual" | "ocr") => {
    setCreateMode(mode);
    setDraft(EMPTY_DRAFT);
    setConfirmation(null);
    enrichMutation.reset();
  };

  const draftChoices = OBJECTIVE_TYPES.has(draft.qType)
    ? parseChoices(draft.choicesText)
    : [];

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">题库</h1>
        <button
          type="button"
          onClick={() => setShowCreate(true)}
          className="rounded bg-slate-900 px-4 py-2 text-white"
        >
          新建题目
        </button>
      </div>

      <section className="flex flex-wrap items-end gap-4 rounded bg-white p-4 shadow">
        <label className="space-y-1 text-sm">
          <span className="block text-slate-600">筛选科目</span>
          <select
            value={subject}
            onChange={(event) => setSubject(event.target.value)}
            className="rounded border px-3 py-2"
          >
            {SUBJECTS.map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
        <label className="space-y-1 text-sm">
          <span className="block text-slate-600">状态</span>
          <select
            value={status}
            disabled={pendingOnly}
            onChange={(event) => setStatus(event.target.value)}
            className="rounded border px-3 py-2 disabled:opacity-50"
          >
            {STATUSES.map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 pb-2 text-sm">
          <input
            type="checkbox"
            checked={pendingOnly}
            onChange={(event) => setPendingOnly(event.target.checked)}
          />
          仅看待审核
        </label>
      </section>

      <section className="overflow-hidden rounded bg-white shadow">
        {questions.isLoading && allItems.length === 0 && (
          <p className="p-4 text-slate-500">加载中…</p>
        )}
        {questions.error && (
          <p role="alert" className="p-4 text-red-600">
            {(questions.error as Error).message}
          </p>
        )}
        {!questions.isLoading && !questions.error && allItems.length === 0 && (
          <p className="p-6 text-center text-slate-500">暂无题目</p>
        )}
        {!!allItems.length && (
          <table className="w-full text-sm">
            <thead className="bg-slate-100 text-left">
              <tr>
                <th className="px-4 py-3">题干</th>
                <th className="px-4 py-3">科目</th>
                <th className="px-4 py-3">难度</th>
                <th className="px-4 py-3">状态</th>
                <th className="px-4 py-3">操作</th>
              </tr>
            </thead>
            <tbody>
              {allItems.map((item) => {
                const canMutate = role === "org_admin" || item.scope === "org";
                return (
                  <tr key={item.id} className="border-t align-top">
                    <td className="max-w-xl px-4 py-3">
                      <MathText text={item.stem} />
                    </td>
                    <td className="px-4 py-3">
                      {SUBJECT_LABELS[item.subject_code] ?? item.subject_code}
                    </td>
                    <td className="px-4 py-3">{item.difficulty ?? "—"}</td>
                    <td className="px-4 py-3">
                      {STATUS_LABELS[item.status] ?? item.status}
                    </td>
                    <td className="space-x-2 whitespace-nowrap px-4 py-3">
                      <button
                        type="button"
                        onClick={() => setDetailItem(item)}
                        className="text-slate-700 underline"
                      >
                        查看
                      </button>
                      {item.status !== "active" && canMutate && (
                        <button
                          type="button"
                          onClick={() => {
                            setDetailItem(null);
                            setEditItem(item);
                          }}
                          className="text-slate-700 underline"
                        >
                          编辑
                        </button>
                      )}
                      {DELETABLE.has(item.status) && canMutate && (
                        <button
                          type="button"
                          onClick={() => requestDelete(item.id)}
                          className="text-red-700 underline"
                        >
                          删除
                        </button>
                      )}
                      {item.status === "pending_review" && canMutate && (
                        <>
                          <button
                            onClick={() =>
                              reviewMutation.mutate({ id: item.id, action: "approve" })
                            }
                            className="text-green-700 underline"
                          >
                            通过
                          </button>
                          <button
                            onClick={() =>
                              reviewMutation.mutate({ id: item.id, action: "reject" })
                            }
                            className="text-red-700 underline"
                          >
                            驳回
                          </button>
                        </>
                      )}
                      {item.status === "active" && canMutate && (
                        <button
                          onClick={() =>
                            reviewMutation.mutate({ id: item.id, action: "disable" })
                          }
                          className="text-red-700 underline"
                        >
                          禁用
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
        {!!allItems.length && (
          <div className="flex justify-center border-t p-4">
            {hasMore ? (
              <button
                type="button"
                className="rounded border bg-white px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-50"
                onClick={() => setOffset((current) => current + limit)}
                disabled={questions.isLoading}
              >
                {questions.isLoading ? "加载中…" : "加载更多"}
              </button>
            ) : (
              <span className="text-sm text-slate-500">没有更多了</span>
            )}
          </div>
        )}
        {reviewMutation.error && (
          <p role="alert" className="border-t p-3 text-sm text-red-600">
            {(reviewMutation.error as Error).message}
          </p>
        )}
      </section>

      {detailItem ? (
        <QuestionBankItemDetail
          item={detailItem}
          onClose={() => setDetailItem(null)}
          canEdit={
            detailItem.status !== "active" &&
            (role === "org_admin" || detailItem.scope === "org")
          }
          canDelete={
            DELETABLE.has(detailItem.status) &&
            (role === "org_admin" || detailItem.scope === "org")
          }
          onEdit={() => {
            setEditItem(detailItem);
            setDetailItem(null);
          }}
          onDelete={() => {
            if (requestDelete(detailItem.id)) setDetailItem(null);
          }}
        />
      ) : null}

      {editItem ? (
        <QuestionBankEditForm
          item={editItem}
          onClose={() => setEditItem(null)}
          onSaved={() => {
            setEditItem(null);
            resetList();
            queryClient.invalidateQueries({ queryKey: ["question-bank"] });
          }}
        />
      ) : null}

      {showCreate && (
        <div className="fixed inset-0 z-10 flex items-start justify-center overflow-auto bg-black/40 p-8">
          <div
            className={`w-full rounded bg-white p-6 shadow-xl ${
              createMode === "ocr" ? "max-w-4xl" : "max-w-2xl"
            }`}
          >
            {createMode === "ocr" ? (
              <div className="space-y-4">
                <h2 className="text-lg font-semibold">新建题目</h2>
                <div className="flex gap-2 border-b pb-3">
                  <button
                    type="button"
                    onClick={() => selectCreateMode("manual")}
                    className="rounded bg-slate-100 px-3 py-2"
                  >
                    手工添加
                  </button>
                  <button
                    type="button"
                    onClick={() => selectCreateMode("ocr")}
                    className="rounded bg-slate-900 px-3 py-2 text-white"
                  >
                    图片识别添加
                  </button>
                </div>
                <QuestionBankOcrWorkbench
                  role={role}
                  scope={scope}
                  onSubmitted={() => {
                    closeCreate();
                    resetList();
                    queryClient.invalidateQueries({
                      queryKey: ["question-bank"],
                    });
                  }}
                  onCancel={closeCreate}
                />
              </div>
            ) : !confirmation ? (
              <form onSubmit={onEnrich} className="space-y-4">
                <h2 className="text-lg font-semibold">新建题目</h2>
                <div className="flex gap-2 border-b pb-3">
                  <button
                    type="button"
                    onClick={() => selectCreateMode("manual")}
                    className="rounded bg-slate-900 px-3 py-2 text-white"
                  >
                    手工添加
                  </button>
                  <button
                    type="button"
                    onClick={() => selectCreateMode("ocr")}
                    className="rounded bg-slate-100 px-3 py-2"
                  >
                    图片识别添加
                  </button>
                </div>
                <label className="block space-y-1">
                  <span>题型</span>
                  <select
                    value={draft.qType}
                    onChange={(event) =>
                      setDraft({ ...draft, qType: event.target.value })
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
                    onChange={(event) =>
                      setDraft({ ...draft, stem: event.target.value })
                    }
                    required
                    rows={4}
                    className="w-full rounded border px-3 py-2"
                  />
                </label>
                {draft.stem.trim() ? (
                  <div className="rounded border border-dashed bg-slate-50 p-3 text-sm">
                    <div className="mb-1 text-xs text-slate-500">预览</div>
                    <MathText text={draft.stem} />
                  </div>
                ) : null}
                {OBJECTIVE_TYPES.has(draft.qType) && (
                  <>
                    <label className="block space-y-1">
                      <span>选项（每行一个）</span>
                      <textarea
                        value={draft.choicesText}
                        onChange={(event) =>
                          setDraft({ ...draft, choicesText: event.target.value })
                        }
                        placeholder={"A. 选项一\nB. 选项二"}
                        required
                        rows={5}
                        className="w-full rounded border px-3 py-2"
                      />
                    </label>
                    {draftChoices.length > 0 ? (
                      <div className="rounded border border-dashed bg-slate-50 p-3 text-sm space-y-2">
                        <div className="text-xs text-slate-500">选项预览</div>
                        {draftChoices.map((choice) => (
                          <div key={choice.key}>
                            <span className="font-medium">{choice.key}.</span>{" "}
                            <MathText text={choice.text} />
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </>
                )}
                <label className="block space-y-1">
                  <span>{OBJECTIVE_TYPES.has(draft.qType) ? "答案" : "参考答案"}</span>
                  <input
                    value={draft.answerKey}
                    onChange={(event) =>
                      setDraft({ ...draft, answerKey: event.target.value })
                    }
                    required
                    className="w-full rounded border px-3 py-2"
                  />
                </label>
                {draft.answerKey.trim() ? (
                  <div className="rounded border border-dashed bg-slate-50 p-3 text-sm">
                    <div className="mb-1 text-xs text-slate-500">答案预览</div>
                    <MathText text={draft.answerKey} />
                  </div>
                ) : null}
                <div className="flex justify-end gap-3">
                  <button type="button" onClick={closeCreate} className="px-4 py-2">
                    取消
                  </button>
                  <button
                    type="submit"
                    disabled={enrichMutation.isPending}
                    className="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-50"
                  >
                    {enrichMutation.isPending ? "补全中…" : "智能补全"}
                  </button>
                </div>
                {enrichMutation.error && (
                  <p role="alert" className="text-sm text-red-600">
                    {(enrichMutation.error as Error).message}
                  </p>
                )}
              </form>
            ) : (
              <form onSubmit={onCreate} className="space-y-4">
                <h2 className="text-lg font-semibold">确认题目信息</h2>
                <div className="space-y-3 rounded bg-slate-50 p-3 text-sm">
                  <div>
                    <div className="mb-1 text-xs text-slate-500">题干</div>
                    <MathText text={draft.stem} />
                  </div>
                  {draftChoices.length > 0 && (
                      <div className="space-y-2 border-t pt-3">
                        <div className="text-xs text-slate-500">选项</div>
                        {draftChoices.map((choice) => (
                          <div key={choice.key}>
                            <span className="font-medium">{choice.key}.</span>{" "}
                            <MathText text={choice.text} />
                          </div>
                        ))}
                      </div>
                    )}
                  {draft.answerKey.trim() ? (
                    <div className="border-t pt-3">
                      <div className="mb-1 text-xs text-slate-500">答案</div>
                      <MathText text={draft.answerKey} />
                    </div>
                  ) : null}
                </div>
                {role === "org_admin" && (
                  <label className="block space-y-1">
                    <span>归属</span>
                    <select
                      value={scope}
                      onChange={(event) =>
                        setScope(event.target.value as "org" | "global")
                      }
                      className="w-full rounded border px-3 py-2"
                    >
                      <option value="org">本机构</option>
                      <option value="global">平台公共</option>
                    </select>
                  </label>
                )}
                <label className="block space-y-1">
                  <span>科目</span>
                  <select
                    value={confirmation.subject_code}
                    onChange={(event) =>
                      setConfirmation({
                        ...confirmation,
                        subject_code: event.target.value,
                        knowledge_node_id: null,
                        knowledge_node_name: null,
                      })
                    }
                    className="w-full rounded border px-3 py-2"
                    aria-label="科目"
                  >
                    {SUBJECTS.slice(1).map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                </label>
                <label className="block space-y-1">
                  <span>知识点</span>
                  <KnowledgeNodeSelect
                    subjectCode={confirmation.subject_code}
                    value={confirmation.knowledge_node_id}
                    onChange={(id) =>
                      setConfirmation({
                        ...confirmation,
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
                    value={confirmation.difficulty}
                    onChange={(event) =>
                      setConfirmation({
                        ...confirmation,
                        difficulty: Number(event.target.value),
                      })
                    }
                    required
                    className="w-full rounded border px-3 py-2"
                  />
                </label>
                <label className="block space-y-1">
                  <span>解析</span>
                  <textarea
                    value={confirmation.analysis_text ?? ""}
                    onChange={(event) =>
                      setConfirmation({
                        ...confirmation,
                        analysis_text: event.target.value || null,
                      })
                    }
                    rows={4}
                    className="w-full rounded border px-3 py-2"
                  />
                </label>
                <div className="flex justify-end gap-3">
                  <button
                    type="button"
                    onClick={() => setConfirmation(null)}
                    className="px-4 py-2"
                  >
                    返回修改
                  </button>
                  <button
                    type="submit"
                    disabled={createMutation.isPending}
                    className="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-50"
                  >
                    {createMutation.isPending ? "提交中…" : "确认入库"}
                  </button>
                </div>
                {createMutation.error && (
                  <p role="alert" className="text-sm text-red-600">
                    {(createMutation.error as Error).message}
                  </p>
                )}
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
