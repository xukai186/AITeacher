import { api } from "./client";

export type SelfTestGenerateIn = { subject_code: string };

export type SelfTestPaperSummaryOut = {
  id: string;
  subject_code: string;
  status: string;
  created_at: string;
};

export type SelfTestChoiceOut = { key: string; text: string };

export type SelfTestQuestionOut = {
  id: string;
  seq: number;
  q_type: string;
  stem: string;
  choices: SelfTestChoiceOut[];
  points: number;
};

export type SelfTestPaperDetailOut = SelfTestPaperSummaryOut & {
  questions: SelfTestQuestionOut[];
};

export type SelfTestSubmitIn = {
  answers: { question_id: string; content: string }[];
};

export type SelfTestSubmitOut = {
  submission_id: string;
  total_score: number;
  detail_json: Record<string, unknown>;
};

export type SelfTestGradeOut = {
  submission_id: string;
  total_score: number;
  detail_json: Record<string, unknown>;
};

export function generateSelfTest(payload: SelfTestGenerateIn) {
  return api<SelfTestPaperSummaryOut>("/student/self-tests/generate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listSelfTests() {
  return api<SelfTestPaperSummaryOut[]>("/student/self-tests");
}

export function getSelfTestPaper(paperId: string) {
  return api<SelfTestPaperDetailOut>(`/student/self-tests/${paperId}`);
}

export function submitSelfTest(paperId: string, payload: SelfTestSubmitIn) {
  return api<SelfTestSubmitOut>(`/student/self-tests/${paperId}/submit`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getSelfTestSubmission(submissionId: string) {
  return api<SelfTestGradeOut>(`/student/self-tests/submissions/${submissionId}`);
}

