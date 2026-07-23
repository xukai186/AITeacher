import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import WrongBook from "../src/pages/student/WrongBook";

function mockFetchWrongBook() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: any, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/api/student/me")) {
        return new Response(
          JSON.stringify({
            id: "u1",
            email: "s@example.com",
            name: "s",
            exam_year: 2027,
            subject_codes: ["english"],
          }),
          { status: 200 },
        );
      }
      if (url.includes("/api/chat") && init?.method === "POST") {
        return new Response(
          JSON.stringify({
            session_id: "sess1",
            assistant_message: "这是讲解：正确答案是 A。",
            tools_used: ["explain_wrong_book_item"],
          }),
          { status: 200 },
        );
      }
      if (url.includes("/api/student/wrong-book/w1/practice") && init?.method === "POST") {
        return new Response(
          JSON.stringify({
            is_correct: true,
            status: "active",
            consecutive_correct_count: 1,
            mastered: false,
          }),
          { status: 200 },
        );
      }
      if (url.includes("/api/student/wrong-book")) {
        const isPage2 = url.includes("offset=20");
        if (isPage2) {
          return new Response(JSON.stringify([]), { status: 200 });
        }
        return new Response(
          JSON.stringify([
            {
              id: "w1",
              subject_code: "english",
              knowledge_node_id: null,
              source_type: "self_test",
              source_id: "s1",
              question_snapshot_json: {
                stem: "题干",
                q_type: "single_choice",
                choices: [
                  { key: "A", text: "选项甲" },
                  { key: "B", text: "选项乙" },
                ],
              },
              answer_snapshot_json: { content: "B" },
              correct_snapshot_json: { answer_key: "A" },
              status: "active",
              wrong_count: 1,
              consecutive_correct_count: 0,
              mastered_at: null,
              last_practice_at: null,
              created_at: "2026-05-28T00:00:00Z",
            },
          ]),
          { status: 200 },
        );
      }
      return new Response(JSON.stringify({ detail: "not found" }), { status: 404 });
    }),
  );
}

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/student/wrong-book"]}>
        <Routes>
          <Route path="/student/wrong-book" element={<WrongBook />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("WrongBook page", () => {
  it("hides answers until practice is submitted", async () => {
    mockFetchWrongBook();
    renderPage();
    await waitFor(() => expect(screen.getByText("题干")).toBeTruthy());
    expect(screen.getAllByText("选项甲").length).toBeGreaterThan(0);
    expect(screen.getByText(/当时答案/)).toBeTruthy();
    expect(screen.getByText("B")).toBeTruthy();
    expect(screen.queryByText(/参考答案：/)).toBeNull();
    expect(screen.getByText(/参考答案已隐藏/)).toBeTruthy();
    expect(screen.getByText(/当时选择/)).toBeTruthy();

    const radios = screen.getAllByRole("radio");
    fireEvent.click(radios[0]);
    fireEvent.click(screen.getByRole("button", { name: /提交重做/ }));

    await waitFor(() => expect(screen.getByText(/参考答案：/)).toBeTruthy());
    expect(screen.getByText(/回答正确/)).toBeTruthy();
    expect(screen.getByText(/当时答案/)).toBeTruthy();
  });

  it("explains a wrong-book item inline via chat", async () => {
    const fetchMock = vi.fn(async (input: any, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/api/student/me")) {
        return new Response(
          JSON.stringify({
            id: "u1",
            email: "s@example.com",
            name: "s",
            exam_year: 2027,
            subject_codes: ["english"],
          }),
          { status: 200 },
        );
      }
      if (url.includes("/api/chat") && init?.method === "POST") {
        const body = JSON.parse(String(init.body));
        expect(body.agent_type).toBe("subject");
        expect(body.subject_code).toBe("english");
        expect(body.message).toContain("item_id=w1");
        expect(body.message).toContain("错题 1");
        return new Response(
          JSON.stringify({
            session_id: "sess1",
            assistant_message: "这是讲解：正确答案是 A。",
            tools_used: ["explain_wrong_book_item"],
          }),
          { status: 200 },
        );
      }
      if (url.includes("/api/student/wrong-book")) {
        return new Response(
          JSON.stringify([
            {
              id: "w1",
              subject_code: "english",
              knowledge_node_id: null,
              source_type: "self_test",
              source_id: "s1",
              question_snapshot_json: {
                stem: "题干",
                q_type: "single_choice",
                choices: [
                  { key: "A", text: "选项甲" },
                  { key: "B", text: "选项乙" },
                ],
              },
              answer_snapshot_json: { content: "B" },
              correct_snapshot_json: { answer_key: "A" },
              status: "active",
              wrong_count: 1,
              consecutive_correct_count: 0,
              mastered_at: null,
              last_practice_at: null,
              created_at: "2026-05-28T00:00:00Z",
            },
          ]),
          { status: 200 },
        );
      }
      return new Response(JSON.stringify({ detail: "not found" }), { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();
    await waitFor(() => expect(screen.getByText("题干")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /错题讲解/ }));
    await waitFor(() => expect(screen.getByText(/这是讲解：正确答案是 A/)).toBeTruthy());
  });

  it("shows explain error and allows retry", async () => {
    let chatCalls = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: any, init?: RequestInit) => {
        const url = String(input);
        if (url.includes("/api/student/me")) {
          return new Response(
            JSON.stringify({
              id: "u1",
              email: "s@example.com",
              name: "s",
              exam_year: 2027,
              subject_codes: ["english"],
            }),
            { status: 200 },
          );
        }
        if (url.includes("/api/chat") && init?.method === "POST") {
          chatCalls += 1;
          if (chatCalls === 1) {
            return new Response(JSON.stringify({ detail: "boom" }), { status: 500 });
          }
          return new Response(
            JSON.stringify({
              session_id: "sess2",
              assistant_message: "重试成功讲解",
              tools_used: ["explain_wrong_book_item"],
            }),
            { status: 200 },
          );
        }
        if (url.includes("/api/student/wrong-book")) {
          return new Response(
            JSON.stringify([
              {
                id: "w1",
                subject_code: "english",
                knowledge_node_id: null,
                source_type: "self_test",
                source_id: "s1",
                question_snapshot_json: {
                  stem: "题干",
                  q_type: "single_choice",
                  choices: [{ key: "A", text: "选项甲" }],
                },
                answer_snapshot_json: { content: "B" },
                correct_snapshot_json: { answer_key: "A" },
                status: "active",
                wrong_count: 1,
                consecutive_correct_count: 0,
                mastered_at: null,
                last_practice_at: null,
                created_at: "2026-05-28T00:00:00Z",
              },
            ]),
            { status: 200 },
          );
        }
        return new Response(JSON.stringify({ detail: "not found" }), { status: 404 });
      }),
    );

    renderPage();
    await waitFor(() => expect(screen.getByText("题干")).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /错题讲解/ }));
    await waitFor(() => expect(screen.getByText(/讲解失败|请求失败/)).toBeTruthy());
    fireEvent.click(screen.getByRole("button", { name: /重试/ }));
    await waitFor(() => expect(screen.getByText(/重试成功讲解/)).toBeTruthy());
  });
});
