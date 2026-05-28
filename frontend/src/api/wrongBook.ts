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
  created_at: string;
};

export function listWrongBook(params?: {
  subject_code?: string;
  source_type?: string;
  knowledge_node_id?: string;
  limit?: number;
  offset?: number;
}) {
  const qsParams = new URLSearchParams();
  if (params?.subject_code) qsParams.set("subject_code", params.subject_code);
  if (params?.source_type) qsParams.set("source_type", params.source_type);
  if (params?.knowledge_node_id) qsParams.set("knowledge_node_id", params.knowledge_node_id);
  if (typeof params?.limit === "number") qsParams.set("limit", String(params.limit));
  if (typeof params?.offset === "number") qsParams.set("offset", String(params.offset));
  const qs = qsParams.toString() ? `?${qsParams.toString()}` : "";
  return api<WrongBookItemOut[]>(`/student/wrong-book${qs}`);
}

