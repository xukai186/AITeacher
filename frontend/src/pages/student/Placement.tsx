import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import PaperGeneratingView from "@/components/PaperGeneratingView";
import {
  getPlacementPaper,
  submitPlacement,
  type PlacementQuestionOut,
} from "@/api/placement";
import QuestionAnswerInput from "@/components/QuestionAnswerInput";
import MathText from "@/components/MathText";
import { useWaitForPaperGeneration } from "@/hooks/useWaitForPaperGeneration";

type AnswersState = Record<string, string>;

function defaultAnswers(questions: PlacementQuestionOut[]): AnswersState {
  const out: AnswersState = {};
  for (const q of questions) out[q.id] = "";
  return out;
}

export default function Placement() {
  const navigate = useNavigate();
  const { paperId } = useParams();
  const id = paperId ?? "";

  const paper = useQuery({
    queryKey: ["student", "placement", "paper", id],
    queryFn: () => getPlacementPaper(id),
    enabled: Boolean(id),
  });

  const generation = useWaitForPaperGeneration(paper.data, paper.refetch, id);

  const [answers, setAnswers] = useState<AnswersState>({});

  const questions = paper.data?.questions ?? [];
  const canSubmit = useMemo(
    () => questions.length > 0 && questions.every((q) => (answers[q.id] ?? "").trim().length > 0),
    [answers, questions],
  );

  const submit = useMutation({
    mutationFn: async () => {
      return submitPlacement(id, {
        answers: questions.map((q) => ({ question_id: q.id, content: (answers[q.id] ?? "").trim() })),
      });
    },
    onSuccess: () => navigate("/student/workspace"),
  });

  if (paper.isLoading) return <p className="text-slate-500">加载中…</p>;
  if (paper.error) return <p className="text-red-600">{(paper.error as Error).message}</p>;
  if (!paper.data) return null;

  if (paper.data.status === "failed") {
    return (
      <PaperGeneratingView
        title={`摸底测评：${paper.data.title}`}
        error={new Error("试卷生成失败，请返回工作台重新开始")}
        onBack={() => navigate("/student/workspace")}
      />
    );
  }

  if ((generation.waiting || paper.data.status === "generating") && questions.length === 0) {
    return (
      <PaperGeneratingView
        title={`摸底测评：${paper.data.title}`}
        message={generation.message}
        progressPct={generation.progressPct}
        error={generation.error}
        onBack={() => navigate("/student/workspace")}
      />
    );
  }

  if (Object.keys(answers).length === 0 && questions.length > 0) {
    queueMicrotask(() => setAnswers(defaultAnswers(questions)));
  }

  return (
    <div className="max-w-4xl mx-auto bg-white shadow rounded p-6 space-y-4">
      <header className="flex justify-between items-baseline">
        <h1 className="text-xl font-semibold">摸底测评：{paper.data.title}</h1>
        <button className="text-sm text-slate-600 underline" onClick={() => navigate("/student/workspace")}>
          返回工作台
        </button>
      </header>

      <div className="flex justify-end">
        <button
          className="px-3 py-1 rounded border text-sm bg-white text-slate-700 border-slate-300"
          onClick={() => {
            const next: AnswersState = {};
            for (const q of questions) {
              if (q.q_type === "short_answer" || q.q_type === "essay") {
                next[q.id] = "参考作答要点（开发占位）";
              } else {
                next[q.id] = q.answer_key ?? "";
              }
            }
            setAnswers(next);
          }}
        >
          一键填入正确答案（仅开发）
        </button>
      </div>

      <div className="space-y-4">
        {questions.map((q) => (
          <div key={q.id} className="border rounded p-4 space-y-2">
            <div className="font-medium">
              {q.seq}. [{q.q_type}] <MathText text={q.stem} />
              <span className="ml-2 text-xs text-slate-500">({q.points} 分)</span>
            </div>
            <QuestionAnswerInput
              question={q}
              value={answers[q.id] ?? ""}
              onChange={(val) => setAnswers((prev) => ({ ...prev, [q.id]: val }))}
            />
          </div>
        ))}
      </div>

      <div className="flex justify-end gap-3 pt-2 items-center">
        {submit.error && (
          <p className="text-sm text-red-600 mr-auto">提交失败：{(submit.error as Error).message}</p>
        )}
        <button
          disabled={!canSubmit || submit.isPending}
          className={`px-4 py-2 rounded text-sm ${
            !canSubmit || submit.isPending ? "bg-slate-200 text-slate-500" : "bg-slate-900 text-white"
          }`}
          onClick={() => submit.mutate()}
        >
          {submit.isPending ? "提交中…" : "提交"}
        </button>
      </div>
    </div>
  );
}
