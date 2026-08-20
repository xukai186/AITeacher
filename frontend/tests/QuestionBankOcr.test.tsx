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

  it("segments one image into multiple drafts and batch submits", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/org/question-bank/upload-image")) {
        return new Response(
          JSON.stringify({ asset_id: "asset-sheet", storage_key: "k" }),
          { status: 201 },
        );
      }
      if (url.endsWith("/org/question-bank/ocr")) {
        expect(JSON.parse(String(init?.body))).toEqual({
          mode: "single_image_multi_question",
          asset_ids: ["asset-sheet"],
        });
        return new Response(
          JSON.stringify({
            mode: "segmented",
            questions: [
              {
                q_type: "single_choice",
                stem: "Q1",
                choices: [{ key: "A", text: "1" }],
                answer_key: "A",
              },
              {
                q_type: "short_answer",
                stem: "Q2",
                choices: null,
                answer_key: "x",
              },
            ],
          }),
          { status: 200 },
        );
      }
      if (url.endsWith("/org/question-bank/enrich")) {
        return new Response(
          JSON.stringify({
            subject_code: "english",
            knowledge_node_id: null,
            difficulty: 2,
            analysis_text: "analysis",
            q_type: null,
          }),
          { status: 200 },
        );
      }
      if (url.endsWith("/org/question-bank") && init?.method === "POST") {
        const body = JSON.parse(String(init?.body));
        return new Response(
          JSON.stringify({
            id: `q-${body.stem}`,
            stem: body.stem,
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
    fireEvent.click(screen.getByRole("button", { name: "一图多题" }));
    fireEvent.change(screen.getByLabelText("题目图片"), {
      target: {
        files: [new File(["img"], "sheet.png", { type: "image/png" })],
      },
    });
    fireEvent.click(screen.getByRole("button", { name: "开始识别" }));

    await waitFor(() => {
      expect(screen.getByDisplayValue("Q1")).toBeInTheDocument();
      expect(screen.getByDisplayValue("Q2")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "批量智能补全" }));
    await waitFor(() =>
      expect(screen.getAllByText("english").length).toBeGreaterThan(0),
    );

    fireEvent.click(screen.getByRole("button", { name: "批量提交" }));
    await waitFor(() => {
      const creates = fetchMock.mock.calls.filter(
        ([url, init]) =>
          String(url).endsWith("/org/question-bank") &&
          init?.method === "POST",
      );
      expect(creates).toHaveLength(2);
    });
  });

  it("shows raw OCR text and lets user manually add drafts", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/org/question-bank/upload-image")) {
        return new Response(
          JSON.stringify({ asset_id: "asset-raw", storage_key: "raw-key" }),
          { status: 201 },
        );
      }
      if (url.endsWith("/org/question-bank/ocr")) {
        return new Response(
          JSON.stringify({
            mode: "raw_text_fallback",
            raw_text: "第一题：请手工整理这段识别文本",
          }),
          { status: 200 },
        );
      }
      if (url.endsWith("/org/question-bank/enrich")) {
        return new Response(
          JSON.stringify({
            subject_code: "english",
            knowledge_node_id: null,
            difficulty: 2,
            analysis_text: "analysis",
            q_type: null,
          }),
          { status: 200 },
        );
      }
      if (url.endsWith("/org/question-bank") && init?.method === "POST") {
        return new Response(
          JSON.stringify({
            id: "q-manual-draft",
            stem: "整理后的题目",
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
      target: {
        files: [new File(["img"], "raw.png", { type: "image/png" })],
      },
    });
    fireEvent.click(screen.getByRole("button", { name: "开始识别" }));

    await waitFor(() =>
      expect(
        screen.getByDisplayValue("第一题：请手工整理这段识别文本"),
      ).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "新增题目" }));
    fireEvent.change(screen.getByLabelText("题干"), {
      target: { value: "整理后的题目" },
    });
    fireEvent.change(screen.getByLabelText("参考答案"), {
      target: { value: "答案" },
    });
    fireEvent.click(screen.getByRole("button", { name: "批量智能补全" }));
    await waitFor(() => expect(screen.getByText("english")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "批量提交" }));

    await waitFor(() => {
      const createCall = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).endsWith("/org/question-bank") &&
          init?.method === "POST",
      );
      expect(createCall).toBeTruthy();
      expect(JSON.parse(String(createCall![1]?.body))).toMatchObject({
        stem: "整理后的题目",
        source_type: "ocr_import",
        source_image_asset_id: "asset-raw",
      });
    });
  });
});
