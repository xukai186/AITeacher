import type { Student } from "@/api/students";

export function StudentSignals({ student }: { student: Student }) {
  const badges: { label: string; className: string }[] = [];

  if ((student.wrong_added_7d ?? 0) > 0) {
    badges.push({
      label: `近7天错题 ${student.wrong_added_7d}`,
      className: "bg-slate-100 text-slate-700",
    });
  }
  if ((student.pending_task_count ?? 0) > 0) {
    badges.push({
      label: `待办 ${student.pending_task_count}`,
      className: "bg-blue-50 text-blue-800",
    });
  }
  if ((student.open_review_job_count ?? 0) > 0) {
    badges.push({
      label: `复审中 ${student.open_review_job_count}`,
      className: "bg-purple-50 text-purple-800",
    });
  }
  if (student.requires_plan_confirmation) {
    badges.push({
      label: "计划待确认",
      className: "bg-amber-50 text-amber-900",
    });
  }

  if (badges.length === 0) {
    return <span className="text-slate-400">—</span>;
  }

  return (
    <div className="flex flex-wrap gap-1">
      {badges.map((b) => (
        <span key={b.label} className={`text-xs px-2 py-0.5 rounded ${b.className}`}>
          {b.label}
        </span>
      ))}
    </div>
  );
}
