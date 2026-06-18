import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { fetchStudentMe } from "@/api/me";
import { listStudentPapers, type StudentPaperSummary } from "@/api/papers";
import { generateSelfTest } from "@/api/selfTests";

const SUBJECT_LABELS: Record<string, string> = {
  politics: "政治",
  english: "英语",
  math: "数学",
};

const TYPE_LABELS: Record<StudentPaperSummary["paper_type"], string> = {
  placement: "摸底",
  self_test: "自测",
};

const STATUS_LABELS: Record<string, string> = {
  generating: "生成中",
  ready: "待作答",
  submitted: "已提交",
  graded: "已批改",
  failed: "生成失败",
  locked: "已锁卷",
  replaced: "已换卷",
};

function subjectLabel(code: string) {
  return SUBJECT_LABELS[code] ?? code;
}

function paperAction(paper: StudentPaperSummary): { label: string; to: string } {
  if (paper.paper_type === "placement") {
    return {
      label: paper.status === "submitted" ? "查看" : "继续作答",
      to: `/student/placement/${paper.id}`,
    };
  }
  if (paper.submission_id && paper.status === "graded") {
    return {
      label: "查看结果",
      to: `/student/self-tests/result/${paper.submission_id}`,
    };
  }
  return {
    label: "继续作答",
    to: `/student/self-tests/${paper.id}`,
  };
}

export default function PaperCenter() {
  const navigate = useNavigate();
  const me = useQuery({ queryKey: ["student", "me"], queryFn: fetchStudentMe });

  const [subject, setSubject] = useState("");
  const [paperType, setPaperType] = useState<"" | "placement" | "self_test">("");
  const [status, setStatus] = useState("");
  const [openGen, setOpenGen] = useState(false);
  const [genSubject, setGenSubject] = useState("");

  const subjectOptions = useMemo(() => me.data?.subject_codes ?? [], [me.data?.subject_codes]);

  const papers = useQuery({
    queryKey: ["student", "papers", subject, paperType, status],
    queryFn: () =>
      listStudentPapers({
        subject_code: subject || undefined,
        paper_type: paperType || undefined,
        status: status || undefined,
      }),
    enabled: Boolean(me.data),
  });

  const gen = useMutation({
    mutationFn: async () => generateSelfTest({ subject_code: genSubject }),
    onSuccess: (p) => navigate(`/student/self-tests/${p.id}`),
  });

  if (me.isLoading || papers.isLoading) return <p className="text-slate-500">加载中…</p>;
  if (me.error) return <p className="text-red-600">{(me.error as Error).message}</p>;
  if (papers.error) return <p className="text-red-600">{(papers.error as Error).message}</p>;

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <header className="flex justify-between items-baseline gap-3">
        <h1 className="text-xl font-semibold">试卷中心</h1>
        <button
          type="button"
          className="px-3 py-1 rounded text-sm bg-slate-900 text-white disabled:bg-slate-200 disabled:text-slate-500"
          disabled={subjectOptions.length === 0}
          onClick={() => {
            setGenSubject(subjectOptions[0] ?? "");
            setOpenGen(true);
          }}
        >
          生成自测
        </button>
      </header>

      <div className="bg-white shadow rounded p-4 flex flex-wrap gap-3 items-end text-sm">
        <label className="space-y-1">
          <span className="text-slate-600">科目</span>
          <select
            className="block border rounded px-2 py-1"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
          >
            <option value="">全部</option>
            {subjectOptions.map((code) => (
              <option key={code} value={code}>
                {subjectLabel(code)}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1">
          <span className="text-slate-600">类型</span>
          <select
            className="block border rounded px-2 py-1"
            value={paperType}
            onChange={(e) => setPaperType(e.target.value as typeof paperType)}
          >
            <option value="">全部</option>
            <option value="placement">摸底</option>
            <option value="self_test">自测</option>
          </select>
        </label>
        <label className="space-y-1">
          <span className="text-slate-600">状态</span>
          <select
            className="block border rounded px-2 py-1"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">全部</option>
            <option value="generating">生成中</option>
            <option value="ready">待作答</option>
            <option value="submitted">已提交</option>
            <option value="graded">已批改</option>
            <option value="failed">生成失败</option>
          </select>
        </label>
      </div>

      {openGen && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center p-4">
          <div className="bg-white rounded shadow w-full max-w-sm p-4 space-y-3">
            <div className="font-semibold">选择科目</div>
            <select
              className="w-full border rounded px-3 py-2 text-sm"
              value={genSubject}
              onChange={(e) => setGenSubject(e.target.value)}
            >
              {subjectOptions.map((code) => (
                <option key={code} value={code}>
                  {subjectLabel(code)}
                </option>
              ))}
            </select>
            <div className="flex justify-end gap-2">
              <button
                type="button"
                className="px-3 py-1 rounded border text-sm"
                onClick={() => setOpenGen(false)}
              >
                取消
              </button>
              <button
                type="button"
                className="px-3 py-1 rounded text-sm bg-slate-900 text-white disabled:opacity-50"
                disabled={!genSubject || gen.isPending}
                onClick={() => gen.mutate()}
              >
                生成并开始
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="bg-white shadow rounded overflow-hidden">
        {(papers.data ?? []).length === 0 ? (
          <p className="p-6 text-slate-500 text-sm text-center">暂无试卷记录。</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-100 text-left">
              <tr>
                <th className="px-4 py-2">类型</th>
                <th className="px-4 py-2">科目</th>
                <th className="px-4 py-2">状态</th>
                <th className="px-4 py-2">得分</th>
                <th className="px-4 py-2">时间</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {(papers.data ?? []).map((paper) => {
                const action = paperAction(paper);
                return (
                  <tr key={`${paper.paper_type}-${paper.id}`} className="border-t">
                    <td className="px-4 py-2">{TYPE_LABELS[paper.paper_type]}</td>
                    <td className="px-4 py-2">{subjectLabel(paper.subject_code)}</td>
                    <td className="px-4 py-2">{STATUS_LABELS[paper.status] ?? paper.status}</td>
                    <td className="px-4 py-2">
                      {paper.total_score != null ? `${paper.total_score} 分` : "—"}
                    </td>
                    <td className="px-4 py-2 text-slate-500">
                      {new Date(paper.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-2">
                      <Link to={action.to} className="text-blue-600 hover:underline">
                        {action.label}
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
