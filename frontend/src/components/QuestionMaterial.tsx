type Props = {
  text: string;
};

export default function QuestionMaterial({ text }: Props) {
  return (
    <div className="rounded border border-slate-200 bg-slate-50 p-4 text-sm leading-7 whitespace-pre-wrap text-slate-800">
      {text}
    </div>
  );
}
