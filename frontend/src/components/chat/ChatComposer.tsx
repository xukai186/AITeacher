import { useState } from "react";

export default function ChatComposer({
  placeholder,
  disabled,
  onSend,
}: {
  placeholder?: string;
  disabled?: boolean;
  onSend: (text: string) => void;
}) {
  const [text, setText] = useState("");

  function send() {
    const trimmed = text.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setText("");
  }

  return (
    <div className="flex gap-2">
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            send();
          }
        }}
        placeholder={placeholder ?? "输入你的问题…"}
        disabled={disabled}
        className="flex-1 rounded border border-slate-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-slate-900/20 disabled:bg-slate-50"
      />
      <button
        type="button"
        onClick={send}
        disabled={disabled}
        className="rounded bg-slate-900 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
      >
        发送
      </button>
    </div>
  );
}

