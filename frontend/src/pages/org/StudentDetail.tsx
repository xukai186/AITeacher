import { FormEvent, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchOrgOverview,
  fetchOrgPapers,
  fetchOrgPlans,
  fetchOrgTasks,
  fetchOrgWrongBook,
  lockPaper,
  patchMasterBudget,
  replacePaper,
  SUBJECT_LABELS,
} from "@/api/orgStudent";
import { useAuth } from "@/auth/AuthContext";

type Tab = "overview" | "plans" | "papers" | "wrong";

const PAPER_STATUS_LABELS: Record<string, string> = {
  draft: "草稿",
  locked: "已锁卷",
  replaced: "已换卷",
};

const JOB_STATUS_LABELS: Record<string, string> = {
  pending: "排队中",
  retry: "重试中",
  running: "执行中",
  succeeded: "已完成",
  failed: "失败",
};

function subjectLabel(code: string) {
  return SUBJECT_LABELS[code] ?? code;
}

function BudgetTable({ budget }: { budget: { date: string; minutes: number }[] | null }) {
  if (!budget?.length) {
    return <p className="text-sm text-slate-500">暂无预算数据</p>;
  }
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-slate-500">
          <th className="py-1 pr-4">日期</th>
          <th className="py-1">分钟</th>
        </tr>
      </thead>
      <tbody>
        {budget.map((row) => (
          <tr key={row.date}>
            <td className="py-1 pr-4">{row.date}</td>
            <td className="py-1">{row.minutes}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function StudentDetail() {
  const { studentId = "" } = useParams();
  const { state } = useAuth();
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("overview");
  const [budgetJson, setBudgetJson] = useState("");

  const backTo =
    state.status === "authed" && state.me.role === "org_staff"
      ? "/staff/students"
      : "/admin/students";

  const overview = useQuery({
    queryKey: ["org", studentId, "overview"],
    queryFn: () => fetchOrgOverview(studentId),
    enabled: !!studentId,
  });

  const tasks = useQuery({
    queryKey: ["org", studentId, "tasks"],
    queryFn: () => fetchOrgTasks(studentId),
    enabled: !!studentId && tab === "overview",
  });

  const plans = useQuery({
    queryKey: ["org", studentId, "plans"],
    queryFn: () => fetchOrgPlans(studentId),
    enabled: !!studentId && (tab === "plans" || tab === "overview"),
  });

  const papers = useQuery({
    queryKey: ["org", studentId, "papers"],
    queryFn: () => fetchOrgPapers(studentId),
    enabled: !!studentId && tab === "papers",
  });

  const wrong = useQuery({
    queryKey: ["org", studentId, "wrong"],
    queryFn: () => fetchOrgWrongBook(studentId),
    enabled: !!studentId && tab === "wrong",
  });

  const budgetMut = useMutation({
    mutationFn: (body: { date: string; minutes: number }[]) =>
      patchMasterBudget(studentId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["org", studentId, "plans"] });
    },
  });

  const lockMut = useMutation({
    mutationFn: (paperId: string) => lockPaper(studentId, paperId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["org", studentId, "papers"] }),
  });

  const replaceMut = useMutation({
    mutationFn: (paperId: string) => replacePaper(studentId, paperId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["org", studentId, "papers"] });
      qc.invalidateQueries({ queryKey: ["org", studentId, "overview"] });
    },
  });

  const defaultBudget = useMemo(() => {
    const v = plans.data?.master_version?.daily_time_budget_json;
    if (!v?.length) return '[{"date":"' + new Date().toISOString().slice(0, 10) + '","minutes":180}]';
    return JSON.stringify(v, null, 2);
  }, [plans.data]);

  const onSaveBudget = (e: FormEvent) => {
    e.preventDefault();
    const parsed = JSON.parse(budgetJson || defaultBudget) as { date: string; minutes: number }[];
    budgetMut.mutate(parsed);
  };

  const o = overview.data;
  const p = plans.data;

  return (
    <div className="space-y-4 max-w-4xl">
      <div className="flex items-center gap-3">
        <Link to={backTo} className="text-sm text-blue-600 hover:underline">
          ← 返回列表
        </Link>
        <h1 className="text-xl font-semibold">{o?.name ?? "学员详情"}</h1>
      </div>
      {o && <p className="text-sm text-slate-600">{o.email}</p>}

      {p?.requires_confirmation && (
        <div className="bg-amber-50 border border-amber-200 rounded p-3 text-sm text-amber-900">
          总计划有待学员确认的调整，当前版本尚未替换。
        </div>
      )}

      <div className="flex gap-2 border-b">
        {(
          [
            ["overview", "概览"],
            ["plans", "计划"],
            ["papers", "试卷"],
            ["wrong", "错题"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={`px-3 py-2 text-sm ${tab === key ? "border-b-2 border-blue-600 font-medium" : "text-slate-500"}`}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "overview" && o && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="bg-white rounded shadow p-3 text-sm">
              <div className="text-slate-500">错题总数</div>
              <div className="text-lg font-semibold">{o.wrong_book_total}</div>
            </div>
            <div className="bg-white rounded shadow p-3 text-sm">
              <div className="text-slate-500">今日待办</div>
              <div className="text-lg font-semibold">{tasks.data?.tasks.length ?? "—"}</div>
            </div>
            <div className="bg-white rounded shadow p-3 text-sm">
              <div className="text-slate-500">计划复审</div>
              <div className="text-lg font-semibold">
                {p?.plan_review_jobs.filter((j) =>
                  ["pending", "retry", "running"].includes(j.status),
                ).length ?? "—"}
              </div>
            </div>
            <div className="bg-white rounded shadow p-3 text-sm">
              <div className="text-slate-500">总计划状态</div>
              <div className="text-lg font-semibold">
                {p?.requires_confirmation ? "待确认" : (p?.master_status ?? "—")}
              </div>
            </div>
          </div>

          {tasks.data && tasks.data.tasks.length > 0 && (
            <section className="bg-white rounded shadow p-4">
              <h2 className="font-medium mb-2">今日待办（{tasks.data.date}）</h2>
              <ul className="text-sm divide-y">
                {tasks.data.tasks.map((t) => (
                  <li key={t.id} className="py-2 flex justify-between gap-2">
                    <span>
                      {subjectLabel(t.subject_code)} · {t.title}
                    </span>
                    <span className="text-slate-500 shrink-0">{t.est_minutes} 分钟</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {o.recent_papers.length > 0 && (
            <section className="bg-white rounded shadow p-4">
              <h2 className="font-medium mb-2">最近试卷</h2>
              <table className="w-full text-sm">
                <thead className="text-left text-slate-500">
                  <tr>
                    <th className="py-1">科目</th>
                    <th className="py-1">状态</th>
                    <th className="py-1">已提交</th>
                    <th className="py-1">时间</th>
                  </tr>
                </thead>
                <tbody>
                  {o.recent_papers.map((paper) => (
                    <tr key={paper.id} className="border-t">
                      <td className="py-1">{subjectLabel(paper.subject_code)}</td>
                      <td className="py-1">
                        {PAPER_STATUS_LABELS[paper.status] ?? paper.status}
                      </td>
                      <td className="py-1">{paper.has_submission ? "是" : "否"}</td>
                      <td className="py-1 text-slate-500">
                        {new Date(paper.created_at).toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          {o.subject_codes.map((code) => {
            const r = o.reports_by_subject[code];
            if (!r) return null;
            return (
              <div key={code} className="bg-white rounded shadow p-4 space-y-3">
                <h2 className="font-medium">{subjectLabel(code)}</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                  <div>
                    <div className="font-medium text-slate-700 mb-1">错题来源</div>
                    <p className="text-slate-600">
                      测评：{r.wrong_source_counts?.placement ?? 0}，自测：
                      {r.wrong_source_counts?.self_test ?? 0}
                    </p>
                  </div>
                  <div>
                    <div className="font-medium text-slate-700 mb-1">近 7 天</div>
                    <p className="text-slate-600">
                      新增错题：{r.last_7d?.wrong_added ?? 0}；自测次数：
                      {r.last_7d?.self_test_count ?? 0}
                      {r.last_7d?.self_test_avg_score != null
                        ? `；均分 ${r.last_7d.self_test_avg_score}`
                        : null}
                    </p>
                  </div>
                </div>

                {(r.weak_nodes ?? []).length > 0 && (
                  <div>
                    <div className="font-medium text-slate-700 mb-1">薄弱点 Top</div>
                    <ul className="text-sm text-slate-600 space-y-1">
                      {r.weak_nodes.map((n, idx) => (
                        <li key={n.knowledge_node_id ?? `null-${idx}`}>
                          {n.knowledge_node_name ?? "（未标注知识点）"}：{n.wrong_count}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {(r.recommendations ?? []).length > 0 && (
                  <div>
                    <div className="font-medium text-slate-700 mb-1">建议</div>
                    <ul className="text-sm space-y-2">
                      {r.recommendations.map((rec, i) => (
                        <li key={i} className="border-l-2 border-slate-200 pl-3">
                          <div className="font-medium">{rec.title}</div>
                          {rec.detail ? <div className="text-slate-600">{rec.detail}</div> : null}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {(r.self_test_trend ?? []).length > 0 && (
                  <div>
                    <div className="font-medium text-slate-700 mb-1">自测趋势</div>
                    <ul className="text-sm text-slate-600 space-y-1">
                      {r.self_test_trend.map((t) => (
                        <li key={t.submission_id} className="flex justify-between">
                          <span>{new Date(t.created_at).toLocaleString()}</span>
                          <span className="font-medium">{t.total_score} 分</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {tab === "plans" && p && (
        <div className="space-y-4">
          {p.master_version && (
            <div className="bg-white rounded shadow p-4 text-sm space-y-3">
              <p>
                当前总规划 v{p.master_version.version}（{p.master_version.source}）
              </p>
              {p.master_version.weekly_goals_json?.length ? (
                <div>
                  <h3 className="font-medium mb-1">本周目标</h3>
                  <ul className="list-disc pl-5 space-y-1">
                    {p.master_version.weekly_goals_json.map(
                      (g: { title?: string; description?: string }, i: number) => (
                        <li key={i}>
                          <span className="font-medium">{g.title}</span>
                          {g.description ? (
                            <span className="text-slate-600"> — {g.description}</span>
                          ) : null}
                        </li>
                      ),
                    )}
                  </ul>
                </div>
              ) : null}
              <div>
                <h3 className="font-medium mb-1">每日时间预算</h3>
                <BudgetTable budget={p.master_version.daily_time_budget_json} />
              </div>
            </div>
          )}

          {p.pending_version && (
            <div className="bg-amber-50 border border-amber-200 rounded p-4 text-sm space-y-2">
              <h3 className="font-medium text-amber-900">待学员确认的调整 v{p.pending_version.version}</h3>
              <BudgetTable budget={p.pending_version.daily_time_budget_json} />
            </div>
          )}

          {p.subject_versions.length > 0 && (
            <div className="bg-white rounded shadow p-4 text-sm space-y-3">
              <h3 className="font-medium">分科计划</h3>
              {p.subject_versions.map((sv) => (
                <div key={sv.id} className="border-t pt-2 first:border-t-0 first:pt-0">
                  <p className="font-medium">
                    {subjectLabel(sv.subject_code)} v{sv.version}（{sv.source}）
                  </p>
                  {sv.phases_json?.length ? (
                    <pre className="mt-1 bg-slate-50 p-2 rounded overflow-auto text-xs">
                      {JSON.stringify(sv.phases_json, null, 2)}
                    </pre>
                  ) : (
                    <p className="text-slate-500">暂无阶段数据</p>
                  )}
                </div>
              ))}
            </div>
          )}

          {p.plan_review_jobs.length > 0 && (
            <div className="bg-white rounded shadow p-4 text-sm">
              <h3 className="font-medium mb-2">计划复审任务（最近 10 条）</h3>
              <table className="w-full">
                <thead className="text-left text-slate-500">
                  <tr>
                    <th className="py-1">科目</th>
                    <th className="py-1">目标日</th>
                    <th className="py-1">状态</th>
                    <th className="py-1">结果</th>
                  </tr>
                </thead>
                <tbody>
                  {p.plan_review_jobs.map((j) => (
                    <tr key={j.id} className="border-t">
                      <td className="py-1">{subjectLabel(j.subject_code)}</td>
                      <td className="py-1">{j.target_date}</td>
                      <td className="py-1">{JOB_STATUS_LABELS[j.status] ?? j.status}</td>
                      <td className="py-1 text-slate-600">
                        {j.status === "succeeded"
                          ? `生成 ${j.created_count ?? 0} 项`
                          : j.last_error ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <form onSubmit={onSaveBudget} className="bg-white rounded shadow p-4 space-y-2">
            <label className="text-sm font-medium">更新每日时间预算（JSON）</label>
            <textarea
              className="w-full border rounded p-2 font-mono text-xs h-40"
              defaultValue={defaultBudget}
              onChange={(e) => setBudgetJson(e.target.value)}
            />
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded text-sm"
              disabled={budgetMut.isPending}
            >
              保存并生效
            </button>
            {budgetMut.isError && (
              <p className="text-red-600 text-sm">{(budgetMut.error as Error).message}</p>
            )}
          </form>
        </div>
      )}

      {tab === "papers" && (
        <table className="w-full text-sm bg-white shadow rounded">
          <thead className="bg-slate-100 text-left">
            <tr>
              <th className="px-3 py-2">科目</th>
              <th className="px-3 py-2">状态</th>
              <th className="px-3 py-2">已提交</th>
              <th className="px-3 py-2">操作</th>
            </tr>
          </thead>
          <tbody>
            {papers.data?.map((paper) => (
              <tr key={paper.id} className="border-t">
                <td className="px-3 py-2">{subjectLabel(paper.subject_code)}</td>
                <td className="px-3 py-2">
                  {PAPER_STATUS_LABELS[paper.status] ?? paper.status}
                </td>
                <td className="px-3 py-2">{paper.has_submission ? "是" : "否"}</td>
                <td className="px-3 py-2 space-x-2">
                  {paper.status !== "locked" && paper.status !== "replaced" && (
                    <button
                      type="button"
                      className="text-blue-600 underline"
                      onClick={() => lockMut.mutate(paper.id)}
                    >
                      锁卷
                    </button>
                  )}
                  {paper.status !== "replaced" && (
                    <button
                      type="button"
                      className="text-amber-700 underline"
                      onClick={() => replaceMut.mutate(paper.id)}
                    >
                      换卷
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {tab === "wrong" && (
        <ul className="bg-white rounded shadow divide-y text-sm">
          {wrong.data?.map((w) => {
            const choices = Array.isArray(w.question_snapshot_json?.choices)
              ? (w.question_snapshot_json.choices as { key?: string; text?: string }[])
              : [];
            return (
              <li key={w.id} className="px-4 py-3 space-y-1">
                <span className="text-slate-500">{subjectLabel(w.subject_code)}</span> · {w.source_type}
                <div className="mt-1 font-medium">{w.question_snapshot_json?.stem ?? "（无题干）"}</div>
                {choices.length > 0 ? (
                  <ul className="text-slate-700 space-y-0.5">
                    {choices.map((c, idx) => (
                      <li key={String(c.key ?? idx)}>
                        {String(c.key ?? "")}. {String(c.text ?? "")}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </li>
            );
          })}
          {wrong.data?.length === 0 && (
            <li className="px-4 py-6 text-center text-slate-500">暂无错题</li>
          )}
        </ul>
      )}
    </div>
  );
}
