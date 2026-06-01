import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  enqueueApplyRecommendations,
  fetchPlanReviewJob,
  pollPlanReviewJob,
} from "@/api/agent";
import { fetchStudentMe } from "@/api/me";
import { fetchStudentReportOverview } from "@/api/report";

const SUBJECT_LABELS: Record<string, string> = {
  politics: "政治",
  english: "英语",
  math: "数学",
};

export default function Report() {
  const queryClient = useQueryClient();
  const me = useQuery({ queryKey: ["student", "me"], queryFn: fetchStudentMe });
  const [subject, setSubject] = useState<string>("__default__");
  const [applyMessage, setApplyMessage] = useState<string | null>(null);

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

  const applyTasks = useMutation({
    mutationFn: async () => {
      const enqueued = await enqueueApplyRecommendations({
        subject_code: effectiveSubject,
      });
      if (enqueued.status === "succeeded") {
        const done = await fetchPlanReviewJob(enqueued.job_id);
        return done;
      }
      return pollPlanReviewJob(enqueued.job_id, { intervalMs: 400, timeoutMs: 30000 });
    },
    onSuccess: (job) => {
      void queryClient.invalidateQueries({ queryKey: ["student", "tasks", "today"] });
      if (job.status === "failed") {
        setApplyMessage(job.last_error || "任务生成失败");
        return;
      }
      const created = job.created_count ?? 0;
      const skipped = job.skipped_count ?? 0;
      const warn = job.warnings.length ? ` ${job.warnings.join(" ")}` : "";
      setApplyMessage(
        `已为 ${job.target_date} 生成 ${created} 项任务（跳过 ${skipped} 项重复）。${warn}`,
      );
    },
    onError: (err) => setApplyMessage((err as Error).message),
  });

  if (me.isLoading) return <p className="text-slate-500">加载中…</p>;
  if (me.error) return <p className="text-red-600">{(me.error as Error).message}</p>;

  function wrongBookLink(knowledgeNodeId: string | null): string {
    const qs = new URLSearchParams();
    if (effectiveSubject) qs.set("subject_code", effectiveSubject);
    if (knowledgeNodeId) qs.set("knowledge_node_id", knowledgeNodeId);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return `/student/wrong-book${suffix}`;
  }

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
                <li key={n.knowledge_node_id ?? `null-${idx}`} className="flex justify-between items-center">
                  <span>
                    {n.knowledge_node_name ?? "（未标注知识点）"}：{n.wrong_count}
                  </span>
                  {n.knowledge_node_id ? (
                    <Link to={wrongBookLink(n.knowledge_node_id)} className="text-slate-700 underline">
                      查看错题
                    </Link>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
          <div className="bg-white shadow rounded p-4 space-y-2 md:col-span-2">
            <div className="flex justify-between items-center gap-2">
              <div className="font-medium">建议</div>
              {effectiveSubject && (overview.data?.recommendations ?? []).length > 0 ? (
                <button
                  type="button"
                  className="text-sm px-3 py-1 rounded bg-slate-900 text-white disabled:opacity-50"
                  disabled={applyTasks.isPending}
                  onClick={() => {
                    setApplyMessage(null);
                    applyTasks.mutate();
                  }}
                >
                  {applyTasks.isPending ? "生成中…" : "生成明日任务"}
                </button>
              ) : null}
            </div>
            {applyMessage ? <p className="text-sm text-slate-600">{applyMessage}</p> : null}
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
            <div className="font-medium">近 7 天</div>
            <div className="text-sm text-slate-700">
              新增错题：{overview.data?.last_7d?.wrong_added ?? 0}
            </div>
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

