import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ChatPanel from "../src/components/chat/ChatPanel";

beforeEach(() => {
  vi.restoreAllMocks();
});

function mockChatFetch(options?: {
  history?: { session_id: string | null; messages: Array<{ role: string; content: string }> };
  post?: { session_id: string; assistant_message: string; tools_used?: string[] };
}) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method ?? "GET").toUpperCase();
      if (url.includes("/api/chat") && method === "GET") {
        return new Response(
          JSON.stringify(
            options?.history ?? { session_id: null, messages: [] },
          ),
          { status: 200 },
        );
      }
      return new Response(
        JSON.stringify(
          options?.post ?? {
            session_id: "s1",
            assistant_message: "hello",
            tools_used: ["get_subject_context"],
          },
        ),
        { status: 200 },
      );
    }),
  );
}

describe("ChatPanel", () => {
  it("loads persisted chat history on open", async () => {
    mockChatFetch({
      history: {
        session_id: "s1",
        messages: [
          { role: "user", content: "昨天的问题" },
          { role: "assistant", content: "昨天的回答" },
        ],
      },
    });
    render(<ChatPanel agentType="subject" subjectCode="english" />);
    expect(await screen.findByText("昨天的问题")).toBeTruthy();
    expect(screen.getByText("昨天的回答")).toBeTruthy();
  });

  it("sends a message and renders assistant reply", async () => {
    mockChatFetch({
      post: {
        session_id: "s1",
        assistant_message: "hello",
        tools_used: ["get_subject_context"],
      },
    });
    render(<ChatPanel agentType="subject" subjectCode="english" />);
    await screen.findByText("你好，我是你的 AI 老师。");
    fireEvent.change(screen.getByPlaceholderText(/输入/), {
      target: { value: "hi" },
    });
    fireEvent.click(screen.getByRole("button", { name: /发送/ }));
    await waitFor(() => expect(screen.getByText("hello")).toBeTruthy());
    await waitFor(() => expect(screen.getByText(/已调用：get_subject_context/)).toBeTruthy());
  });
});

