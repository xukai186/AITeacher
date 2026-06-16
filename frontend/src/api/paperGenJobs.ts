import { api } from "./client";

export type PaperGenJobProgress = {
  done: number;
  total: number;
  message?: string | null;
};

export type PaperGenJobOut = {
  id: string;
  status: string;
  purpose: string;
  subject_code: string;
  paper_id: string;
  attempts: number;
  last_error: string | null;
  progress: PaperGenJobProgress | null;
  result_json: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export function getPaperGenJob(jobId: string) {
  return api<PaperGenJobOut>(`/student/paper-gen-jobs/${jobId}`);
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function waitForPaperGenJob(
  jobId: string,
  onProgress?: (job: PaperGenJobOut) => void,
): Promise<PaperGenJobOut> {
  for (;;) {
    const job = await getPaperGenJob(jobId);
    onProgress?.(job);
    if (job.status === "succeeded") return job;
    if (job.status === "failed") {
      throw new Error(job.last_error || "题目生成失败");
    }
    await sleep(1500);
  }
}
