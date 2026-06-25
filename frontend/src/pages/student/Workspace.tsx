import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { fetchStudentMe } from "@/api/me";
import { startPlacement } from "@/api/placement";
import { fetchTodayTasks } from "@/api/tasks";
import { generateSelfTest } from "@/api/selfTests";
import { getStudentExamProfile } from "@/api/examProfile";
import ChatPanel from "@/components/chat/ChatPanel";
import { usePaperGenProgress } from "@/hooks/usePaperGenProgress";

const SUBJECT_LABELS: Record<string, string> = {
  politics: "政治",
  english: "英语",
  math: "数学",
};

const ENGLISH_TRACK_LABELS: Record<string, string> = {
  english_1: "英语一",
  english_2: "英语二",
};

const MATH_TRACK_LABELS: Record<string, string> = {
  math_1: "数学一",
  math_2: "数学二",
  none: "不考数学",
};

const CET_STATUS_LABELS: Record<string, string> = {
  not_taken: "未考",
  cet4: "四级",
  cet6: "六级",
};

const MATH_LEVEL_LABELS: Record<string, string> = {
  zero: "零基础",
  basic: "一般",
  good: "较好",
  strong: "很好",
};

export default function Workspace() {
  const navigate = useNavigate();
  const { data, isLoading, error } = useQuery({
    queryKey: ["student", "me"],
    queryFn: fetchStudentMe,
  });

  const todayTasks = useQuery({
    queryKey: ["student", "tasks", "today"],
    queryFn: fetchTodayTasks,
  });

  const examProfile = useQuery({
    queryKey: ["student", "exam-profile"],
    queryFn: getStudentExamProfile,
  });

  const paperGen = usePaperGenProgress();

  const start = useMutation({
    mutationFn: async () => {
      if (!current) throw new Error("请先选择科目");
      const out = await startPlacement({ subject_code: current });
      if (out.gen_job_id) {
        await paperGen.run(out.gen_job_id);
      }
      return out;
    },
    onSuccess: (out) => {
      const paperId = out.subjects[0]?.paper_id;
      if (paperId) navigate(`/student/placement/${paperId}`);
    },
  });

  const [selfTestOpen, setSelfTestOpen] = useState(false);
  const [selfTestSubject, setSelfTestSubject] = useState<string>("");
  const genSelfTest = useMutation({
    mutationFn: async () => {
      const paper = await generateSelfTest({ subject_code: selfTestSubject });
      if (paper.gen_job_id) {
        await paperGen.run(paper.gen_job_id);
      }
      return paper;
    },
    onSuccess: (p) => {
      setSelfTestOpen(false);
      navigate(`/student/self-tests/${p.id}`);
    },
  });

  const [activeSubject, setActiveSubject] = useState<string | null>(null);

  if (isLoading) return <p className="text-slate-500">加载中…</p>;
  if (error) return <p className="text-red-600">{(error as Error).message}</p>;
  if (!data) return null;

  const current = activeSubject ?? data.subject_codes[0] ?? null;
  const paperGenBusy = start.isPending || genSelfTest.isPending || paperGen.running;
  const profile = examProfile.data;
  const profileIncomplete =
    examProfile.isSuccess && (!profile || !profile.profile_completed_at);
  const profileComplete = Boolean(profile?.profile_completed_at);

  return (
    <div className="grid grid-cols-12 gap-4 h-full">
      <div className="col-span-7 bg-white shadow rounded p-6 space-y-4">
        <header className="flex justify-between items-baseline">
          <h1 className="text-xl font-semibold">今日计划</h1>
          <div className="text-sm text-slate-500">考试年份：{data.exam_year}</div>
        </header>

        {examProfile.isLoading && (
          <p className="text-sm text-slate-500">加载报考档案…</p>
        )}
        {profileComplete && profile && (
          <div className="rounded border bg-slate-50 p-3 text-sm space-y-1" data-testid="exam-profile-summary">
            <p className="font-medium text-slate-800">报考档案</p>
            <p>
              <span className="text-slate-500">专业：</span>
              {profile.major_name}
            </p>
            <p>
              <span className="text-slate-500">卷种：</span>
              {ENGLISH_TRACK_LABELS[profile.effective_english_track] ?? profile.effective_english_track}
              {" · "}
              {MATH_TRACK_LABELS[profile.effective_math_track] ?? profile.effective_math_track}
            </p>
            <p>
              <span className="text-slate-500">科目：</span>
              {profile.subject_codes.map((c) => SUBJECT_LABELS[c] ?? c).join("、")}
            </p>
            {(profile.cet_status || profile.math_mastery_level) && (
              <p>
                <span className="text-slate-500">基础水平：</span>
                {profile.cet_status
                  ? `${CET_STATUS_LABELS[profile.cet_status] ?? profile.cet_status}${profile.cet_score != null ? ` ${profile.cet_score} 分` : ""}`
                  : ""}
                {profile.cet_status && profile.math_mastery_level ? " · " : ""}
                {profile.math_mastery_level
                  ? `数学 ${MATH_LEVEL_LABELS[profile.math_mastery_level] ?? profile.math_mastery_level}`
                  : ""}
              </p>
            )}
          </div>
        )}

        <div className="flex justify-between items-center">
          <div className="text-sm text-slate-600">
            摸底测评（P3）
            {current ? ` · ${SUBJECT_LABELS[current] ?? current}` : ""}
          </div>
          <button
            className="px-3 py-1 rounded text-sm bg-slate-900 text-white disabled:bg-slate-200 disabled:text-slate-500"
            disabled={paperGenBusy || !current || profileIncomplete}
            onClick={() => start.mutate()}
          >
            {paperGenBusy ? "生成题目中…" : "开始摸底测评"}
          </button>
        </div>
        {profileIncomplete && (
          <div className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            请等待老师完善报考档案
          </div>
        )}
        {paperGenBusy && (
          <div className="text-sm text-slate-600 space-y-2">
            <p>{paperGen.message ?? "AI 正在生成题目，请勿重复点击。"}</p>
            {paperGen.progressPct !== null && (
              <div className="h-2 bg-slate-100 rounded overflow-hidden">
                <div
                  className="h-full bg-slate-900 transition-all duration-500"
                  style={{ width: `${paperGen.progressPct}%` }}
                />
              </div>
            )}
          </div>
        )}
        {(start.error || paperGen.error) && (
          <p className="text-sm text-red-600">
            {((start.error || paperGen.error) as Error).message}
          </p>
        )}

        <div className="flex justify-between items-center">
          <div className="text-sm text-slate-600">自测（P4）</div>
          <button
            className="px-3 py-1 rounded text-sm bg-slate-900 text-white disabled:bg-slate-200 disabled:text-slate-500"
            disabled={data.subject_codes.length === 0}
            onClick={() => {
              setSelfTestSubject(data.subject_codes[0] ?? "");
              setSelfTestOpen(true);
            }}
          >
            生成自测
          </button>
        </div>

        {selfTestOpen && (
          <div className="fixed inset-0 bg-black/30 flex items-center justify-center p-4">
            <div className="bg-white rounded shadow w-full max-w-sm p-4 space-y-3">
              <div className="font-semibold">选择科目</div>
              <select
                className="w-full border rounded px-3 py-2 text-sm"
                value={selfTestSubject}
                onChange={(e) => setSelfTestSubject(e.target.value)}
              >
                {data.subject_codes.map((code) => (
                  <option key={code} value={code}>
                    {SUBJECT_LABELS[code] ?? code}
                  </option>
                ))}
              </select>
              <div className="flex justify-end gap-2">
                <button
                  className="px-3 py-1 rounded border text-sm bg-white text-slate-700 border-slate-300"
                  onClick={() => setSelfTestOpen(false)}
                >
                  取消
                </button>
                <button
                  className="px-3 py-1 rounded text-sm bg-slate-900 text-white disabled:bg-slate-200 disabled:text-slate-500"
                  disabled={!selfTestSubject || paperGenBusy}
                  onClick={() => genSelfTest.mutate()}
                >
                  {paperGenBusy ? "生成中…" : "生成并开始"}
                </button>
              </div>
            </div>
          </div>
        )}

        <div className="flex gap-2 flex-wrap">
          {data.subject_codes.map((code) => (
            <button
              key={code}
              onClick={() => setActiveSubject(code)}
              className={`px-3 py-1 rounded border text-sm ${
                current === code
                  ? "bg-slate-900 text-white border-slate-900"
                  : "bg-white text-slate-700 border-slate-300"
              }`}
            >
              {SUBJECT_LABELS[code] ?? code}
            </button>
          ))}
          {data.subject_codes.length === 0 && (
            <p className="text-slate-500 text-sm">尚未开通科目，请联系管理员</p>
          )}
        </div>
        {todayTasks.isLoading ? (
          <p className="text-slate-500 text-sm">加载任务中…</p>
        ) : todayTasks.error ? (
          <p className="text-red-600 text-sm">{(todayTasks.error as Error).message}</p>
        ) : (
          <div className="space-y-2">
            {(todayTasks.data?.tasks ?? []).length === 0 ? (
              <p className="text-slate-500 text-sm">
                {current ? `${SUBJECT_LABELS[current] ?? current} 暂无今日任务。` : "暂无今日任务。"}
              </p>
            ) : (
              <ul className="space-y-2">
                {(todayTasks.data?.tasks ?? [])
                  .filter((t) => !current || t.subject_code === current)
                  .map((t) => (
                    <li key={t.id} className="border rounded p-3">
                      <div className="flex justify-between text-sm">
                        <div className="font-medium">{t.title}</div>
                        <div className="text-slate-500">{t.status}</div>
                      </div>
                      <div className="text-xs text-slate-500 mt-1">预计 {t.est_minutes} 分钟</div>
                    </li>
                  ))}
              </ul>
            )}
          </div>
        )}
      </div>
      <aside className="col-span-5 bg-white shadow rounded p-6">
        <h2 className="font-semibold mb-3">
          {current ? `${SUBJECT_LABELS[current] ?? current} AI 老师` : "AI 老师"}
        </h2>
        {current ? (
          <ChatPanel agentType="subject" subjectCode={current} />
        ) : (
          <p className="text-slate-500 text-sm">请先开通科目</p>
        )}
      </aside>
    </div>
  );
}
