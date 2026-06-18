import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import PaperCenter from "../src/pages/student/PaperCenter";

function mockFetchPapers() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
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
      if (url.includes("/api/student/papers")) {
        return new Response(
          JSON.stringify([
            {
              id: "p1",
              paper_type: "placement",
              subject_code: "english",
              status: "submitted",
              title: "英语摸底",
              created_at: "2026-05-28T00:00:00Z",
              submission_id: null,
              total_score: 80,
            },
            {
              id: "s1",
              paper_type: "self_test",
              subject_code: "english",
              status: "graded",
              title: "english 自测",
              created_at: "2026-05-29T00:00:00Z",
              submission_id: "sub1",
              total_score: 72,
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
      <MemoryRouter>
        <PaperCenter />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("PaperCenter page", () => {
  it("renders merged placement and self test papers", async () => {
    mockFetchPapers();
    renderPage();

    expect(await screen.findByText("试卷中心")).toBeTruthy();
    expect(screen.getAllByText("摸底").length).toBeGreaterThan(0);
    expect(screen.getAllByText("自测").length).toBeGreaterThan(0);
    expect(screen.getByText("80 分")).toBeTruthy();
    expect(screen.getByText("72 分")).toBeTruthy();
    expect(screen.getByRole("link", { name: "查看结果" })).toBeTruthy();
  });
});
