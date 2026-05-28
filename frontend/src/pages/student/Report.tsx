import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { fetchStudentMe } from "@/api/me";
import { fetchStudentReportOverview } from "@/api/report";

const SUBJECT_LABELS: Record<string, string> = {
  politics: "政治",
  english: "英语",
  math: "数学",
};

export default function Report() {
  const me = useQuery({ queryKey: ["student", "me"], queryFn: fetchStudentMe });
  const [subject, setSubject] = useState<string>("__default__");

  const subjectOptions = useMemo(() => me.data?.subject_codes ?? [], [me.data?.subject_codes]);
  const effectiveSubject = subject === "__default__" ? subjectOptions[0] || "" : subject;

  const overview = useQuery({
    queryKey: ["student", "report_overview", effectiveSubject],
    queryFn: () =>
      fetchStudentReportOverview({
        subject_code: effectiveSubject || undefined,
      }),
    enabled: Boolean(me.data),
  });

  if (me.isLoading) return <p className="text-slate-500">加载中…</p>;
  if (me.error) return <p className="text-red-600">{(me.error as Error).message}</p>;

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <header className="flex justify-between items-baseline">
        <h1 className="text-xl font-semibold">学情报告</h1>
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
        </div>
      </header>

      {overview.isLoading ? (
        <p className="text-slate-500 text-sm">加载中…</p>
      ) : overview.error ? (
        <p className="text-red-600 text-sm">{(overview.error as Error).message}</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="bg-white shadow rounded p-4 space-y-2">
            <div className="font-medium">错题来源</div>
            <div className="text-sm text-slate-700">
              测评：{overview.data?.wrong_source_counts?.placement ?? 0}，自测：
              {overview.data?.wrong_source_counts?.self_test ?? 0}
            </div>
          </div>
          <div className="bg-white shadow rounded p-4 space-y-2">
            <div className="font-medium">薄弱点 Top</div>
            <ul className="text-sm text-slate-700 space-y-1">
              {(overview.data?.weak_nodes ?? []).map((n, idx) => (
                <li key={n.knowledge_node_id ?? `null-${idx}`}>
                  {n.knowledge_node_name ?? "（未标注知识点）"}：{n.wrong_count}
                </li>
              ))}
            </ul>
          </div>
          <div className="bg-white shadow rounded p-4 space-y-2 md:col-span-2">
            <div className="font-medium">建议</div>
            {(overview.data?.recommendations ?? []).length === 0 ? (
              <div className="text-sm text-slate-500">暂无建议。</div>
            ) : (
              <ul className="text-sm text-slate-700 space-y-2">
                {(overview.data?.recommendations ?? []).map((r, idx) => (
                  <li key={`${r.type}-${idx}`} className="border-l-2 border-slate-200 pl-3">
                    <div className="font-medium text-slate-900">{r.title}</div>
                    <div className="text-slate-700">{r.detail}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="bg-white shadow rounded p-4 space-y-2 md:col-span-2">
            <div className="font-medium">自测趋势</div>
            {(overview.data?.self_test_trend ?? []).length === 0 ? (
              <div className="text-sm text-slate-500">暂无自测记录。</div>
            ) : (
              <ul className="text-sm text-slate-700 space-y-1">
                {(overview.data?.self_test_trend ?? []).map((t) => (
                  <li key={t.submission_id} className="flex justify-between items-center">
                    <span className="text-slate-600">{new Date(t.created_at).toLocaleString()}</span>
                    <div className="flex items-center gap-3">
                      <span className="font-medium text-slate-900">{t.total_score} 分</span>
                      <Link
                        to={`/student/self-tests/result/${t.submission_id}`}
                        className="text-slate-700 underline"
                      >
                        查看结果
                      </Link>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

