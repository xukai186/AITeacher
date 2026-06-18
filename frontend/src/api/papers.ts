import { api } from "./client";

export type StudentPaperSummary = {
  id: string;
  paper_type: "placement" | "self_test";
  subject_code: string;
  status: string;
  title: string;
  created_at: string;
  submission_id: string | null;
  total_score: number | null;
};

export type ListStudentPapersParams = {
  subject_code?: string;
  paper_type?: "placement" | "self_test";
  status?: string;
};

export function listStudentPapers(params?: ListStudentPapersParams) {
  const qs = new URLSearchParams();
  if (params?.subject_code) qs.set("subject_code", params.subject_code);
  if (params?.paper_type) qs.set("paper_type", params.paper_type);
  if (params?.status) qs.set("status", params.status);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return api<StudentPaperSummary[]>(`/student/papers${suffix}`);
}
