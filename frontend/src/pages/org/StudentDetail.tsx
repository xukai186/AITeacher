import { FormEvent, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchOrgOverview,
  fetchOrgPapers,
  fetchOrgPlans,
  fetchOrgWrongBook,
  lockPaper,
  patchMasterBudget,
  replacePaper,
} from "@/api/orgStudent";
import { useAuth } from "@/auth/AuthContext";

type Tab = "overview" | "plans" | "papers" | "wrong";

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

  const plans = useQuery({
    queryKey: ["org", studentId, "plans"],
    queryFn: () => fetchOrgPlans(studentId),
    enabled: !!studentId && tab === "plans",
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

  return (
    <div className="space-y-4 max-w-4xl">
      <div className="flex items-center gap-3">
        <Link to={backTo} className="text-sm text-blue-600 hover:underline">
          ← 返回列表
        </Link>
        <h1 className="text-xl font-semibold">{o?.name ?? "学员详情"}</h1>
      </div>
      {o && <p className="text-sm text-slate-600">{o.email}</p>}

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
          <p className="text-sm">错题总数：{o.wrong_book_total}</p>
          {o.subject_codes.map((code) => {
            const r = o.reports_by_subject[code];
            if (!r) return null;
            return (
              <div key={code} className="bg-white rounded shadow p-4">
                <h2 className="font-medium mb-2">{code}</h2>
                <p className="text-sm text-slate-600">
                  近7天错题：{r.last_7d?.wrong_added ?? 0}；自测次数：
                  {r.last_7d?.self_test_count ?? 0}
                </p>
                {r.recommendations?.length ? (
                  <ul className="mt-2 text-sm list-disc pl-5">
                    {r.recommendations.map((rec, i) => (
                      <li key={i}>{rec.title}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            );
          })}
        </div>
      )}

      {tab === "plans" && (
        <div className="space-y-4">
          {plans.data?.master_version && (
            <div className="bg-white rounded shadow p-4 text-sm">
              <p>
                当前总规划 v{plans.data.master_version.version}（
                {plans.data.master_version.source}）
              </p>
              <pre className="mt-2 bg-slate-50 p-2 rounded overflow-auto text-xs">
                {JSON.stringify(plans.data.master_version.daily_time_budget_json, null, 2)}
              </pre>
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
            {papers.data?.map((p) => (
              <tr key={p.id} className="border-t">
                <td className="px-3 py-2">{p.subject_code}</td>
                <td className="px-3 py-2">{p.status}</td>
                <td className="px-3 py-2">{p.has_submission ? "是" : "否"}</td>
                <td className="px-3 py-2 space-x-2">
                  {p.status !== "locked" && p.status !== "replaced" && (
                    <button
                      type="button"
                      className="text-blue-600 underline"
                      onClick={() => lockMut.mutate(p.id)}
                    >
                      锁卷
                    </button>
                  )}
                  {p.status !== "replaced" && (
                    <button
                      type="button"
                      className="text-amber-700 underline"
                      onClick={() => replaceMut.mutate(p.id)}
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
          {wrong.data?.map((w) => (
            <li key={w.id} className="px-4 py-3">
              <span className="text-slate-500">{w.subject_code}</span> · {w.source_type}
              <div className="mt-1">{w.question_snapshot_json?.stem ?? "（无题干）"}</div>
            </li>
          ))}
          {wrong.data?.length === 0 && (
            <li className="px-4 py-6 text-center text-slate-500">暂无错题</li>
          )}
        </ul>
      )}
    </div>
  );
}
