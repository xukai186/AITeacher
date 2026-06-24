import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  CetStatus,
  ExamMajor,
  MathMasteryLevel,
  MathTrack,
  StudentExamProfile,
  SubjectCode,
  UpsertStudentExamProfileInput,
  listExamMajorCategories,
  listExamMajorsByCategory,
} from "@/api/examProfile";

type WizardStep = 1 | 2 | 3 | 4 | 5;

type ExamProfileWizardProps = {
  studentId: string;
  title?: string;
  getExamProfile: (studentId: string) => Promise<StudentExamProfile | null>;
  saveExamProfile: (studentId: string, body: UpsertStudentExamProfileInput) => Promise<StudentExamProfile>;
  confirmExamProfile: (studentId: string) => Promise<StudentExamProfile>;
  onCompleted?: (profile: StudentExamProfile) => void;
};

const SUBJECTS: { code: SubjectCode; label: string }[] = [
  { code: "english", label: "英语" },
  { code: "math", label: "数学" },
  { code: "politics", label: "政治" },
];

const CET_STATUS_LABELS: Record<Exclude<CetStatus, null>, string> = {
  not_taken: "未考",
  cet4: "四级",
  cet6: "六级",
};

const MATH_LEVEL_LABELS: Record<Exclude<MathMasteryLevel, null>, string> = {
  zero: "零基础",
  basic: "一般",
  good: "较好",
  strong: "很好",
};

function normalizeSubjects(input: SubjectCode[]) {
  const out: SubjectCode[] = [];
  for (const s of input) {
    if (!out.includes(s)) out.push(s);
  }
  return out;
}

export default function ExamProfileWizard({
  studentId,
  title = "完善报考档案",
  getExamProfile,
  saveExamProfile,
  confirmExamProfile,
  onCompleted,
}: ExamProfileWizardProps) {
  const [step, setStep] = useState<WizardStep>(1);

  const [majorCategoryCode, setMajorCategoryCode] = useState("");
  const [majorCode, setMajorCode] = useState("");
  const [englishTrack, setEnglishTrack] = useState<"english_1" | "english_2">("english_1");
  const [mathTrack, setMathTrack] = useState<MathTrack>("math_1");
  const [subjectCodes, setSubjectCodes] = useState<SubjectCode[]>(["english", "math", "politics"]);
  const [cetStatus, setCetStatus] = useState<CetStatus>(null);
  const [cetScore, setCetScore] = useState<string>("");
  const [mathMasteryLevel, setMathMasteryLevel] = useState<MathMasteryLevel>(null);
  const [initDone, setInitDone] = useState(false);

  const categoriesQuery = useQuery({
    queryKey: ["exam-profile", "categories"],
    queryFn: listExamMajorCategories,
  });

  const majorsQuery = useQuery({
    queryKey: ["exam-profile", "majors", majorCategoryCode],
    queryFn: () => listExamMajorsByCategory(majorCategoryCode),
    enabled: !!majorCategoryCode,
  });

  const profileQuery = useQuery({
    queryKey: ["exam-profile", "student", studentId],
    queryFn: () => getExamProfile(studentId),
    enabled: !!studentId,
  });

  useEffect(() => {
    if (initDone) return;
    if (!profileQuery.data) return;
    const p = profileQuery.data;
    setMajorCategoryCode(p.major_category_code);
    setMajorCode(p.major_code);
    setEnglishTrack(p.english_track ?? "english_1");
    setMathTrack(p.math_track ?? "math_1");
    setSubjectCodes(normalizeSubjects(p.subject_codes));
    setCetStatus(p.cet_status);
    setCetScore(p.cet_score == null ? "" : String(p.cet_score));
    setMathMasteryLevel(p.math_mastery_level);
    setInitDone(true);
  }, [profileQuery.data, initDone]);

  const selectedMajor = useMemo<ExamMajor | null>(() => {
    if (!majorsQuery.data) return null;
    return majorsQuery.data.find((m) => m.code === majorCode) ?? null;
  }, [majorsQuery.data, majorCode]);

  useEffect(() => {
    if (!selectedMajor) return;
    setEnglishTrack(selectedMajor.default_english_track);
    setMathTrack(selectedMajor.default_math_track);
    setSubjectCodes(normalizeSubjects(selectedMajor.default_subject_codes));
  }, [selectedMajor?.code]); // intentional: reset only when major actually changes

  useEffect(() => {
    if (mathTrack === "none") {
      setSubjectCodes((prev) => prev.filter((s) => s !== "math"));
    }
  }, [mathTrack]);

  const saveAndConfirmMut = useMutation({
    mutationFn: async () => {
      const cetScoreNum = cetScore.trim() === "" ? null : Number(cetScore);
      const payload: UpsertStudentExamProfileInput = {
        major_category_code: majorCategoryCode,
        major_code: majorCode,
        english_track: englishTrack,
        math_track: mathTrack,
        subject_codes: normalizeSubjects(subjectCodes),
        cet_status: cetStatus,
        cet_score: Number.isNaN(cetScoreNum) ? null : cetScoreNum,
        math_mastery_level: mathMasteryLevel,
      };
      await saveExamProfile(studentId, payload);
      return confirmExamProfile(studentId);
    },
    onSuccess: (profile) => {
      onCompleted?.(profile);
    },
  });

  const stepReady =
    step === 1
      ? !!majorCategoryCode
      : step === 2
        ? !!majorCode
        : step === 3
          ? subjectCodes.length > 0 && (mathTrack !== "none" || !subjectCodes.includes("math"))
          : step === 4
            ? true
            : true;

  const goNext = () => {
    if (!stepReady || step === 5) return;
    setStep((prev) => (prev + 1) as WizardStep);
  };

  const goPrev = () => {
    if (step === 1) return;
    setStep((prev) => (prev - 1) as WizardStep);
  };

  const renderStep = () => {
    if (categoriesQuery.isLoading || profileQuery.isLoading) {
      return <p className="text-sm text-slate-500">加载中…</p>;
    }
    if (categoriesQuery.error || profileQuery.error) {
      return (
        <p className="text-sm text-red-600">
          {((categoriesQuery.error || profileQuery.error) as Error).message}
        </p>
      );
    }

    if (step === 1) {
      return (
        <div className="space-y-2">
          <label className="text-sm font-medium block" htmlFor="major-category">
            报考大类
          </label>
          <select
            id="major-category"
            className="w-full border rounded px-3 py-2 text-sm"
            value={majorCategoryCode}
            onChange={(e) => {
              setMajorCategoryCode(e.target.value);
              setMajorCode("");
            }}
          >
            <option value="">请选择大类</option>
            {categoriesQuery.data?.map((cat) => (
              <option key={cat.code} value={cat.code}>
                {cat.name}
              </option>
            ))}
          </select>
        </div>
      );
    }

    if (step === 2) {
      return (
        <div className="space-y-3">
          {majorsQuery.isLoading ? (
            <p className="text-sm text-slate-500">加载专业列表…</p>
          ) : majorsQuery.error ? (
            <p className="text-sm text-red-600">{(majorsQuery.error as Error).message}</p>
          ) : (
            <>
              <label className="text-sm font-medium block" htmlFor="major-code">
                具体专业
              </label>
              <select
                id="major-code"
                className="w-full border rounded px-3 py-2 text-sm"
                value={majorCode}
                onChange={(e) => setMajorCode(e.target.value)}
              >
                <option value="">请选择专业</option>
                {majorsQuery.data?.map((major) => (
                  <option key={major.code} value={major.code}>
                    {major.name}
                  </option>
                ))}
              </select>
            </>
          )}
          {selectedMajor && (
            <div className="rounded border bg-slate-50 p-3 text-sm space-y-1">
              <p className="font-medium">系统推荐</p>
              <p>英语卷种：{selectedMajor.default_english_track}</p>
              <p>数学卷种：{selectedMajor.default_math_track}</p>
              <p>科目：{selectedMajor.default_subject_codes.join(" / ")}</p>
            </div>
          )}
        </div>
      );
    }

    if (step === 3) {
      return (
        <div className="space-y-3">
          <details open className="border rounded">
            <summary className="cursor-pointer px-3 py-2 bg-slate-50 text-sm font-medium">
              覆盖系统推荐
            </summary>
            <div className="p-3 space-y-3">
              <div>
                <label className="text-sm font-medium block" htmlFor="english-track">
                  英语卷种
                </label>
                <select
                  id="english-track"
                  className="w-full border rounded px-3 py-2 text-sm"
                  value={englishTrack}
                  onChange={(e) => setEnglishTrack(e.target.value as "english_1" | "english_2")}
                >
                  <option value="english_1">english_1</option>
                  <option value="english_2">english_2</option>
                </select>
              </div>
              <div>
                <label className="text-sm font-medium block" htmlFor="math-track">
                  数学卷种
                </label>
                <select
                  id="math-track"
                  className="w-full border rounded px-3 py-2 text-sm"
                  value={mathTrack}
                  onChange={(e) => setMathTrack(e.target.value as MathTrack)}
                >
                  <option value="math_1">math_1</option>
                  <option value="math_2">math_2</option>
                  <option value="none">none（不考数学）</option>
                </select>
              </div>
              <fieldset className="space-y-2">
                <legend className="text-sm font-medium">开通科目</legend>
                {SUBJECTS.map((subject) => {
                  const disabled = subject.code === "math" && mathTrack === "none";
                  return (
                    <label key={subject.code} className="flex items-center gap-2 text-sm text-slate-700">
                      <input
                        type="checkbox"
                        checked={subjectCodes.includes(subject.code)}
                        disabled={disabled}
                        onChange={(e) => {
                          setSubjectCodes((prev) => {
                            if (e.target.checked) return normalizeSubjects([...prev, subject.code]);
                            return prev.filter((s) => s !== subject.code);
                          });
                        }}
                      />
                      {subject.label}
                    </label>
                  );
                })}
              </fieldset>
            </div>
          </details>
        </div>
      );
    }

    if (step === 4) {
      return (
        <div className="space-y-3">
          <div>
            <label className="text-sm font-medium block" htmlFor="cet-status">
              四六级状态（选填）
            </label>
            <select
              id="cet-status"
              className="w-full border rounded px-3 py-2 text-sm"
              value={cetStatus ?? ""}
              onChange={(e) => setCetStatus((e.target.value || null) as CetStatus)}
            >
              <option value="">未填写</option>
              <option value="not_taken">{CET_STATUS_LABELS.not_taken}</option>
              <option value="cet4">{CET_STATUS_LABELS.cet4}</option>
              <option value="cet6">{CET_STATUS_LABELS.cet6}</option>
            </select>
          </div>
          <div>
            <label className="text-sm font-medium block" htmlFor="cet-score">
              四六级分数（选填）
            </label>
            <input
              id="cet-score"
              type="number"
              min={0}
              max={750}
              className="w-full border rounded px-3 py-2 text-sm"
              placeholder="例如 460"
              value={cetScore}
              onChange={(e) => setCetScore(e.target.value)}
            />
          </div>
          <div>
            <label className="text-sm font-medium block" htmlFor="math-level">
              数学掌握（选填）
            </label>
            <select
              id="math-level"
              className="w-full border rounded px-3 py-2 text-sm"
              value={mathMasteryLevel ?? ""}
              onChange={(e) => setMathMasteryLevel((e.target.value || null) as MathMasteryLevel)}
            >
              <option value="">未填写</option>
              <option value="zero">{MATH_LEVEL_LABELS.zero}</option>
              <option value="basic">{MATH_LEVEL_LABELS.basic}</option>
              <option value="good">{MATH_LEVEL_LABELS.good}</option>
              <option value="strong">{MATH_LEVEL_LABELS.strong}</option>
            </select>
          </div>
        </div>
      );
    }

    return (
      <div className="space-y-2 text-sm">
        <div className="rounded border bg-slate-50 p-3 space-y-1">
          <p>
            <span className="text-slate-500">报考大类：</span>
            {categoriesQuery.data?.find((c) => c.code === majorCategoryCode)?.name ?? majorCategoryCode}
          </p>
          <p>
            <span className="text-slate-500">专业：</span>
            {selectedMajor?.name ?? majorCode}
          </p>
          <p>
            <span className="text-slate-500">英语卷种：</span>
            {englishTrack}
          </p>
          <p>
            <span className="text-slate-500">数学卷种：</span>
            {mathTrack}
          </p>
          <p>
            <span className="text-slate-500">科目：</span>
            {subjectCodes.join(" / ")}
          </p>
          <p>
            <span className="text-slate-500">四六级：</span>
            {cetStatus ? CET_STATUS_LABELS[cetStatus] : "未填写"}
            {cetScore ? `（${cetScore}）` : ""}
          </p>
          <p>
            <span className="text-slate-500">数学掌握：</span>
            {mathMasteryLevel ? MATH_LEVEL_LABELS[mathMasteryLevel] : "未填写"}
          </p>
        </div>
        <button
          type="button"
          className="px-4 py-2 rounded text-sm bg-slate-900 text-white disabled:bg-slate-200 disabled:text-slate-500"
          disabled={saveAndConfirmMut.isPending || !majorCode || subjectCodes.length === 0}
          onClick={() => saveAndConfirmMut.mutate()}
        >
          {saveAndConfirmMut.isPending ? "提交中…" : "保存并确认"}
        </button>
        {saveAndConfirmMut.error && (
          <p className="text-sm text-red-600">{(saveAndConfirmMut.error as Error).message}</p>
        )}
        {saveAndConfirmMut.isSuccess && (
          <p className="text-sm text-emerald-700">报考档案已确认完成。</p>
        )}
      </div>
    );
  };

  return (
    <section className="bg-white rounded shadow p-4 space-y-4">
      <header className="space-y-1">
        <h1 className="text-xl font-semibold">{title}</h1>
        <p className="text-sm text-slate-500">第 {step} / 5 步</p>
      </header>
      {renderStep()}
      <footer className="flex justify-between">
        <button
          type="button"
          className="px-3 py-1 rounded border text-sm bg-white text-slate-700 border-slate-300 disabled:opacity-50"
          disabled={step === 1 || saveAndConfirmMut.isPending}
          onClick={goPrev}
        >
          上一步
        </button>
        {step < 5 ? (
          <button
            type="button"
            className="px-3 py-1 rounded text-sm bg-slate-900 text-white disabled:bg-slate-200 disabled:text-slate-500"
            disabled={!stepReady}
            onClick={goNext}
          >
            下一步
          </button>
        ) : (
          <span className="text-xs text-slate-500 self-center">确认后将触发档案完成状态</span>
        )}
      </footer>
    </section>
  );
}
