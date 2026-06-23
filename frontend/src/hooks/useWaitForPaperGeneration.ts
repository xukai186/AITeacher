import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { usePaperGenProgress } from "@/hooks/usePaperGenProgress";

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

type PaperLike = {
  status: string;
  gen_job_id?: string | null;
};

export function useWaitForPaperGeneration(
  paper: PaperLike | undefined,
  refetch: () => Promise<{ data?: PaperLike }>,
  paperId?: string,
) {
  const queryClient = useQueryClient();
  const paperGen = usePaperGenProgress();
  const waiting =
    paper?.status === "generating" || paperGen.running;

  useEffect(() => {
    if (!paper || paper.status !== "generating") return;

    let cancelled = false;

    (async () => {
      try {
        if (paper.gen_job_id) {
          await paperGen.run(paper.gen_job_id);
        } else {
          while (!cancelled) {
            await sleep(1500);
            const next = await refetch();
            if (next.data?.status !== "generating") break;
          }
        }
        if (!cancelled) {
          await refetch();
          if (paperId) {
            await queryClient.invalidateQueries({
              queryKey: ["student", "placement", "paper", paperId],
            });
          }
        }
      } catch {
        // error surfaced via paperGen.error
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once per generating paper
  }, [paper?.status, paper?.gen_job_id]);

  return {
    waiting,
    progressPct: paperGen.progressPct,
    message: paperGen.message ?? (waiting ? "正在生成题目…" : null),
    error: paperGen.error,
  };
}
