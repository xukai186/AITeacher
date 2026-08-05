import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import QuestionBankPage from "../src/components/questionBank/QuestionBankPage";
import { setToken } from "../src/api/client";

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <QuestionBankPage role="org_staff" />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Question bank", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    setToken("test-token");
  });

  it("enriches a new question, confirms suggestions, then creates it", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/org/question-bank/enrich")) {
        return new Response(
          JSON.stringify({
            subject_code: "math",
            knowledge_node_id: null,
            difficulty: 3,
            analysis_text: "先移项，再求解。",
            q_type: "short_answer",
          }),
          { status: 200 },
        );
      }
      if (url.endsWith("/org/question-bank") && init?.method === "POST") {
        return new Response(
          JSON.stringify({
            id: "q1",
            stem: "解方程 x + 1 = 2",
            subject_code: "math",
            q_type: "short_answer",
            status: "active",
          }),
          { status: 201 },
        );
      }
      if (url.includes("/org/question-bank")) {
        return new Response(JSON.stringify([]), { status: 200 });
      }
      return new Response("not found", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "新建题目" }));
    fireEvent.change(screen.getByLabelText("题干"), {
      target: { value: "解方程 x + 1 = 2" },
    });
    fireEvent.change(screen.getByLabelText("参考答案"), {
      target: { value: "x = 1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "智能补全" }));

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "确认题目信息" })).toBeTruthy(),
    );
    expect(screen.getByLabelText("科目")).toHaveValue("math");
    expect(screen.getByLabelText("解析")).toHaveValue("先移项，再求解。");

    fireEvent.click(screen.getByRole("button", { name: "确认入库" }));

    await waitFor(() => {
      const createCall = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).endsWith("/org/question-bank") && init?.method === "POST",
      );
      expect(createCall).toBeTruthy();
    });
    const createCall = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url).endsWith("/org/question-bank") && init?.method === "POST",
    );
    expect(JSON.parse(String(createCall![1]?.body))).toMatchObject({
      stem: "解方程 x + 1 = 2",
      q_type: "short_answer",
      answer_key: "x = 1",
      subject_code: "math",
      difficulty: 3,
      analysis_text: "先移项，再求解。",
      source_type: "staff_manual",
    });
  });
});
