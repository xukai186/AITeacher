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

export function postChat(body: ChatPostRequest) {
  return api<ChatPostResponse>("/chat", { method: "POST", body: JSON.stringify(body) });
}

