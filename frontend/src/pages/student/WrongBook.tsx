import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchStudentMe } from "@/api/me";
import { listWrongBook } from "@/api/wrongBook";

const SUBJECT_LABELS: Record<string, string> = {
  politics: "政治",
  english: "英语",
  math: "数学",
};

export default function WrongBook() {
  const me = useQuery({ queryKey: ["student", "me"], queryFn: fetchStudentMe });
  const [subject, setSubject] = useState<string>("");

  const subjectOptions = useMemo(() => me.data?.subject_codes ?? [], [me.data?.subject_codes]);
  const effectiveSubject = subject || subjectOptions[0] || "";

  const items = useQuery({
    queryKey: ["student", "wrong_book", effectiveSubject],
    queryFn: () => listWrongBook(effectiveSubject),
    enabled: Boolean(effectiveSubject),
  });

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
            value={effectiveSubject}
            onChange={(e) => setSubject(e.target.value)}
          >
            {subjectOptions.map((code) => (
              <option key={code} value={code}>
                {SUBJECT_LABELS[code] ?? code}
              </option>
            ))}
          </select>
        </div>
      </header>

      {items.isLoading ? (
        <p className="text-slate-500 text-sm">加载中…</p>
      ) : items.error ? (
        <p className="text-red-600 text-sm">{(items.error as Error).message}</p>
      ) : (items.data ?? []).length === 0 ? (
        <div className="bg-white shadow rounded p-4">
          <p className="text-slate-500 text-sm">暂无错题。</p>
        </div>
      ) : (
        <ul className="space-y-3">
          {(items.data ?? []).map((i) => (
            <li key={i.id} className="bg-white shadow rounded p-4 space-y-2">
              <div className="text-sm text-slate-500">
                {SUBJECT_LABELS[i.subject_code] ?? i.subject_code} · {i.source_type}
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
      )}
    </div>
  );
}

