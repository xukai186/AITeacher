import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  confirmMasterPlan,
  fetchMasterPlan,
  rejectMasterPlan,
} from "@/api/masterPlan";
import {
  confirmRoadmap,
  fetchRoadmap,
  rejectRoadmap,
  type RoadmapMonth,
} from "@/api/roadmap";

const SUBJECT_LABELS: Record<string, string> = {
  politics: "政治",
  english: "英语",
  math: "数学",
};

export default function MasterPlanPage() {
  const qc = useQueryClient();
  const master = useQuery({
    queryKey: ["student", "master-plan"],
    queryFn: fetchMasterPlan,
  });
  const roadmap = useQuery({
    queryKey: ["student", "roadmap"],
    queryFn: fetchRoadmap,
  });

  const confirmMaster = useMutation({
    mutationFn: confirmMasterPlan,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["student", "master-plan"] }),
  });
  const rejectMaster = useMutation({
    mutationFn: rejectMasterPlan,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["student", "master-plan"] }),
  });
  const confirmRoad = useMutation({
    mutationFn: confirmRoadmap,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["student", "roadmap"] });
      qc.invalidateQueries({ queryKey: ["student", "master-plan"] });
    },
  });
  const rejectRoad = useMutation({
    mutationFn: rejectRoadmap,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["student", "roadmap"] }),
  });

  if (master.isLoading || roadmap.isLoading) {
    return <p className="text-slate-500">加载中…</p>;
  }
  if (master.error) {
    return <p className="text-red-600">{(master.error as Error).message}</p>;
  }

  const activeRoadmap = roadmap.data?.active_version;
  const pendingRoadmap = roadmap.data?.pending_version;
  const job = roadmap.data?.generation_job;
  const masterData = master.data;

  return (
    <div className="max-w-3xl space-y-6">
      <h1 className="text-xl font-semibold">总计划</h1>

      {job?.status === "running" || job?.status === "pending" ? (
        <div className="bg-blue-50 border border-blue-200 rounded p-3 text-sm text-blue-900">
          正在生成全年学习计划…
        </div>
      ) : null}
      {job?.status === "failed" ? (
        <div className="bg-red-50 border border-red-200 rounded p-3 text-sm text-red-800">
          全年计划生成失败：{job.error_message ?? "未知错误"}
        </div>
      ) : null}

      <section className="bg-white rounded shadow p-4 space-y-4">
        <h2 className="font-medium">全年路线图</h2>
        {pendingRoadmap ? (
          <div className="bg-amber-50 border border-amber-200 rounded p-3 space-y-2">
            <p className="text-sm text-amber-900">新的全年学习计划待确认</p>
            <RoadmapTimeline months={(pendingRoadmap.months_json?.months ?? []) as RoadmapMonth[]} />
            <div className="flex gap-2 items-center flex-wrap">
              <button
                type="button"
                className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm disabled:opacity-60"
                disabled={confirmRoad.isPending}
                onClick={() => confirmRoad.mutate()}
              >
                {confirmRoad.isPending ? "确认中…" : "确认全年计划"}
              </button>
              <button
                type="button"
                className="px-3 py-1.5 border rounded text-sm disabled:opacity-60"
                disabled={rejectRoad.isPending}
                onClick={() => rejectRoad.mutate()}
              >
                拒绝
              </button>
              {confirmRoad.error ? (
                <p className="text-sm text-red-600 w-full">
                  {(confirmRoad.error as Error).message}
                </p>
              ) : null}
            </div>
          </div>
        ) : null}
        {activeRoadmap ? (
          <div className="space-y-2">
            {activeRoadmap.summary_json?.text ? (
              <p className="text-sm text-slate-600">{activeRoadmap.summary_json.text}</p>
            ) : null}
            <RoadmapTimeline months={(activeRoadmap.months_json?.months ?? []) as RoadmapMonth[]} />
          </div>
        ) : (
          !pendingRoadmap && (
            <p className="text-sm text-slate-500">完成全部科目摸底后，系统将生成全年路线图。</p>
          )
        )}
      </section>

      {!masterData?.active_version ? (
        <p className="text-slate-500">确认全年路线图后，将生成本周执行计划。</p>
      ) : (
        <WeeklyExecutionSection
          data={masterData}
          confirmMut={confirmMaster}
          rejectMut={rejectMaster}
        />
      )}
    </div>
  );
}

function WeeklyExecutionSection({
  data,
  confirmMut,
  rejectMut,
}: {
  data: NonNullable<Awaited<ReturnType<typeof fetchMasterPlan>>>;
  confirmMut: ReturnType<typeof useMutation<unknown, Error, void>>;
  rejectMut: ReturnType<typeof useMutation<unknown, Error, void>>;
}) {
  const pct =
    data.budget_change_ratio != null ? Math.round(data.budget_change_ratio * 100) : null;

  return (
    <>
      <section className="bg-white rounded shadow p-4">
        <h2 className="font-medium mb-2">本周目标</h2>
        <p className="text-xs text-slate-500 mb-2">
          当前版本 v{data.active_version!.version}（{data.active_version!.source}）
        </p>
        {data.active_version!.weekly_goals_json?.length ? (
          <ul className="list-disc pl-5 text-sm space-y-2">
            {data.active_version!.weekly_goals_json.map(
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
        ) : (
          <p className="text-sm text-slate-500">暂无周目标</p>
        )}
      </section>

      <section className="bg-white rounded shadow p-4">
        <h2 className="font-medium mb-2">每日时间预算（已生效）</h2>
        <BudgetTable budget={data.active_version!.daily_time_budget_json} />
      </section>

      {data.pending_version ? (
        <section className="bg-amber-50 border border-amber-200 rounded p-4 space-y-3">
          <h2 className="font-medium text-amber-900">本周计划待确认</h2>
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
      ) : null}
    </>
  );
}

function RoadmapTimeline({ months }: { months: RoadmapMonth[] }) {
  if (!months.length) {
    return <p className="text-sm text-slate-500">暂无月份数据</p>;
  }
  return (
    <div className="space-y-4">
      {months.map((m) => (
        <div key={m.month} className="border-l-2 border-blue-200 pl-3">
          <p className="font-medium text-sm">
            {m.month} · {m.label}
          </p>
          {m.milestones?.length ? (
            <p className="text-xs text-slate-500 mt-1">里程碑：{m.milestones.join("；")}</p>
          ) : null}
          <div className="mt-2 space-y-2">
            {Object.entries(m.subjects ?? {}).map(([code, block]) => (
              <div key={code} className="text-sm bg-slate-50 rounded p-2">
                <p className="font-medium">{SUBJECT_LABELS[code] ?? code}</p>
                <p className="text-slate-600">{block.focus}</p>
                {block.syllabus_nodes?.length ? (
                  <p className="text-xs text-slate-500">考纲：{block.syllabus_nodes.join("、")}</p>
                ) : null}
                {block.weekly_hours_hint != null ? (
                  <p className="text-xs text-slate-500">建议约 {block.weekly_hours_hint} 小时/周</p>
                ) : null}
                {block.notes ? <p className="text-xs text-slate-500 mt-1">{block.notes}</p> : null}
              </div>
            ))}
          </div>
        </div>
      ))}
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
