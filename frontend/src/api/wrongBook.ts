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

export function listWrongBook(subjectCode?: string) {
  const qs = subjectCode ? `?subject_code=${encodeURIComponent(subjectCode)}` : "";
  return api<WrongBookItemOut[]>(`/student/wrong-book${qs}`);
}

