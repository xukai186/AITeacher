import { useState } from "react";
import { postChat } from "@/api/chat";
import ChatComposer from "./ChatComposer";
import ChatMessageList, { type ChatMessage } from "./ChatMessageList";

export default function ChatPanel({
  agentType,
  subjectCode,
}: {
  agentType: "planner" | "subject";
  subjectCode?: string | null;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pending, setPending] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);

  async function handleSend(text: string) {
    if (pending) return;
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setPending(true);
    try {
      const resp = await postChat({
        agent_type: agentType,
        subject_code: subjectCode ?? null,
        message: text,
      });
      setSessionId(resp.session_id);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: resp.assistant_message,
          toolsUsed:
            resp.tools_used && resp.tools_used.length > 0 ? resp.tools_used : undefined,
        },
      ]);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex-1 overflow-auto rounded border border-slate-200 p-3">
        {messages.length === 0 ? (
          <p className="text-slate-500 text-sm">
            {sessionId ? "继续提问吧。" : "你好，我是你的 AI 老师。"}
          </p>
        ) : (
          <ChatMessageList messages={messages} />
        )}
      </div>
      <ChatComposer disabled={pending} onSend={handleSend} />
    </div>
  );
}

