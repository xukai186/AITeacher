import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { getSelfTestSubmission } from "@/api/selfTests";

type PerQuestion = {
  question_id: string;
  seq: number;
  score: number;
  points: number;
  detail?: any;
};

export default function SelfTestResult() {
  const navigate = useNavigate();
  const { submissionId } = useParams();
  const id = submissionId ?? "";

  const grade = useQuery({
    queryKey: ["student", "self_tests", "submission", id],
    queryFn: () => getSelfTestSubmission(id),
    enabled: Boolean(id),
  });

  if (grade.isLoading) return <p className="text-slate-500">加载中…</p>;
  if (grade.error) return <p className="text-red-600">{(grade.error as Error).message}</p>;
  if (!grade.data) return null;

  const questions: PerQuestion[] = (grade.data.detail_json as any)?.questions ?? [];

  return (
    <div className="max-w-4xl mx-auto bg-white shadow rounded p-6 space-y-4">
      <header className="flex justify-between items-baseline">
        <h1 className="text-xl font-semibold">自测结果</h1>
        <button className="text-sm text-slate-600 underline" onClick={() => navigate("/student/self-tests")}>
          返回列表
        </button>
      </header>

      <div className="flex items-center justify-between border rounded p-4">
        <div className="text-sm text-slate-600">总分</div>
        <div className="text-2xl font-semibold">{grade.data.total_score}</div>
      </div>

      <div className="space-y-2">
        {questions.map((q) => (
          <div key={q.question_id} className="border rounded p-3 text-sm flex justify-between">
            <div>第 {q.seq} 题</div>
            <div className="text-slate-700">
              {q.score} / {q.points}
            </div>
          </div>
        ))}
      </div>

      <div className="flex justify-end gap-3 pt-2">
        <button
          className="px-4 py-2 rounded text-sm bg-white text-slate-700 border border-slate-300"
          onClick={() => navigate("/student/wrong-book")}
        >
          查看错题本
        </button>
      </div>
    </div>
  );
}

