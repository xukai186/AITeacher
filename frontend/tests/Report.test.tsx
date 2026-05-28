import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
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
            self_test_trend: [],
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
  });
});

