import { api } from "./client";

export type ChatPostRequest = {
  agent_type: "planner" | "subject";
  subject_code?: string | null;
  message: string;
};

export type ChatPostResponse = {
  session_id: string;
  assistant_message: string;
  tools_used?: string[];
};

export type ChatHistoryMessage = {
  role: "user" | "assistant";
  content: string;
};

export type ChatHistoryResponse = {
  session_id: string | null;
  messages: ChatHistoryMessage[];
};

export function fetchChatHistory(
  agentType: "planner" | "subject",
  subjectCode?: string | null,
) {
  const params = new URLSearchParams({ agent_type: agentType });
  if (subjectCode) params.set("subject_code", subjectCode);
  return api<ChatHistoryResponse>(`/chat?${params.toString()}`);
}

export function postChat(body: ChatPostRequest) {
  return api<ChatPostResponse>("/chat", { method: "POST", body: JSON.stringify(body) });
}
