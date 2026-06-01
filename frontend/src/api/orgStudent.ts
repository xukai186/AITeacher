import { api } from "./client";
import type { ReportOverviewOut } from "./report";

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
  subject_versions: {
    id: string;
    subject_code: string;
    version: number;
    source: string;
    phases_json: unknown[] | null;
    created_at: string;
  }[];
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
