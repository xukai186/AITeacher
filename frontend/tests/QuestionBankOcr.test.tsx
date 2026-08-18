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

describe("Question bank OCR import", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    setToken("test-token");
  });

  it("uploads and recognizes an image before enriching and creating the question", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/org/question-bank/upload-image")) {
        expect(init?.body).toBeInstanceOf(FormData);
        return new Response(
          JSON.stringify({ asset_id: "asset-1", storage_key: "org-1/asset-1" }),
          { status: 201 },
        );
      }
      if (url.endsWith("/org/question-bank/ocr")) {
        expect(JSON.parse(String(init?.body))).toEqual({ asset_id: "asset-1" });
        return new Response(
          JSON.stringify({
            q_type: "multi_choice",
            stem: "下列哪些是质数？",
            choices: [
              { key: "A", text: "2" },
              { key: "B", text: "4" },
              { key: "C", text: "5" },
            ],
            answer_key: "AC",
          }),
          { status: 200 },
        );
      }
      if (url.endsWith("/org/question-bank/enrich")) {
        expect(JSON.parse(String(init?.body))).toMatchObject({
          q_type: "multi_choice",
          stem: "下列哪些是质数？",
          choices: [
            { key: "A", text: "2" },
            { key: "B", text: "4" },
            { key: "C", text: "5" },
          ],
          answer_key: "AC",
        });
        return new Response(
          JSON.stringify({
            subject_code: "math",
            knowledge_node_id: null,
            difficulty: 2,
            analysis_text: "2 和 5 只能被 1 和自身整除。",
            q_type: "multi_choice",
          }),
          { status: 200 },
        );
      }
      if (url.endsWith("/org/question-bank") && init?.method === "POST") {
        return new Response(
          JSON.stringify({
            id: "q-ocr",
            stem: "下列哪些是质数？",
            subject_code: "math",
            q_type: "multi_choice",
            status: "pending_review",
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
    fireEvent.click(screen.getByRole("button", { name: "图片识别添加" }));
    fireEvent.change(screen.getByLabelText("题目图片"), {
      target: { files: [new File(["image"], "question.png", { type: "image/png" })] },
    });
    fireEvent.click(screen.getByRole("button", { name: "开始识别" }));

    await waitFor(() =>
      expect(screen.getByLabelText("题干")).toHaveValue("下列哪些是质数？"),
    );
    expect(screen.getByLabelText("题型")).toHaveValue("multi_choice");
    expect(screen.getByLabelText("选项（每行一个）")).toHaveValue(
      "A. 2\nB. 4\nC. 5",
    );
    expect(screen.getByLabelText("答案")).toHaveValue("AC");

    fireEvent.click(screen.getByRole("button", { name: "智能补全" }));
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "确认题目信息" })).toBeTruthy(),
    );
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
      source_type: "ocr_import",
      source_image_asset_id: "asset-1",
      q_type: "multi_choice",
      choices: [
        { key: "A", text: "2" },
        { key: "B", text: "4" },
        { key: "C", text: "5" },
      ],
    });
  });

  it("disables enrich until OCR recognition succeeds", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/org/question-bank")) {
        return new Response(JSON.stringify([]), { status: 200 });
      }
      return new Response("not found", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "新建题目" }));
    fireEvent.click(screen.getByRole("button", { name: "图片识别添加" }));
    fireEvent.change(screen.getByLabelText("题干"), {
      target: { value: "手工填的题干" },
    });
    fireEvent.change(screen.getByLabelText("参考答案"), {
      target: { value: "1" },
    });

    const enrich = screen.getByRole("button", { name: "智能补全" });
    expect(enrich).toBeDisabled();
    expect(screen.getByText("请先完成图片识别")).toBeTruthy();
  });
});
