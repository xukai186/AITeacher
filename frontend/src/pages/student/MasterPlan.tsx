import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  confirmMasterPlan,
  fetchMasterPlan,
  rejectMasterPlan,
} from "@/api/masterPlan";

export default function MasterPlanPage() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ["student", "master-plan"],
    queryFn: fetchMasterPlan,
  });

  const confirmMut = useMutation({
    mutationFn: confirmMasterPlan,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["student", "master-plan"] }),
  });

  const rejectMut = useMutation({
    mutationFn: rejectMasterPlan,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["student", "master-plan"] }),
  });

  if (isLoading) return <p className="text-slate-500">加载中…</p>;
  if (error) return <p className="text-red-600">{(error as Error).message}</p>;
  if (!data?.active_version) {
    return <p className="text-slate-500">暂无总规划，请先完成摸底测评。</p>;
  }

  const pct =
    data.budget_change_ratio != null
      ? Math.round(data.budget_change_ratio * 100)
      : null;

  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="text-xl font-semibold">总计划</h1>
      <p className="text-sm text-slate-600">
        当前版本 v{data.active_version.version}（{data.active_version.source}）
      </p>

      <section className="bg-white rounded shadow p-4">
        <h2 className="font-medium mb-2">本周目标</h2>
        {data.active_version.weekly_goals_json?.length ? (
          <ul className="list-disc pl-5 text-sm space-y-2">
            {data.active_version.weekly_goals_json.map((g: { title?: string; description?: string }, i: number) => (
              <li key={i}>
                <span className="font-medium">{g.title}</span>
                {g.description ? <span className="text-slate-600"> — {g.description}</span> : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-500">暂无周目标</p>
        )}
      </section>

      <section className="bg-white rounded shadow p-4">
        <h2 className="font-medium mb-2">每日时间预算（已生效）</h2>
        <BudgetTable budget={data.active_version.daily_time_budget_json} />
      </section>

      {data.pending_version && (
        <section className="bg-amber-50 border border-amber-200 rounded p-4 space-y-3">
          <h2 className="font-medium text-amber-900">待确认调整</h2>
          <p className="text-sm text-amber-800">
            总规划每日时长变化约 {pct ?? "—"}%，超过 15% 阈值，确认后才会替换当前计划。
          </p>
          <BudgetTable budget={data.pending_version.daily_time_budget_json} />
          <div className="flex gap-3">
            <button
              type="button"
              className="px-4 py-2 bg-blue-600 text-white rounded text-sm"
              disabled={confirmMut.isPending}
              onClick={() => confirmMut.mutate()}
            >
              确认生效
            </button>
            <button
              type="button"
              className="px-4 py-2 border border-slate-300 rounded text-sm"
              disabled={rejectMut.isPending}
              onClick={() => rejectMut.mutate()}
            >
              拒绝
            </button>
          </div>
        </section>
      )}
    </div>
  );
}

function BudgetTable({
  budget,
}: {
  budget: { date: string; minutes: number }[] | null;
}) {
  if (!budget?.length) return <p className="text-sm text-slate-500">无预算数据</p>;
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-slate-500">
          <th className="py-1">日期</th>
          <th className="py-1">分钟</th>
        </tr>
      </thead>
      <tbody>
        {budget.map((row) => (
          <tr key={row.date} className="border-t">
            <td className="py-1">{row.date}</td>
            <td className="py-1">{row.minutes}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
