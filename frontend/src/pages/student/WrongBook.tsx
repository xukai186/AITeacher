import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchStudentMe } from "@/api/me";
import { listWrongBook } from "@/api/wrongBook";

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

export default function WrongBook() {
  const me = useQuery({ queryKey: ["student", "me"], queryFn: fetchStudentMe });
  // "__default__" means use first subject in profile.
  // "" means all subjects (no subject_code filter).
  const [subject, setSubject] = useState<string>("__default__");
  const [sourceType, setSourceType] = useState<string>("");
  const [offset, setOffset] = useState(0);
  const limit = 20;
  const [allItems, setAllItems] = useState<any[]>([]);
  const [hasMore, setHasMore] = useState(true);

  const subjectOptions = useMemo(() => me.data?.subject_codes ?? [], [me.data?.subject_codes]);
  const effectiveSubject = subject === "__default__" ? subjectOptions[0] || "" : subject;

  const items = useQuery({
    queryKey: ["student", "wrong_book", effectiveSubject, sourceType, offset, limit],
    queryFn: () =>
      listWrongBook({
        subject_code: effectiveSubject || undefined,
        source_type: sourceType || undefined,
        limit,
        offset,
      }),
    enabled: Boolean(me.data),
  });

  useEffect(() => {
    setOffset(0);
    setAllItems([]);
    setHasMore(true);
  }, [effectiveSubject, sourceType]);

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
                <div className="text-sm text-slate-500">
                  {SUBJECT_LABELS[i.subject_code] ?? i.subject_code} · {SOURCE_LABELS[i.source_type] ?? i.source_type}
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

