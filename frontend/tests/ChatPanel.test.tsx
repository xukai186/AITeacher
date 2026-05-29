import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import ChatPanel from "../src/components/chat/ChatPanel";

beforeEach(() => {
  vi.restoreAllMocks();
});

function mockFetchOnce(body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify(body), { status: 200 })),
  );
}

describe("ChatPanel", () => {
  it("sends a message and renders assistant reply", async () => {
    mockFetchOnce({
      session_id: "s1",
      assistant_message: "hello",
      tools_used: ["get_subject_context"],
    });
    render(<ChatPanel agentType="subject" subjectCode="english" />);
    fireEvent.change(screen.getByPlaceholderText(/输入/), {
      target: { value: "hi" },
    });
    fireEvent.click(screen.getByRole("button", { name: /发送/ }));
    await waitFor(() => expect(screen.getByText("hello")).toBeTruthy());
    await waitFor(() => expect(screen.getByText(/已调用：get_subject_context/)).toBeTruthy());
  });
});

