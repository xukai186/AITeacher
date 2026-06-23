import MathText from "@/components/MathText";

export type QuestionChoice = { key: string; text: string };

export type AnswerableQuestion = {
  id: string;
  q_type: string;
  choices: QuestionChoice[];
};

type Props = {
  question: AnswerableQuestion;
  value: string;
  onChange: (value: string) => void;
};

export default function QuestionAnswerInput({ question, value, onChange }: Props) {
  const qType = question.q_type;

  if (qType === "fill_blank") {
    return (
      <input
        className="w-full border rounded px-3 py-2 text-sm"
        value={value}
        placeholder="请输入答案"
        onChange={(e) => onChange(e.target.value)}
      />
    );
  }

  if (qType === "short_answer" || qType === "essay") {
    return (
      <textarea
        className="w-full border rounded px-3 py-2 text-sm min-h-[120px]"
        value={value}
        placeholder="请输入作答内容"
        onChange={(e) => onChange(e.target.value)}
      />
    );
  }

  if (qType === "multi_choice") {
    const selected = new Set(value.split("").filter(Boolean));
    return (
      <div className="grid grid-cols-2 gap-2">
        {question.choices.map((c) => (
          <label key={c.key} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={selected.has(c.key)}
              onChange={(e) => {
                const next = new Set(selected);
                if (e.target.checked) next.add(c.key);
                else next.delete(c.key);
                onChange(Array.from(next).sort().join(""));
              }}
            />
            <span>
              {c.key}. <MathText text={c.text} />
            </span>
          </label>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 gap-2">
      {question.choices.map((c) => (
        <label key={c.key} className="flex items-center gap-2 text-sm">
          <input
            type="radio"
            name={question.id}
            value={c.key}
            checked={value === c.key}
            onChange={(e) => onChange(e.target.value)}
          />
          <span>
            {c.key}. <MathText text={c.text} />
          </span>
        </label>
      ))}
    </div>
  );
}
