export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
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
          {m.content}
        </div>
      ))}
    </div>
  );
}

