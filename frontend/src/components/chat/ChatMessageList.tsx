import ChatRichText from "./ChatRichText";

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  toolsUsed?: string[];
};

export default function ChatMessageList({
  messages,
}: {
  messages: ChatMessage[];
}) {
  return (
    <div className="flex flex-col gap-3">
      {messages.map((m, idx) => (
        <div
          key={idx}
          className={`max-w-[90%] rounded px-3 py-2 text-sm leading-relaxed ${
            m.role === "user"
              ? "self-end bg-slate-900 text-white"
              : "self-start bg-slate-100 text-slate-900"
          }`}
        >
          {m.role === "assistant" ? (
            <ChatRichText text={m.content} />
          ) : (
            <div className="whitespace-pre-wrap break-words">{m.content}</div>
          )}
          {m.role === "assistant" && m.toolsUsed && m.toolsUsed.length > 0 ? (
            <div className="mt-1 text-xs text-slate-500">
              已调用：{m.toolsUsed.join("、")}
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}
