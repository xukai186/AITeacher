import { api } from "./client";
import type { ReportOverviewOut } from "./report";

export const SUBJECT_LABELS: Record<string, string> = {
  politics: "政治",
  english: "英语",
  math: "数学",
};

export type OrgPaperSummary = {
  id: string;
  subject_code: string;
  status: string;
  created_at: string;
  has_submission: boolean;
};

export type OrgStudentOverview = {
  student_id: string;
  name: string;
  email: string;
  subject_codes: string[];
  wrong_book_total: number;
  reports_by_subject: Record<string, ReportOverviewOut>;
  recent_papers: OrgPaperSummary[];
};

export type MasterPlanVersion = {
  id: string;
  version: number;
  source: string;
  weekly_goals_json: unknown[] | null;
  daily_time_budget_json: { date: string; minutes: number }[] | null;
  created_at: string;
};

export type OrgStudentPlans = {
  master_status: string | null;
  master_version: MasterPlanVersion | null;
  pending_version: MasterPlanVersion | null;
  requires_confirmation: boolean;
  subject_versions: {
    id: string;
    subject_code: string;
    version: number;
    source: string;
    phases_json: unknown[] | null;
    created_at: string;
  }[];
  plan_review_jobs: PlanReviewJob[];
};

export type PlanReviewJob = {
  id: string;
  status: string;
  subject_code: string;
  target_date: string;
  trigger: string;
  attempts: number;
  last_error: string | null;
  created_at: string;
  updated_at: string;
  created_count: number | null;
  skipped_count: number | null;
  scheduled_minutes: number | null;
  budget_minutes: number | null;
  over_budget: boolean;
  warnings: string[];
};

export type DailyTask = {
  id: string;
  date: string;
  subject_code: string;
  type: string;
  ref_id: string | null;
  status: string;
  est_minutes: number;
  title: string;
  created_at: string;
};

export type OrgStudentTasks = {
  date: string;
  tasks: DailyTask[];
};

export type WrongBookItem = {
  id: string;
  subject_code: string;
  source_type: string;
  question_snapshot_json: { stem?: string };
  created_at: string;
};

export function fetchOrgOverview(studentId: string) {
  return api<OrgStudentOverview>(`/org/students/${studentId}/overview`);
}

export function fetchOrgPlans(studentId: string) {
  return api<OrgStudentPlans>(`/org/students/${studentId}/plans`);
}

export function fetchOrgTasks(studentId: string, taskDate?: string) {
  const q = taskDate ? `?task_date=${encodeURIComponent(taskDate)}` : "";
  return api<OrgStudentTasks>(`/org/students/${studentId}/tasks${q}`);
}

export function patchMasterBudget(
  studentId: string,
  daily_time_budget_json: { date: string; minutes: number }[],
) {
  return api<MasterPlanVersion>(`/org/students/${studentId}/plans/master`, {
    method: "PATCH",
    body: JSON.stringify({ daily_time_budget_json }),
  });
}

export function fetchOrgPapers(studentId: string) {
  return api<OrgPaperSummary[]>(`/org/students/${studentId}/papers`);
}

export function lockPaper(studentId: string, paperId: string) {
  return api<{ paper_id: string; status: string }>(
    `/org/students/${studentId}/papers/${paperId}/lock`,
    { method: "POST" },
  );
}

export function replacePaper(studentId: string, paperId: string) {
  return api<{ paper_id: string; status: string; replaced_by_paper_id: string }>(
    `/org/students/${studentId}/papers/${paperId}/replace`,
    { method: "POST" },
  );
}

export function fetchOrgWrongBook(studentId: string, subjectCode?: string) {
  const q = subjectCode ? `?subject_code=${encodeURIComponent(subjectCode)}` : "";
  return api<WrongBookItem[]>(`/org/students/${studentId}/wrong-book${q}`);
}
