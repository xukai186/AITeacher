type Props = {
  title: string;
  message?: string | null;
  progressPct?: number | null;
  error?: Error | null;
  onBack?: () => void;
};

export default function PaperGeneratingView({
  title,
  message,
  progressPct,
  error,
  onBack,
}: Props) {
  if (error) {
    return (
      <div className="max-w-4xl mx-auto bg-white shadow rounded p-6 space-y-4">
        <h1 className="text-xl font-semibold">{title}</h1>
        <p className="text-red-600">题目生成失败：{error.message}</p>
        {onBack && (
          <button className="text-sm text-slate-600 underline" onClick={onBack}>
            返回
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto bg-white shadow rounded p-6 space-y-4">
      <h1 className="text-xl font-semibold">{title}</h1>
      <p className="text-slate-600">{message ?? "正在生成题目…"}</p>
      {progressPct != null && (
        <div className="space-y-1">
          <div className="h-2 bg-slate-100 rounded overflow-hidden">
            <div
              className="h-full bg-slate-900 transition-all duration-300"
              style={{ width: `${progressPct}%` }}
            />
          </div>
          <p className="text-xs text-slate-500 text-right">{progressPct}%</p>
        </div>
      )}
    </div>
  );
}
