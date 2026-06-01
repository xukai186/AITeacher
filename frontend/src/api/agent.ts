import { api } from "./client";

export type EnqueuePlanReviewOut = {
  job_id: string;
  created: boolean;
  status: string;
  subject_code: string;
  target_date: string;
  trigger: string;
};

export type PlanReviewJobOut = {
  id: string;
  status: string;
  subject_code: string;
  target_date: string;
  trigger: string;
  attempts: number;
  last_error: string | null;
  result_json: Record<string, unknown> | null;
  created_count: number | null;
  skipped_count: number | null;
  scheduled_minutes: number | null;
  budget_minutes: number | null;
  over_budget: boolean;
  warnings: string[];
};

export function enqueueApplyRecommendations(params: {
  subject_code: string;
  target_date?: string;
}) {
  const qs = new URLSearchParams({ subject_code: params.subject_code });
  if (params.target_date) qs.set("target_date", params.target_date);
  return api<EnqueuePlanReviewOut>(`/student/agent/apply-recommendations?${qs.toString()}`, {
    method: "POST",
  });
}

export function fetchPlanReviewJob(jobId: string) {
  return api<PlanReviewJobOut>(`/student/agent/plan-review-jobs/${jobId}`);
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function pollPlanReviewJob(
  jobId: string,
  opts?: { intervalMs?: number; timeoutMs?: number },
): Promise<PlanReviewJobOut> {
  const intervalMs = opts?.intervalMs ?? 500;
  const timeoutMs = opts?.timeoutMs ?? 30000;
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const job = await fetchPlanReviewJob(jobId);
    if (job.status === "succeeded" || job.status === "failed") {
      return job;
    }
    await sleep(intervalMs);
  }
  throw new Error("计划复审超时，请稍后在今日计划中查看");
}

/** @deprecated use enqueueApplyRecommendations + pollPlanReviewJob */
export const applyRecommendationsAsTasks = enqueueApplyRecommendations;
