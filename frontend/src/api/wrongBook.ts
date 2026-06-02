import { api } from "./client";

export type WrongBookItemOut = {
  id: string;
  subject_code: string;
  knowledge_node_id: string | null;
  source_type: string;
  source_id: string | null;
  question_snapshot_json: Record<string, unknown>;
  answer_snapshot_json: Record<string, unknown>;
  correct_snapshot_json: Record<string, unknown>;
  status: string;
  wrong_count: number;
  consecutive_correct_count: number;
  mastered_at: string | null;
  last_practice_at: string | null;
  created_at: string;
};

export type WrongBookPracticeOut = {
  is_correct: boolean;
  status: string;
  consecutive_correct_count: number;
  mastered: boolean;
};

export function listWrongBook(params?: {
  subject_code?: string;
  source_type?: string;
  knowledge_node_id?: string;
  status?: string;
  limit?: number;
  offset?: number;
}) {
  const qsParams = new URLSearchParams();
  if (params?.subject_code) qsParams.set("subject_code", params.subject_code);
  if (params?.source_type) qsParams.set("source_type", params.source_type);
  if (params?.knowledge_node_id) qsParams.set("knowledge_node_id", params.knowledge_node_id);
  if (params?.status) qsParams.set("status", params.status);
  if (typeof params?.limit === "number") qsParams.set("limit", String(params.limit));
  if (typeof params?.offset === "number") qsParams.set("offset", String(params.offset));
  const qs = qsParams.toString() ? `?${qsParams.toString()}` : "";
  return api<WrongBookItemOut[]>(`/student/wrong-book${qs}`);
}

export function practiceWrongItem(itemId: string, content: string) {
  return api<WrongBookPracticeOut>(`/student/wrong-book/${itemId}/practice`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}

export function archiveWrongItem(itemId: string) {
  return api<WrongBookItemOut>(`/student/wrong-book/${itemId}/archive`, {
    method: "POST",
  });
}
