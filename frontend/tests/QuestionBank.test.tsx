import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import QuestionBankPage from "../src/components/questionBank/QuestionBankPage";
import KnowledgeNodeSelect from "../src/components/questionBank/KnowledgeNodeSelect";
import { setToken } from "../src/api/client";

function renderPage(role: "org_admin" | "org_staff" = "org_staff") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <QuestionBankPage role={role} />
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
      if (url.includes("/org/question-bank/knowledge-nodes")) {
        return new Response(JSON.stringify([]), { status: 200 });
      }
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

  it("sends multi_choice with choice keys on create", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/org/question-bank/knowledge-nodes")) {
        return new Response(JSON.stringify([]), { status: 200 });
      }
      if (url.endsWith("/org/question-bank/enrich")) {
        return new Response(
          JSON.stringify({
            subject_code: "math",
            knowledge_node_id: null,
            difficulty: 2,
            analysis_text: "选 A 和 C。",
            q_type: "multi_choice",
          }),
          { status: 200 },
        );
      }
      if (url.endsWith("/org/question-bank") && init?.method === "POST") {
        return new Response(
          JSON.stringify({
            id: "q2",
            stem: "下列哪些为偶数？",
            subject_code: "math",
            q_type: "multi_choice",
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
    fireEvent.change(screen.getByLabelText("题型"), {
      target: { value: "multi_choice" },
    });
    fireEvent.change(screen.getByLabelText("题干"), {
      target: { value: "下列哪些为偶数？" },
    });
    fireEvent.change(screen.getByLabelText("选项（每行一个）"), {
      target: { value: "A. 2\nB. 3\nC. 4" },
    });
    fireEvent.change(screen.getByLabelText("答案"), {
      target: { value: "AC" },
    });
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
      stem: "下列哪些为偶数？",
      q_type: "multi_choice",
      answer_key: "AC",
      choices: [
        { key: "A", text: "2" },
        { key: "B", text: "3" },
        { key: "C", text: "4" },
      ],
    });
  });

  it("loads more questions with limit and offset", async () => {
    const page1 = Array.from({ length: 20 }, (_, index) => ({
      id: `q-${index + 1}`,
      scope: "org" as const,
      org_id: "org-1",
      subject_code: "english",
      knowledge_node_id: null,
      q_type: "single_choice",
      stem: `Question ${index + 1}`,
      choices: [{ key: "A", text: "One" }],
      answer_key: "A",
      analysis_text: null,
      difficulty: 2,
      source_type: "staff_manual",
      status: "active" as const,
      created_at: "2026-01-01T00:00:00Z",
    }));
    const page2 = [
      {
        id: "q-21",
        scope: "org" as const,
        org_id: "org-1",
        subject_code: "english",
        knowledge_node_id: null,
        q_type: "single_choice",
        stem: "Question 21",
        choices: [{ key: "A", text: "One" }],
        answer_key: "A",
        analysis_text: null,
        difficulty: 2,
        source_type: "staff_manual",
        status: "active" as const,
        created_at: "2026-01-01T00:00:00Z",
      },
    ];

    const fetchMock = vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/org/question-bank") && !url.includes("/enrich")) {
        const parsed = new URL(url, "http://localhost");
        const offset = Number(parsed.searchParams.get("offset") ?? "0");
        return new Response(JSON.stringify(offset === 0 ? page1 : page2), {
          status: 200,
        });
      }
      return new Response("not found", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();
    await waitFor(() => expect(screen.getByText("Question 1")).toBeTruthy());
    expect(screen.queryByText("Question 21")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "加载更多" }));

    await waitFor(() => expect(screen.getByText("Question 21")).toBeTruthy());
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("limit=20"),
      expect.anything(),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("offset=20"),
      expect.anything(),
    );
  });

  it("previews choice math while creating a question", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/org/question-bank") && !url.includes("/enrich")) {
        return new Response(JSON.stringify([]), { status: 200 });
      }
      return new Response("not found", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();
    fireEvent.click(screen.getByRole("button", { name: "新建题目" }));
    fireEvent.change(screen.getByLabelText("题型"), {
      target: { value: "single_choice" },
    });
    fireEvent.change(screen.getByLabelText("选项（每行一个）"), {
      target: {
        value: "A. $\\frac{1}{2}$\nB. $\\frac{1}{3}$",
      },
    });

    await waitFor(() =>
      expect(screen.getByText("选项预览")).toBeTruthy(),
    );
    expect(document.querySelectorAll(".katex").length).toBeGreaterThan(0);
  });

  it("renders math stems in the question list", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/org/question-bank") && !url.includes("/enrich")) {
        return new Response(
          JSON.stringify([
            {
              id: "q-math",
              scope: "org",
              org_id: "org-1",
              subject_code: "math",
              knowledge_node_id: null,
              q_type: "short_answer",
              stem: "$F(x,y,z) = z + \\ln z - \\int_{y}^{x}e^{-t^2}dt = 0$",
              choices: null,
              answer_key: "0",
              analysis_text: null,
              difficulty: 3,
              source_type: "ocr_import",
              status: "pending_review",
              created_at: "2026-01-01T00:00:00Z",
            },
          ]),
          { status: 200 },
        );
      }
      return new Response("not found", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();
    await waitFor(() =>
      expect(document.querySelector(".katex")).toBeTruthy(),
    );
    expect(document.body.textContent).not.toContain("$F(x,y,z)");
  });

  it("opens question detail with choices answer and analysis", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/org/question-bank") && !url.includes("/enrich")) {
        return new Response(
          JSON.stringify([
            {
              id: "q-detail",
              scope: "org",
              org_id: "org-1",
              subject_code: "math",
              knowledge_node_id: "node-1",
              knowledge_node_name: "极限 / 导数",
              q_type: "single_choice",
              stem: "求 $x$ 的值",
              choices: [
                { key: "A", text: "$1$" },
                { key: "B", text: "$2$" },
              ],
              answer_key: "A",
              analysis_text: "因为 $1+1=2$",
              difficulty: 2,
              source_type: "staff_manual",
              status: "active",
              created_at: "2026-01-01T00:00:00Z",
            },
          ]),
          { status: 200 },
        );
      }
      return new Response("not found", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "查看" })).toBeTruthy(),
    );

    fireEvent.click(screen.getByRole("button", { name: "查看" }));

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "题目详情" })).toBeTruthy(),
    );
    expect(screen.getByText("选项")).toBeTruthy();
    expect(screen.getByText("答案")).toBeTruthy();
    expect(screen.getByText("解析")).toBeTruthy();
    expect(screen.getByText("单选题")).toBeTruthy();
    expect(screen.getByText("极限 / 导数")).toBeTruthy();
    expect(document.querySelectorAll(".katex").length).toBeGreaterThan(0);
  });

  it("loads knowledge nodes for selected subject", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/org/question-bank/knowledge-nodes")) {
        return new Response(
          JSON.stringify([
            { id: "n1", name: "多元函数", parent_name: "高数" },
          ]),
          { status: 200 },
        );
      }
      return new Response("not found", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <KnowledgeNodeSelect subjectCode="math" value={null} onChange={() => {}} />
      </QueryClientProvider>,
    );

    await waitFor(() =>
      expect(screen.getByRole("option", { name: "高数 / 多元函数" })).toBeTruthy(),
    );
  });

  it("edits a pending question via PATCH", async () => {
    const item = {
      id: "q-edit",
      scope: "org" as const,
      org_id: "org-1",
      subject_code: "math",
      knowledge_node_id: null,
      q_type: "short_answer",
      stem: "Original stem",
      choices: null,
      answer_key: "1",
      analysis_text: null,
      difficulty: 2,
      source_type: "ocr_import",
      status: "pending_review" as const,
      created_at: "2026-01-01T00:00:00Z",
    };

    const fetchMock = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/org/question-bank/knowledge-nodes")) {
        return new Response(JSON.stringify([]), { status: 200 });
      }
      if (url.includes("/org/question-bank/q-edit") && init?.method === "PATCH") {
        return new Response(
          JSON.stringify({ ...item, stem: "Updated stem" }),
          { status: 200 },
        );
      }
      if (url.includes("/org/question-bank") && !url.includes("/enrich")) {
        return new Response(JSON.stringify([item]), { status: 200 });
      }
      return new Response("not found", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "编辑" })).toBeTruthy(),
    );

    fireEvent.click(screen.getByRole("button", { name: "编辑" }));
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "编辑题目" })).toBeTruthy(),
    );

    fireEvent.change(screen.getByLabelText("题干"), {
      target: { value: "Updated stem" },
    });
    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => {
      const patchCall = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).includes("/org/question-bank/q-edit") && init?.method === "PATCH",
      );
      expect(patchCall).toBeTruthy();
    });
    const patchCall = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url).includes("/org/question-bank/q-edit") && init?.method === "PATCH",
    );
    expect(JSON.parse(String(patchCall![1]?.body))).toMatchObject({
      stem: "Updated stem",
    });
  });

  it("create confirm can pick a knowledge node before submit", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/org/question-bank/knowledge-nodes")) {
        return new Response(
          JSON.stringify([
            { id: "n1", name: "多元函数", parent_name: "高数" },
          ]),
          { status: 200 },
        );
      }
      if (url.endsWith("/org/question-bank/enrich")) {
        return new Response(
          JSON.stringify({
            subject_code: "math",
            knowledge_node_id: null,
            difficulty: 3,
            analysis_text: "解析",
            q_type: "short_answer",
          }),
          { status: 200 },
        );
      }
      if (url.endsWith("/org/question-bank") && init?.method === "POST") {
        return new Response(
          JSON.stringify({
            id: "q1",
            stem: "题干",
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
    fireEvent.change(screen.getByLabelText("题干"), { target: { value: "题干" } });
    fireEvent.change(screen.getByLabelText("参考答案"), { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "智能补全" }));

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "确认题目信息" })).toBeTruthy(),
    );
    await waitFor(() =>
      expect(screen.getByRole("option", { name: "高数 / 多元函数" })).toBeTruthy(),
    );

    fireEvent.change(screen.getByRole("combobox", { name: "知识点" }), {
      target: { value: "n1" },
    });
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
      knowledge_node_id: "n1",
    });
  });

  it("soft-deletes a pending question after confirm", async () => {
    const item = {
      id: "q-del",
      scope: "org" as const,
      org_id: "org-1",
      subject_code: "math",
      knowledge_node_id: null,
      q_type: "short_answer",
      stem: "To delete",
      choices: null,
      answer_key: "1",
      analysis_text: null,
      difficulty: 2,
      source_type: "ocr_import",
      status: "pending_review" as const,
      created_at: "2026-01-01T00:00:00Z",
    };
    vi.spyOn(window, "confirm").mockReturnValue(true);

    const fetchMock = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/org/question-bank/knowledge-nodes")) {
        return new Response(JSON.stringify([]), { status: 200 });
      }
      if (url.includes("/org/question-bank/q-del/delete") && init?.method === "POST") {
        return new Response(JSON.stringify({ ...item, status: "deleted" }), { status: 200 });
      }
      if (url.includes("/org/question-bank") && !url.includes("/enrich")) {
        return new Response(JSON.stringify([item]), { status: 200 });
      }
      return new Response("not found", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "删除" })).toBeTruthy(),
    );
    fireEvent.click(screen.getByRole("button", { name: "删除" }));

    await waitFor(() => {
      expect(window.confirm).toHaveBeenCalledWith("删除后列表不再显示，确认删除？");
      const del = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).includes("/org/question-bank/q-del/delete") && init?.method === "POST",
      );
      expect(del).toBeTruthy();
    });
  });

  it("soft-deletes from the detail drawer after confirm", async () => {
    const item = {
      id: "q-del",
      scope: "org" as const,
      org_id: "org-1",
      subject_code: "math",
      knowledge_node_id: null,
      q_type: "short_answer",
      stem: "To delete",
      choices: null,
      answer_key: "1",
      analysis_text: null,
      difficulty: 2,
      source_type: "ocr_import",
      status: "pending_review" as const,
      created_at: "2026-01-01T00:00:00Z",
    };
    vi.spyOn(window, "confirm").mockReturnValue(true);

    const fetchMock = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/org/question-bank/knowledge-nodes")) {
        return new Response(JSON.stringify([]), { status: 200 });
      }
      if (url.includes("/org/question-bank/q-del/delete") && init?.method === "POST") {
        return new Response(JSON.stringify({ ...item, status: "deleted" }), { status: 200 });
      }
      if (url.includes("/org/question-bank") && !url.includes("/enrich")) {
        return new Response(JSON.stringify([item]), { status: 200 });
      }
      return new Response("not found", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "查看" })).toBeTruthy(),
    );
    fireEvent.click(screen.getByRole("button", { name: "查看" }));
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "题目详情" })).toBeTruthy(),
    );

    const deleteButtons = screen.getAllByRole("button", { name: "删除" });
    expect(deleteButtons.length).toBeGreaterThan(1);
    fireEvent.click(deleteButtons[deleteButtons.length - 1]);

    await waitFor(() => {
      expect(window.confirm).toHaveBeenCalledWith("删除后列表不再显示，确认删除？");
      const del = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).includes("/org/question-bank/q-del/delete") && init?.method === "POST",
      );
      expect(del).toBeTruthy();
    });
    expect(screen.queryByRole("heading", { name: "题目详情" })).toBeNull();
  });

  it("admin can filter list by scope and shows scope column", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/org/question-bank?") || url.endsWith("/org/question-bank")) {
        const u = new URL(url, "http://localhost");
        const scope = u.searchParams.get("scope");
        const items = [
          {
            id: "q-org",
            scope: "org",
            org_id: "org-1",
            subject_code: "english",
            knowledge_node_id: null,
            q_type: "short_answer",
            stem: "Org question",
            choices: null,
            answer_key: "a",
            analysis_text: null,
            difficulty: 2,
            source_type: "admin_manual",
            status: "active",
            created_at: "2026-08-01T00:00:00Z",
          },
          {
            id: "q-global",
            scope: "global",
            org_id: null,
            subject_code: "english",
            knowledge_node_id: null,
            q_type: "short_answer",
            stem: "Global question",
            choices: null,
            answer_key: "a",
            analysis_text: null,
            difficulty: 2,
            source_type: "admin_manual",
            status: "active",
            created_at: "2026-08-01T00:00:00Z",
          },
        ];
        const filtered =
          scope === "org"
            ? items.filter((i) => i.scope === "org")
            : scope === "global"
              ? items.filter((i) => i.scope === "global")
              : items;
        return new Response(JSON.stringify(filtered), { status: 200 });
      }
      return new Response("not found", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage("org_admin");
    await waitFor(() => expect(screen.getByText("Org question")).toBeTruthy());
    expect(screen.getByText("Global question")).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "范围" })).toBeTruthy();
    const table = screen.getByRole("table");
    expect(table).toHaveTextContent("本机构");
    expect(table).toHaveTextContent("平台公共");

    fireEvent.change(screen.getByLabelText("范围"), {
      target: { value: "global" },
    });

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("scope=global"),
        expect.anything(),
      ),
    );
    await waitFor(() => expect(screen.queryByText("Org question")).toBeNull());
    expect(screen.getByText("Global question")).toBeTruthy();
  });

  it("staff does not show scope filter", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/org/question-bank") && !url.includes("/enrich")) {
        return new Response(
          JSON.stringify([
            {
              id: "q-org",
              scope: "org",
              org_id: "org-1",
              subject_code: "english",
              knowledge_node_id: null,
              q_type: "short_answer",
              stem: "Staff org question",
              choices: null,
              answer_key: "a",
              analysis_text: null,
              difficulty: 2,
              source_type: "staff_manual",
              status: "active",
              created_at: "2026-08-01T00:00:00Z",
            },
          ]),
          { status: 200 },
        );
      }
      return new Response("not found", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage("org_staff");
    await waitFor(() => expect(screen.getByText("Staff org question")).toBeTruthy());
    expect(screen.queryByLabelText("范围")).toBeNull();
    expect(screen.queryByRole("columnheader", { name: "范围" })).toBeNull();
    const listCalls = fetchMock.mock.calls.filter(([url]) => {
      const u = String(url);
      return (
        u.includes("/org/question-bank") &&
        !u.includes("/enrich") &&
        !u.includes("/knowledge-nodes")
      );
    });
    expect(listCalls.every(([url]) => !String(url).includes("scope="))).toBe(true);
  });
});
