import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchStudentMe } from "@/api/me";

const SUBJECT_LABELS: Record<string, string> = {
  politics: "政治",
  english: "英语",
  math: "数学",
};

export default function Workspace() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["student", "me"],
    queryFn: fetchStudentMe,
  });

  const [activeSubject, setActiveSubject] = useState<string | null>(null);

  if (isLoading) return <p className="text-slate-500">加载中…</p>;
  if (error) return <p className="text-red-600">{(error as Error).message}</p>;
  if (!data) return null;

  const current = activeSubject ?? data.subject_codes[0] ?? null;

  return (
    <div className="grid grid-cols-12 gap-4 h-full">
      <div className="col-span-7 bg-white shadow rounded p-6 space-y-4">
        <header className="flex justify-between items-baseline">
          <h1 className="text-xl font-semibold">今日计划</h1>
          <div className="text-sm text-slate-500">考试年份：{data.exam_year}</div>
        </header>
        <div className="flex gap-2 flex-wrap">
          {data.subject_codes.map((code) => (
            <button
              key={code}
              onClick={() => setActiveSubject(code)}
              className={`px-3 py-1 rounded border text-sm ${
                current === code
                  ? "bg-slate-900 text-white border-slate-900"
                  : "bg-white text-slate-700 border-slate-300"
              }`}
            >
              {SUBJECT_LABELS[code] ?? code}
            </button>
          ))}
          {data.subject_codes.length === 0 && (
            <p className="text-slate-500 text-sm">尚未开通科目，请联系管理员</p>
          )}
        </div>
        <p className="text-slate-500 text-sm">
          {current
            ? `${SUBJECT_LABELS[current] ?? current} 暂无今日任务（P3 将启用）。`
            : "暂无今日任务。"}
        </p>
      </div>
      <aside className="col-span-5 bg-white shadow rounded p-6">
        <h2 className="font-semibold mb-3">
          {current ? `${SUBJECT_LABELS[current] ?? current} AI 老师` : "AI 老师"}
        </h2>
        <p className="text-slate-500 text-sm">对话功能将在 P2 接入。</p>
      </aside>
    </div>
  );
}
