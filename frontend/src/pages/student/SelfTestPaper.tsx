import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import PaperGeneratingView from "@/components/PaperGeneratingView";
import { getSelfTestPaper, submitSelfTest, type SelfTestQuestionOut } from "@/api/selfTests";
import { useWaitForPaperGeneration } from "@/hooks/useWaitForPaperGeneration";

type AnswersState = Record<string, string>;

function initAnswers(questions: SelfTestQuestionOut[]): AnswersState {
  const out: AnswersState = {};
  for (const q of questions) out[q.id] = "";
  return out;
}

export default function SelfTestPaper() {
  const navigate = useNavigate();
  const { paperId } = useParams();
  const id = paperId ?? "";

  const paper = useQuery({
    queryKey: ["student", "self_tests", "paper", id],
    queryFn: () => getSelfTestPaper(id),
    enabled: Boolean(id),
  });

  const generation = useWaitForPaperGeneration(paper.data, paper.refetch);

  const questions = paper.data?.questions ?? [];
  const [answers, setAnswers] = useState<AnswersState>({});

  const canSubmit = useMemo(
    () => questions.length > 0 && questions.every((q) => (answers[q.id] ?? "").trim().length > 0),
    [answers, questions],
  );

  const submit = useMutation({
    mutationFn: async () =>
      submitSelfTest(id, {
        answers: questions.map((q) => ({
          question_id: q.id,
          content: (answers[q.id] ?? "").trim(),
        })),
      }),
    onSuccess: (out) => navigate(`/student/self-tests/result/${out.submission_id}`),
  });

  if (paper.isLoading) return <p className="text-slate-500">加载中…</p>;
  if (paper.error) return <p className="text-red-600">{(paper.error as Error).message}</p>;
  if (!paper.data) return null;

  if (paper.data.status === "failed") {
    return (
      <PaperGeneratingView
        title="自测做题"
        error={new Error("试卷生成失败，请返回列表重新生成")}
        onBack={() => navigate("/student/self-tests")}
      />
    );
  }

  if (generation.waiting || paper.data.status === "generating") {
    return (
      <PaperGeneratingView
        title="自测做题"
        message={generation.message}
        progressPct={generation.progressPct}
        error={generation.error}
        onBack={() => navigate("/student/self-tests")}
      />
    );
  }

  if (Object.keys(answers).length === 0 && questions.length > 0) {
    queueMicrotask(() => setAnswers(initAnswers(questions)));
  }

  return (
    <div className="max-w-4xl mx-auto bg-white shadow rounded p-6 space-y-4">
      <header className="flex justify-between items-baseline">
        <h1 className="text-xl font-semibold">自测做题</h1>
        <button className="text-sm text-slate-600 underline" onClick={() => navigate("/student/self-tests")}>
          返回列表
        </button>
      </header>

      <div className="space-y-4">
        {questions.map((q) => (
          <div key={q.id} className="border rounded p-4 space-y-2">
            <div className="font-medium">
              {q.seq}. {q.stem}
            </div>
            <div className="grid grid-cols-2 gap-2">
              {q.choices.map((c) => (
                <label key={c.key} className="flex items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name={q.id}
                    value={c.key}
                    checked={(answers[q.id] ?? "") === c.key}
                    onChange={(e) => setAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))}
                  />
                  <span>
                    {c.key}. {c.text}
                  </span>
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="flex justify-end gap-3 pt-2">
        <button
          disabled={!canSubmit || submit.isPending}
          className={`px-4 py-2 rounded text-sm ${
            !canSubmit || submit.isPending ? "bg-slate-200 text-slate-500" : "bg-slate-900 text-white"
          }`}
          onClick={() => submit.mutate()}
        >
          提交并查看结果
        </button>
      </div>
    </div>
  );
}
