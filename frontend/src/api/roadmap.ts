import { api } from "./client";

export type RoadmapMonth = {
  month: string;
  label?: string;
  subjects?: Record<
    string,
    {
      focus?: string;
      syllabus_nodes?: string[];
      weekly_hours_hint?: number;
      notes?: string;
    }
  >;
  milestones?: string[];
};

export type StudyRoadmapVersion = {
  id: string;
  version: number;
  source: string;
  start_date: string;
  end_date: string;
  summary_json?: { text?: string } | null;
  months_json: { months?: RoadmapMonth[] };
};

export type StudyRoadmapState = {
  roadmap_id: string | null;
  status: string | null;
  active_version: StudyRoadmapVersion | null;
  pending_version: StudyRoadmapVersion | null;
  generation_job?: {
    id: string;
    status: string;
    error_message?: string | null;
  } | null;
};

export function fetchRoadmap() {
  return api<StudyRoadmapState>("/student/roadmap");
}

export function confirmRoadmap() {
  return api<{ active_version: StudyRoadmapVersion; message: string }>(
    "/student/roadmap/confirm",
    { method: "POST" },
  );
}

export function rejectRoadmap() {
  return api<void>("/student/roadmap/reject", { method: "POST" });
}
