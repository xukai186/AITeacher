import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import Report from "../src/pages/student/Report";

function mockFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: any) => {
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
      if (url.includes("/api/student/agent/apply-recommendations")) {
        return new Response(
          JSON.stringify({
            target_date: "2026-05-30",
            subject_code: "english",
            created: [],
            created_count: 2,
            skipped_count: 0,
            budget_minutes: 180,
            scheduled_minutes: 75,
            over_budget: false,
            warnings: [],
          }),
          { status: 200 },
        );
      }
      if (url.includes("/api/student/report/overview")) {
        return new Response(
          JSON.stringify({
            subject_code: "english",
            wrong_source_counts: { placement: 1, self_test: 2 },
            weak_nodes: [
              {
                knowledge_node_id: "n1",
                knowledge_node_name: "阅读理解",
                wrong_count: 3,
                total_count: 3,
              },
            ],
            self_test_trend: [
              {
                submission_id: "sub1",
                paper_id: "p1",
                subject_code: "english",
                total_score: 8,
                created_at: "2026-05-28T00:00:00Z",
              },
            ],
            recommendations: [
              {
                type: "review_wrong",
                title: "优先复习：阅读理解",
                detail: "先把错题重做一轮。",
                subject_code: "english",
                knowledge_node_id: "n1",
              },
            ],
            last_7d: {
              wrong_added: 3,
              wrong_source_counts: { self_test: 2, placement: 1 },
              self_test_count: 1,
              self_test_avg_score: 8,
            },
          }),
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
      <MemoryRouter initialEntries={["/student/report"]}>
        <Routes>
          <Route path="/student/report" element={<Report />} />
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

describe("Report page", () => {
  it("renders overview blocks", async () => {
    mockFetch();
    renderPage();
    await waitFor(() => expect(screen.getByText("学情报告")).toBeTruthy());
    await waitFor(() => expect(screen.getByText("错题来源")).toBeTruthy());
    await waitFor(() => expect(screen.getByText("阅读理解：3")).toBeTruthy());
    await waitFor(() => expect(screen.getByText("建议")).toBeTruthy());
    await waitFor(() => expect(screen.getByText("优先复习：阅读理解")).toBeTruthy());
    await waitFor(() => expect(screen.getByText("自测趋势")).toBeTruthy());
    await waitFor(() => expect(screen.getByText("8 分")).toBeTruthy());
    await waitFor(() => expect(screen.getByText("查看结果")).toBeTruthy());
    await waitFor(() => expect(screen.getByText("查看错题")).toBeTruthy());
    await waitFor(() => expect(screen.getByText("近 7 天")).toBeTruthy());
    await waitFor(() => expect(screen.getByText("新增错题：3")).toBeTruthy());
  });

  it("applies recommendations as tomorrow tasks", async () => {
    mockFetch();
    renderPage();
    await waitFor(() => expect(screen.getByText("生成明日任务")).toBeTruthy());
    fireEvent.click(screen.getByText("生成明日任务"));
    await waitFor(() => expect(screen.getByText(/已为 2026-05-30 生成 2 项任务/)).toBeTruthy());
  });
});

