import { api } from "./client";

export type PlacementStartOut = {
  subjects: { subject_code: string; status: string; paper_id: string | null }[];
  gen_job_id?: string | null;
};

export type PlacementPaperSummary = {
  id: string;
  subject_code: string;
  status: string;
  title: string;
  created_at: string;
};

export type PlacementChoiceOut = { key: string; text: string };

export type PlacementQuestionOut = {
  id: string;
  seq: number;
  q_type: string;
  stem: string;
  choices: PlacementChoiceOut[];
  answer_key: string | null;
};

export type PlacementPaperDetail = PlacementPaperSummary & {
  questions: PlacementQuestionOut[];
};

export type PlacementSubmitIn = {
  answers: { question_id: string; content: string }[];
};

export type PlacementSubmitOut = {
  paper_id: string;
  total_score: number;
  mastery_json: Record<string, number>;
};

export function startPlacement(body?: { subject_code?: string }) {
  return api<PlacementStartOut>("/student/placement/start", {
    method: "POST",
    body: JSON.stringify(body ?? {}),
  });
}

export function listPlacementPapers() {
  return api<PlacementPaperSummary[]>("/student/placement");
}

export function getPlacementPaper(paperId: string) {
  return api<PlacementPaperDetail>(`/student/placement/${paperId}`);
}

export function submitPlacement(paperId: string, payload: PlacementSubmitIn) {
  return api<PlacementSubmitOut>(`/student/placement/${paperId}/submit`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

