import { FormEvent, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  QuestionBankItem,
  updateQuestion,
} from "@/api/questionBank";
import MathText from "@/components/MathText";
import KnowledgeNodeSelect from "./KnowledgeNodeSelect";

const SUBJECTS = [
  ["politics", "政治"],
  ["english", "英语"],
  ["math", "数学"],
] as const;

const OBJECTIVE_TYPES = new Set(["single_choice", "multi_choice"]);

function parseChoices(value: string) {
  return value
    .split("\n")
    .map((line, index) => {
      const match = line.trim().match(/^([A-Za-z])[\s.、:：]+(.+)$/);
      return {
        key: match?.[1]?.toUpperCase() ?? String.fromCharCode(65 + index),
        text: match?.[2]?.trim() ?? line.trim(),
      };
    })
    .filter((choice) => choice.text);
}

function formatChoicesText(
  choices: QuestionBankItem["choices"],
): string {
  if (!choices?.length) return "";
  return choices
    .map((choice, index) => {
      const key = String(choice.key ?? "").trim() || String.fromCharCode(65 + index);
      const text = String(choice.text ?? "").trim();
      return text ? `${key}. ${text}` : "";
    })
    .filter(Boolean)
    .join("\n");
}

type Props = {
  item: QuestionBankItem;
  onClose: () => void;
  onSaved: () => void;
};

export default function QuestionBankEditForm({ item, onClose, onSaved }: Props) {
  const [stem, setStem] = useState(item.stem);
  const [qType, setQType] = useState(item.q_type);
  const [choicesText, setChoicesText] = useState(formatChoicesText(item.choices));
  const [answerKey, setAnswerKey] = useState(item.answer_key ?? "");
  const [subjectCode, setSubjectCode] = useState(item.subject_code);
  const [knowledgeNodeId, setKnowledgeNodeId] = useState<string | null>(
    item.knowledge_node_id,
  );
  const [difficulty, setDifficulty] = useState(item.difficulty ?? 3);
  const [analysisText, setAnalysisText] = useState(item.analysis_text ?? "");

  const updateMutation = useMutation({
    mutationFn: () =>
      updateQuestion(item.id, {
        stem: stem.trim(),
        q_type: qType,
        choices: OBJECTIVE_TYPES.has(qType)
          ? parseChoices(choicesText)
          : undefined,
        answer_key: answerKey.trim() || undefined,
        subject_code: subjectCode,
        knowledge_node_id: knowledgeNodeId,
        difficulty,
        analysis_text: analysisText.trim() || null,
      }),
    onSuccess: () => onSaved(),
  });

  const draftChoices = OBJECTIVE_TYPES.has(qType)
    ? parseChoices(choicesText)
    : [];

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    updateMutation.mutate();
  };

  const onSubjectChange = (nextSubject: string) => {
    setSubjectCode(nextSubject);
    if (knowledgeNodeId) {
      setKnowledgeNodeId(null);
    }
  };

  return (
    <div className="fixed inset-0 z-20 flex items-start justify-center overflow-auto bg-black/40 p-8">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-2xl rounded bg-white p-6 shadow-xl space-y-4"
      >
        <div className="flex items-start justify-between gap-4">
          <h2 className="text-lg font-semibold">编辑题目</h2>
          <button type="button" onClick={onClose} className="text-sm text-slate-600 underline">
            关闭
          </button>
        </div>

        <label className="block space-y-1">
          <span>题型</span>
          <select
            value={qType}
            onChange={(event) => setQType(event.target.value)}
            className="w-full rounded border px-3 py-2"
          >
            <option value="short_answer">简答题</option>
            <option value="fill_blank">填空题</option>
            <option value="single_choice">单选题</option>
            <option value="multi_choice">多选题</option>
          </select>
        </label>

        <label className="block space-y-1">
          <span>题干</span>
          <textarea
            value={stem}
            onChange={(event) => setStem(event.target.value)}
            required
            rows={4}
            className="w-full rounded border px-3 py-2"
            aria-label="题干"
          />
        </label>
        {stem.trim() ? (
          <div className="rounded border border-dashed bg-slate-50 p-3 text-sm">
            <div className="mb-1 text-xs text-slate-500">预览</div>
            <MathText text={stem} />
          </div>
        ) : null}

        {OBJECTIVE_TYPES.has(qType) && (
          <>
            <label className="block space-y-1">
              <span>选项（每行一个）</span>
              <textarea
                value={choicesText}
                onChange={(event) => setChoicesText(event.target.value)}
                required
                rows={5}
                className="w-full rounded border px-3 py-2"
                aria-label="选项（每行一个）"
              />
            </label>
            {draftChoices.length > 0 ? (
              <div className="rounded border border-dashed bg-slate-50 p-3 text-sm space-y-2">
                <div className="text-xs text-slate-500">选项预览</div>
                {draftChoices.map((choice) => (
                  <div key={choice.key}>
                    <span className="font-medium">{choice.key}.</span>{" "}
                    <MathText text={choice.text} />
                  </div>
                ))}
              </div>
            ) : null}
          </>
        )}

        <label className="block space-y-1">
          <span>{OBJECTIVE_TYPES.has(qType) ? "答案" : "参考答案"}</span>
          <input
            value={answerKey}
            onChange={(event) => setAnswerKey(event.target.value)}
            required
            className="w-full rounded border px-3 py-2"
            aria-label={OBJECTIVE_TYPES.has(qType) ? "答案" : "参考答案"}
          />
        </label>
        {answerKey.trim() ? (
          <div className="rounded border border-dashed bg-slate-50 p-3 text-sm">
            <div className="mb-1 text-xs text-slate-500">答案预览</div>
            <MathText text={answerKey} />
          </div>
        ) : null}

        <label className="block space-y-1">
          <span>科目</span>
          <select
            value={subjectCode}
            onChange={(event) => onSubjectChange(event.target.value)}
            className="w-full rounded border px-3 py-2"
            aria-label="科目"
          >
            {SUBJECTS.map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </label>

        <label className="block space-y-1">
          <span>知识点</span>
          <KnowledgeNodeSelect
            subjectCode={subjectCode}
            value={knowledgeNodeId}
            onChange={setKnowledgeNodeId}
          />
        </label>

        <label className="block space-y-1">
          <span>难度（1-5）</span>
          <input
            type="number"
            min={1}
            max={5}
            value={difficulty}
            onChange={(event) => setDifficulty(Number(event.target.value))}
            required
            className="w-full rounded border px-3 py-2"
            aria-label="难度（1-5）"
          />
        </label>

        <label className="block space-y-1">
          <span>解析</span>
          <textarea
            value={analysisText}
            onChange={(event) => setAnalysisText(event.target.value)}
            rows={4}
            className="w-full rounded border px-3 py-2"
            aria-label="解析"
          />
        </label>

        <div className="flex justify-end gap-3">
          <button type="button" onClick={onClose} className="px-4 py-2">
            取消
          </button>
          <button
            type="submit"
            disabled={updateMutation.isPending}
            className="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-50"
          >
            {updateMutation.isPending ? "保存中…" : "保存"}
          </button>
        </div>
        {updateMutation.error ? (
          <p role="alert" className="text-sm text-red-600">
            {(updateMutation.error as Error).message}
          </p>
        ) : null}
      </form>
    </div>
  );
}
