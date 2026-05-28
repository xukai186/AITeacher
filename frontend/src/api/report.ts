import { api } from "./client";

export type ReportWeakNodeOut = {
  knowledge_node_id: string | null;
  knowledge_node_name?: string | null;
  wrong_count: number;
  total_count: number;
};

export type ReportOverviewOut = {
  subject_code: string | null;
  wrong_source_counts: Record<string, number>;
  weak_nodes: ReportWeakNodeOut[];
  self_test_trend: Array<{
    submission_id: string;
    paper_id: string;
    subject_code: string;
    total_score: number;
    created_at: string;
  }>;
};

export function fetchStudentReportOverview(params?: {
  subject_code?: string;
  trend_limit?: number;
}) {
  const qs = new URLSearchParams();
  if (params?.subject_code) qs.set("subject_code", params.subject_code);
  if (typeof params?.trend_limit === "number") qs.set("trend_limit", String(params.trend_limit));
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return api<ReportOverviewOut>(`/student/report/overview${suffix}`);
}

