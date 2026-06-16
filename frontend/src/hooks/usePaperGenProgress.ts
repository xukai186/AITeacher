import { useEffect, useState } from "react";
import { PaperGenJobOut, waitForPaperGenJob } from "@/api/paperGenJobs";

export function usePaperGenProgress() {
  const [job, setJob] = useState<PaperGenJobOut | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    if (!running) {
      setJob(null);
      setError(null);
    }
  }, [running]);

  const run = async (jobId: string) => {
    setRunning(true);
    setError(null);
    try {
      const done = await waitForPaperGenJob(jobId, setJob);
      return done;
    } catch (err) {
      setError(err as Error);
      throw err;
    } finally {
      setRunning(false);
    }
  };

  const progressPct =
    job?.progress && job.progress.total > 0
      ? Math.min(100, Math.round((job.progress.done / job.progress.total) * 100))
      : null;

  return {
    job,
    error,
    running,
    progressPct,
    message: job?.progress?.message ?? (running ? "正在生成题目…" : null),
    run,
  };
}
