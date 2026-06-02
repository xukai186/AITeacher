import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { fetchStudentMe } from "@/api/me";
import { archiveWrongItem, listWrongBook, practiceWrongItem } from "@/api/wrongBook";

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

function WrongBookPractice({ itemId, answerKey }: { itemId: string; answerKey: string }) {
  const qc = useQueryClient();
  const [content, setContent] = useState("");
  const practice = useMutation({
    mutationFn: () => practiceWrongItem(itemId, content),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["student", "wrong_book"] });
      setContent("");
    },
  });

  return (
    <div className="border-t pt-2 space-y-2">
      <div className="text-sm text-slate-600">重做（客观题填选项字母，如 A）</div>
      <div className="flex gap-2">
        <input
          className="border rounded px-2 py-1 text-sm flex-1"
          placeholder={answerKey ? `参考答案: ${answerKey}` : "你的答案"}
          value={content}
          onChange={(e) => setContent(e.target.value)}
        />
        <button
          type="button"
          className="px-3 py-1 bg-slate-900 text-white rounded text-sm disabled:opacity-50"
          disabled={!content.trim() || practice.isPending}
          onClick={() => practice.mutate()}
        >
          提交
        </button>
      </div>
      {practice.data && (
        <p className={`text-sm ${practice.data.is_correct ? "text-green-700" : "text-red-600"}`}>
          {practice.data.is_correct ? "回答正确" : "回答错误"}
          {practice.data.mastered ? " — 已标记为掌握！" : ""}
          {!practice.data.mastered && practice.data.consecutive_correct_count === 1
            ? " — 间隔至少 1 天后再做对一次可标记掌握"
            : ""}
        </p>
      )}
    </div>
  );
}

export default function WrongBook() {
  const qc = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const me = useQuery({ queryKey: ["student", "me"], queryFn: fetchStudentMe });
  // "__default__" means use first subject in profile.
  // "" means all subjects (no subject_code filter).
  const [subject, setSubject] = useState<string>("__default__");
  const [sourceType, setSourceType] = useState<string>("");
  const [knowledgeNodeId, setKnowledgeNodeId] = useState<string>("");
  const [offset, setOffset] = useState(0);
  const limit = 20;
  const [allItems, setAllItems] = useState<any[]>([]);
  const [hasMore, setHasMore] = useState(true);

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
            {allItems.map((i) => (
              <li key={i.id} className="bg-white shadow rounded p-4 space-y-2">
                <div className="text-sm text-slate-500 flex justify-between">
                  <span>
                    {SUBJECT_LABELS[i.subject_code] ?? i.subject_code} ·{" "}
                    {SOURCE_LABELS[i.source_type] ?? i.source_type}
                  </span>
                  <span className="font-medium text-slate-700">
                    {STATUS_LABELS[i.status] ?? i.status}
                    {i.consecutive_correct_count > 0 && i.status === "active"
                      ? ` (${i.consecutive_correct_count}/2)`
                      : ""}
                  </span>
                </div>
                <div className="font-medium">
                  {String((i.question_snapshot_json as any)?.stem ?? "（无题干）")}
                </div>
                <div className="text-sm">
                  <div className="text-slate-600">你的答案</div>
                  <div className="text-slate-900">
                    {String((i.answer_snapshot_json as any)?.content ?? "")}
                  </div>
                </div>
                <div className="text-sm">
                  <div className="text-slate-600">参考答案</div>
                  <div className="text-slate-900">
                    {String((i.correct_snapshot_json as any)?.answer_key ?? "")}
                  </div>
                </div>
                {i.status === "active" && (
                  <WrongBookPractice
                    itemId={i.id}
                    answerKey={String((i.correct_snapshot_json as any)?.answer_key ?? "")}
                  />
                )}
                {i.status === "mastered" && (
                  <button
                    type="button"
                    className="text-sm text-slate-600 underline"
                    onClick={async () => {
                      await archiveWrongItem(i.id);
                      qc.invalidateQueries({ queryKey: ["student", "wrong_book"] });
                    }}
                  >
                    归档
                  </button>
                )}
              </li>
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

