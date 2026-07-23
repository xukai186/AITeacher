import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { postChat } from "@/api/chat";
import { fetchStudentMe } from "@/api/me";
import {
  archiveWrongItem,
  listWrongBook,
  practiceWrongItem,
  type WrongBookItemOut,
  type WrongBookPracticeOut,
} from "@/api/wrongBook";
import ChatRichText from "@/components/chat/ChatRichText";
import MathText from "@/components/MathText";

type SnapshotChoice = { key: string; text: string };

function snapshotChoices(item: WrongBookItemOut): SnapshotChoice[] {
  const raw = (item.question_snapshot_json as { choices?: unknown } | undefined)?.choices;
  if (!Array.isArray(raw)) return [];
  return raw
    .map((c) => {
      if (!c || typeof c !== "object") return null;
      const row = c as { key?: unknown; text?: unknown };
      const key = String(row.key ?? "").trim();
      if (!key) return null;
      return { key, text: String(row.text ?? "") };
    })
    .filter((c): c is SnapshotChoice => c != null);
}

function snapshotStem(item: WrongBookItemOut): string {
  return String((item.question_snapshot_json as { stem?: string } | undefined)?.stem ?? "（无题干）");
}

function studentAnswerOf(item: WrongBookItemOut): string {
  return String((item.answer_snapshot_json as { content?: string } | undefined)?.content ?? "");
}

function correctAnswerOf(item: WrongBookItemOut): string {
  return String((item.correct_snapshot_json as { answer_key?: string } | undefined)?.answer_key ?? "");
}

const SUBJECT_LABELS: Record<string, string> = {
  politics: "政治",
  english: "英语",
  math: "数学",
};

const SOURCE_LABELS: Record<string, string> = {
  "": "全部",
  self_test: "自测",
  placement: "测评",
};

const STATUS_LABELS: Record<string, string> = {
  active: "待掌握",
  mastered: "已掌握",
  archived: "已归档",
};

type PracticeReveal = WrongBookPracticeOut & { attempt: string };

function WrongBookPractice({
  item,
  choices,
  onRevealed,
}: {
  item: WrongBookItemOut;
  choices: SnapshotChoice[];
  onRevealed: (result: PracticeReveal) => void;
}) {
  const qc = useQueryClient();
  const [content, setContent] = useState("");
  const practice = useMutation({
    mutationFn: () => practiceWrongItem(item.id, content),
    onSuccess: (data) => {
      onRevealed({ ...data, attempt: content.trim() });
      qc.invalidateQueries({ queryKey: ["student", "wrong_book"] });
    },
  });

  return (
    <div className="border-t pt-2 space-y-2">
      <div className="text-sm text-slate-600">重做（答案与解析在提交后显示）</div>
      {choices.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {choices.map((c) => (
            <label key={c.key} className="flex items-start gap-2 text-sm">
              <input
                type="radio"
                name={`practice-${item.id}`}
                className="mt-1"
                value={c.key}
                checked={content === c.key}
                disabled={practice.isPending}
                onChange={() => setContent(c.key)}
              />
              <span>
                <span className="font-medium">{c.key}.</span> <MathText text={c.text} />
              </span>
            </label>
          ))}
        </div>
      ) : (
        <input
          className="border rounded px-2 py-1 text-sm w-full"
          placeholder="输入你的答案"
          value={content}
          disabled={practice.isPending}
          onChange={(e) => setContent(e.target.value)}
        />
      )}
      <button
        type="button"
        className="px-3 py-1 bg-slate-900 text-white rounded text-sm disabled:opacity-50"
        disabled={!content.trim() || practice.isPending}
        onClick={() => practice.mutate()}
      >
        {practice.isPending ? "提交中…" : "提交重做"}
      </button>
    </div>
  );
}

function WrongBookItemCard({
  item,
  index,
  reveal,
  onRevealed,
  onResetReveal,
}: {
  item: WrongBookItemOut;
  index: number;
  reveal: PracticeReveal | undefined;
  onRevealed: (result: PracticeReveal) => void;
  onResetReveal: () => void;
}) {
  const qc = useQueryClient();
  const choices = snapshotChoices(item);
  const correctAnswer = correctAnswerOf(item);
  const originalStudentAnswer = studentAnswerOf(item);
  // Active items stay concealed until this session's practice submit; mastered/archived always show.
  const showAnswers = item.status !== "active" || Boolean(reveal);
  const practiceAttempt = reveal?.attempt ?? "";
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

  return (
    <li className="bg-white shadow rounded p-4 space-y-2">
      <div className="text-sm text-slate-500 flex justify-between">
        <span>
          错题 {index}
          {" · "}
          {SUBJECT_LABELS[item.subject_code] ?? item.subject_code} ·{" "}
          {SOURCE_LABELS[item.source_type] ?? item.source_type}
          {(item.question_snapshot_json as { seq?: number } | undefined)?.seq != null
            ? ` · 原卷第 ${(item.question_snapshot_json as { seq: number }).seq} 题`
            : ""}
        </span>
        <span className="font-medium text-slate-700">
          {STATUS_LABELS[item.status] ?? item.status}
          {item.consecutive_correct_count > 0 && item.status === "active"
            ? ` (${item.consecutive_correct_count}/2)`
            : ""}
        </span>
      </div>

      <div className="font-medium">
        <MathText text={snapshotStem(item)} />
      </div>

      {choices.length > 0 ? (
        <ul className="space-y-1 text-sm">
          {choices.map((c) => {
            const isCorrect = showAnswers && correctAnswer.includes(c.key);
            const isAttempt = showAnswers && practiceAttempt.includes(c.key);
            // Original wrong pick is always visible so students remember what they chose.
            const isOriginal =
              originalStudentAnswer.includes(c.key) &&
              !(showAnswers && correctAnswer.includes(c.key));
            return (
              <li
                key={c.key}
                className={
                  isCorrect
                    ? "text-green-700"
                    : isAttempt && !isCorrect
                      ? "text-red-600"
                      : isOriginal
                        ? "text-amber-700"
                        : "text-slate-800"
                }
              >
                <span className="font-medium">{c.key}.</span> <MathText text={c.text} />
                {isCorrect ? "（正确）" : null}
                {isAttempt && !isCorrect ? "（本次选择）" : null}
                {isOriginal && !isCorrect ? "（当时选择）" : null}
              </li>
            );
          })}
        </ul>
      ) : null}

      <div className="text-sm space-y-1 rounded bg-slate-50 p-2">
        <div>
          <span className="text-slate-600">当时答案：</span>
          <span className="text-slate-900">{originalStudentAnswer || "（空）"}</span>
        </div>
        {showAnswers ? (
          <>
            {reveal ? (
              <div>
                <span className="text-slate-600">本次作答：</span>
                <span className="text-slate-900">{reveal.attempt || "（空）"}</span>
              </div>
            ) : null}
            <div>
              <span className="text-slate-600">参考答案：</span>
              <span className="text-slate-900">{correctAnswer || "（无）"}</span>
            </div>
            {reveal ? (
              <p className={reveal.is_correct ? "text-green-700" : "text-red-600"}>
                {reveal.is_correct ? "回答正确" : "回答错误"}
                {reveal.mastered ? " — 已标记为掌握！" : ""}
                {!reveal.mastered && reveal.consecutive_correct_count === 1
                  ? " — 间隔至少 1 天后再做对一次可标记掌握"
                  : ""}
              </p>
            ) : null}
          </>
        ) : (
          <p className="text-xs text-slate-500">参考答案已隐藏，完成重做后揭晓。</p>
        )}
      </div>

      {item.status === "active" && !reveal ? (
        <WrongBookPractice item={item} choices={choices} onRevealed={onRevealed} />
      ) : null}

      {item.status === "active" && reveal ? (
        <button type="button" className="text-sm text-slate-600 underline" onClick={onResetReveal}>
          再练一次（将重新隐藏答案）
        </button>
      ) : null}

      {item.status === "mastered" ? (
        <button
          type="button"
          className="text-sm text-slate-600 underline"
          onClick={async () => {
            await archiveWrongItem(item.id);
            qc.invalidateQueries({ queryKey: ["student", "wrong_book"] });
          }}
        >
          归档
        </button>
      ) : null}

      <div className="flex flex-wrap gap-3 items-center">
        <button
          type="button"
          className="text-sm text-slate-900 underline disabled:opacity-50"
          disabled={explainLoading}
          onClick={() => void runExplain()}
        >
          {explainLoading ? "讲解中…" : "错题讲解"}
        </button>
        {explainText && !explainOpen ? (
          <button
            type="button"
            className="text-sm text-slate-500 underline"
            onClick={() => setExplainOpen(true)}
          >
            展开讲解
          </button>
        ) : null}
        {explainText && explainOpen ? (
          <button
            type="button"
            className="text-sm text-slate-500 underline"
            onClick={() => setExplainOpen(false)}
          >
            收起讲解
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
    </li>
  );
}

export default function WrongBook() {
  const [searchParams, setSearchParams] = useSearchParams();
  const me = useQuery({ queryKey: ["student", "me"], queryFn: fetchStudentMe });
  // "__default__" means use first subject in profile.
  // "" means all subjects (no subject_code filter).
  const [subject, setSubject] = useState<string>("__default__");
  const [sourceType, setSourceType] = useState<string>("");
  const [knowledgeNodeId, setKnowledgeNodeId] = useState<string>("");
  const [offset, setOffset] = useState(0);
  const limit = 20;
  const [allItems, setAllItems] = useState<WrongBookItemOut[]>([]);
  const [hasMore, setHasMore] = useState(true);
  const [reveals, setReveals] = useState<Record<string, PracticeReveal | undefined>>({});

  const subjectOptions = useMemo(() => me.data?.subject_codes ?? [], [me.data?.subject_codes]);
  const effectiveSubject = subject === "__default__" ? subjectOptions[0] || "" : subject;

  useEffect(() => {
    const pSubject = searchParams.get("subject_code");
    const pSourceType = searchParams.get("source_type");
    const pNode = searchParams.get("knowledge_node_id");
    if (pSubject !== null) setSubject(pSubject);
    if (pSourceType !== null) setSourceType(pSourceType);
    if (pNode !== null) setKnowledgeNodeId(pNode);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const items = useQuery({
    queryKey: ["student", "wrong_book", effectiveSubject, sourceType, knowledgeNodeId, offset, limit],
    queryFn: () =>
      listWrongBook({
        subject_code: effectiveSubject || undefined,
        source_type: sourceType || undefined,
        knowledge_node_id: knowledgeNodeId || undefined,
        limit,
        offset,
      }),
    enabled: Boolean(me.data),
  });

  useEffect(() => {
    setOffset(0);
    setAllItems([]);
    setHasMore(true);
    setReveals({});
  }, [effectiveSubject, sourceType, knowledgeNodeId]);

  useEffect(() => {
    if (!items.data) return;
    setAllItems((prev) => {
      const existing = new Set(prev.map((i) => i.id));
      const next = [...prev];
      for (const it of items.data) {
        if (!existing.has(it.id)) next.push(it);
      }
      return next;
    });
    setHasMore(items.data.length === limit);
  }, [items.data, limit]);

  if (me.isLoading) return <p className="text-slate-500">加载中…</p>;
  if (me.error) return <p className="text-red-600">{(me.error as Error).message}</p>;

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <header className="flex justify-between items-baseline">
        <h1 className="text-xl font-semibold">错题本</h1>
        <div className="flex items-center gap-2">
          <span className="text-sm text-slate-600">科目</span>
          <select
            className="border rounded px-2 py-1 text-sm"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
          >
            <option value="__default__">（默认）</option>
            <option value="">全部科目</option>
            {subjectOptions.map((code) => (
              <option key={code} value={code}>
                {SUBJECT_LABELS[code] ?? code}
              </option>
            ))}
          </select>
          <span className="text-sm text-slate-600 ml-2">来源</span>
          <select
            className="border rounded px-2 py-1 text-sm"
            value={sourceType}
            onChange={(e) => setSourceType(e.target.value)}
          >
            {Object.entries(SOURCE_LABELS).map(([v, label]) => (
              <option key={v || "all"} value={v}>
                {label}
              </option>
            ))}
          </select>
        </div>
      </header>

      {knowledgeNodeId ? (
        <div className="bg-white shadow rounded p-3 text-sm flex items-center justify-between">
          <div className="text-slate-700">
            当前筛选：<span className="font-mono">{knowledgeNodeId}</span>
          </div>
          <button
            className="underline text-slate-700"
            onClick={() => {
              setKnowledgeNodeId("");
              const next = new URLSearchParams(searchParams);
              next.delete("knowledge_node_id");
              setSearchParams(next);
            }}
          >
            清除知识点筛选
          </button>
        </div>
      ) : null}

      {items.isLoading && allItems.length === 0 ? (
        <p className="text-slate-500 text-sm">加载中…</p>
      ) : items.error ? (
        <p className="text-red-600 text-sm">{(items.error as Error).message}</p>
      ) : allItems.length === 0 ? (
        <div className="bg-white shadow rounded p-4">
          <p className="text-slate-500 text-sm">暂无错题。</p>
        </div>
      ) : (
        <div className="space-y-3">
          <ul className="space-y-3">
            {allItems.map((i, idx) => (
              <WrongBookItemCard
                key={i.id}
                item={i}
                index={idx + 1}
                reveal={reveals[i.id]}
                onRevealed={(result) => setReveals((prev) => ({ ...prev, [i.id]: result }))}
                onResetReveal={() =>
                  setReveals((prev) => {
                    const next = { ...prev };
                    delete next[i.id];
                    return next;
                  })
                }
              />
            ))}
          </ul>

          <div className="flex justify-center">
            {hasMore ? (
              <button
                className="border rounded px-3 py-2 text-sm bg-white hover:bg-slate-50 disabled:opacity-50"
                onClick={() => setOffset((o) => o + limit)}
                disabled={items.isLoading}
              >
                {items.isLoading ? "加载中…" : "加载更多"}
              </button>
            ) : (
              <span className="text-slate-500 text-sm">没有更多了</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
