import { api } from "./client";

export type QuestionBankRole = "org_admin" | "org_staff";
export type QuestionStatus = "pending_review" | "active" | "rejected" | "disabled";

export type QuestionBankItem = {
  id: string;
  scope: "org" | "global";
  org_id: string | null;
  subject_code: string;
  knowledge_node_id: string | null;
  q_type: string;
  stem: string;
  choices: Array<{ key?: string; text?: string; [key: string]: unknown }> | null;
  answer_key: string | null;
  analysis_text: string | null;
  difficulty: number | null;
  source_type: string;
  status: QuestionStatus;
  created_at: string;
};

export type QuestionDraft = {
  stem: string;
  q_type: string;
  choices?: Array<{ key: string; text: string }>;
  answer_key?: string;
};

export type Enrichment = {
  subject_code: string;
  knowledge_node_id: string | null;
  difficulty: number;
  analysis_text: string | null;
  q_type: string | null;
};

export type UploadedQuestionImage = {
  asset_id: string;
  storage_key: string;
};

export type RecognizedQuestion = QuestionDraft & {
  choices?: Array<{ key: string; text: string }>;
};

export type CreateQuestion = QuestionDraft & Enrichment & {
  scope: "org" | "global";
  source_type: "admin_manual" | "staff_manual" | "ocr_import";
  source_image_asset_id?: string;
};

export type QuestionFilters = {
  subject_code?: string;
  status?: string;
  pending?: boolean;
  limit?: number;
  offset?: number;
};

export function listQuestions(filters: QuestionFilters) {
  const params = new URLSearchParams();
  if (filters.subject_code) params.set("subject_code", filters.subject_code);
  if (filters.status) params.set("status", filters.status);
  if (filters.pending) params.set("pending", "true");
  if (filters.limit != null) params.set("limit", String(filters.limit));
  if (filters.offset != null) params.set("offset", String(filters.offset));
  const query = params.toString();
  return api<QuestionBankItem[]>(`/org/question-bank${query ? `?${query}` : ""}`);
}

export function enrichQuestion(body: QuestionDraft) {
  return api<Enrichment>("/org/question-bank/enrich", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function uploadQuestionImage(file: File) {
  const body = new FormData();
  body.append("file", file);
  return api<UploadedQuestionImage>("/org/question-bank/upload-image", {
    method: "POST",
    body,
  });
}

export function recognizeQuestion(assetId: string) {
  return api<RecognizedQuestion>("/org/question-bank/ocr", {
    method: "POST",
    body: JSON.stringify({ asset_id: assetId }),
  });
}

export function createQuestion(body: CreateQuestion) {
  return api<QuestionBankItem>("/org/question-bank", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function reviewQuestion(
  itemId: string,
  action: "approve" | "reject" | "disable",
) {
  return api<QuestionBankItem>(`/org/question-bank/${itemId}/${action}`, {
    method: "POST",
  });
}
