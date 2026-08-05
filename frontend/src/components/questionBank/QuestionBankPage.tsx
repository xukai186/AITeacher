import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createQuestion,
  CreateQuestion,
  enrichQuestion,
  Enrichment,
  listQuestions,
  QuestionBankRole,
  reviewQuestion,
} from "@/api/questionBank";

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
const OBJECTIVE_TYPES = new Set(["single_choice", "multiple_choice"]);

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
        label: match?.[1]?.toUpperCase() ?? String.fromCharCode(65 + index),
        text: match?.[2]?.trim() ?? line.trim(),
      };
    })
    .filter((choice) => choice.text);
}

export default function QuestionBankPage({ role }: { role: QuestionBankRole }) {
  const queryClient = useQueryClient();
  const [subject, setSubject] = useState("");
  const [status, setStatus] = useState("");
  const [pendingOnly, setPendingOnly] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [confirmation, setConfirmation] = useState<Enrichment | null>(null);
  const [scope, setScope] = useState<"org" | "global">("org");

  const filters = { subject_code: subject, status, pending: pendingOnly };
  const questions = useQuery({
    queryKey: ["question-bank", filters],
    queryFn: () => listQuestions(filters),
  });

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
      queryClient.invalidateQueries({ queryKey: ["question-bank"] });
    },
  });
  const reviewMutation = useMutation({
    mutationFn: ({
      id,
      action,
    }: {
      id: string;
      action: "approve" | "reject" | "disable";
    }) => reviewQuestion(id, action),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["question-bank"] }),
  });

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
      source_type: role === "org_admin" ? "admin_manual" : "staff_manual",
    };
    createMutation.mutate(body);
  };

  const closeCreate = () => {
    setShowCreate(false);
    setDraft(EMPTY_DRAFT);
    setConfirmation(null);
    enrichMutation.reset();
    createMutation.reset();
  };

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
        {questions.isLoading && <p className="p-4 text-slate-500">加载中…</p>}
        {questions.error && (
          <p role="alert" className="p-4 text-red-600">
            {(questions.error as Error).message}
          </p>
        )}
        {questions.data?.length === 0 && (
          <p className="p-6 text-center text-slate-500">暂无题目</p>
        )}
        {!!questions.data?.length && (
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
              {questions.data.map((item) => {
                const canMutate = role === "org_admin" || item.scope === "org";
                return (
                  <tr key={item.id} className="border-t align-top">
                    <td className="max-w-xl px-4 py-3">{item.stem}</td>
                    <td className="px-4 py-3">
                      {SUBJECT_LABELS[item.subject_code] ?? item.subject_code}
                    </td>
                    <td className="px-4 py-3">{item.difficulty ?? "—"}</td>
                    <td className="px-4 py-3">
                      {STATUS_LABELS[item.status] ?? item.status}
                    </td>
                    <td className="space-x-2 whitespace-nowrap px-4 py-3">
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
        {reviewMutation.error && (
          <p role="alert" className="border-t p-3 text-sm text-red-600">
            {(reviewMutation.error as Error).message}
          </p>
        )}
      </section>

      {showCreate && (
        <div className="fixed inset-0 z-10 flex items-start justify-center overflow-auto bg-black/40 p-8">
          <div className="w-full max-w-2xl rounded bg-white p-6 shadow-xl">
            {!confirmation ? (
              <form onSubmit={onEnrich} className="space-y-4">
                <h2 className="text-lg font-semibold">新建题目</h2>
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
                    <option value="multiple_choice">多选题</option>
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
                {OBJECTIVE_TYPES.has(draft.qType) && (
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
                <p className="rounded bg-slate-50 p-3 text-sm">{draft.stem}</p>
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
                      })
                    }
                    className="w-full rounded border px-3 py-2"
                  >
                    {SUBJECTS.slice(1).map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                </label>
                <label className="block space-y-1">
                  <span>知识点 ID（可选）</span>
                  <input
                    value={confirmation.knowledge_node_id ?? ""}
                    onChange={(event) =>
                      setConfirmation({
                        ...confirmation,
                        knowledge_node_id: event.target.value || null,
                      })
                    }
                    className="w-full rounded border px-3 py-2"
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
