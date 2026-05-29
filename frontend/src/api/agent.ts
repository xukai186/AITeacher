import { api } from "./client";
import type { DailyTaskOut } from "./tasks";

export type ApplyRecommendationsOut = {
  target_date: string;
  subject_code: string;
  created: DailyTaskOut[];
  created_count: number;
  skipped_count: number;
  budget_minutes: number | null;
  scheduled_minutes: number;
  over_budget: boolean;
  warnings: string[];
};

export function applyRecommendationsAsTasks(params: {
  subject_code: string;
  target_date?: string;
}) {
  const qs = new URLSearchParams({ subject_code: params.subject_code });
  if (params.target_date) qs.set("target_date", params.target_date);
  return api<ApplyRecommendationsOut>(`/student/agent/apply-recommendations?${qs.toString()}`, {
    method: "POST",
  });
}
