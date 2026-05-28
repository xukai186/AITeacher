import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { fetchStudentMe } from "@/api/me";
import { generateSelfTest, listSelfTests } from "@/api/selfTests";

const SUBJECT_LABELS: Record<string, string> = {
  politics: "政治",
  english: "英语",
  math: "数学",
};

export default function SelfTests() {
  const navigate = useNavigate();
  const me = useQuery({ queryKey: ["student", "me"], queryFn: fetchStudentMe });
  const papers = useQuery({ queryKey: ["student", "self_tests"], queryFn: listSelfTests });

  const [open, setOpen] = useState(false);
  const [subject, setSubject] = useState<string>("");

  const subjectOptions = useMemo(() => me.data?.subject_codes ?? [], [me.data?.subject_codes]);

  const gen = useMutation({
    mutationFn: async () => generateSelfTest({ subject_code: subject }),
    onSuccess: (p) => navigate(`/student/self-tests/${p.id}`),
  });

  if (me.isLoading || papers.isLoading) return <p className="text-slate-500">加载中…</p>;
  if (me.error) return <p className="text-red-600">{(me.error as Error).message}</p>;
  if (papers.error) return <p className="text-red-600">{(papers.error as Error).message}</p>;

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <header className="flex justify-between items-baseline">
        <h1 className="text-xl font-semibold">自测</h1>
        <button
          className="px-3 py-1 rounded text-sm bg-slate-900 text-white disabled:bg-slate-200 disabled:text-slate-500"
          disabled={subjectOptions.length === 0}
          onClick={() => {
            setSubject(subjectOptions[0] ?? "");
            setOpen(true);
          }}
        >
          生成自测
        </button>
      </header>

      {open && (
        <div className="fixed inset-0 bg-black/30 flex items-center justify-center p-4">
          <div className="bg-white rounded shadow w-full max-w-sm p-4 space-y-3">
            <div className="font-semibold">选择科目</div>
            <select
              className="w-full border rounded px-3 py-2 text-sm"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
            >
              {subjectOptions.map((code) => (
                <option key={code} value={code}>
                  {SUBJECT_LABELS[code] ?? code}
                </option>
              ))}
            </select>
            <div className="flex justify-end gap-2">
              <button
                className="px-3 py-1 rounded border text-sm bg-white text-slate-700 border-slate-300"
                onClick={() => setOpen(false)}
              >
                取消
              </button>
              <button
                className="px-3 py-1 rounded text-sm bg-slate-900 text-white disabled:bg-slate-200 disabled:text-slate-500"
                disabled={!subject || gen.isPending}
                onClick={() => gen.mutate()}
              >
                生成并开始
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="bg-white shadow rounded p-4">
        {(papers.data ?? []).length === 0 ? (
          <p className="text-slate-500 text-sm">暂无自测记录。</p>
        ) : (
          <ul className="divide-y">
            {(papers.data ?? []).map((p) => (
              <li key={p.id} className="py-3 flex justify-between items-center">
                <div>
                  <div className="font-medium">{SUBJECT_LABELS[p.subject_code] ?? p.subject_code}</div>
                  <div className="text-xs text-slate-500">{p.status}</div>
                </div>
                <button
                  className="text-sm underline text-slate-700"
                  onClick={() => navigate(`/student/self-tests/${p.id}`)}
                >
                  打开
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

