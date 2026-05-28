import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import SelfTestResult from "../src/pages/student/SelfTestResult";

function mockFetchResult() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: any) => {
      const url = String(input);
      if (url.includes("/api/student/self-tests/submissions/s1")) {
        return new Response(
          JSON.stringify({
            submission_id: "s1",
            total_score: 3,
            detail_json: { questions: [{ question_id: "q1", seq: 1, score: 1, points: 1 }] },
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
      <MemoryRouter initialEntries={["/student/self-tests/result/s1"]}>
        <Routes>
          <Route path="/student/self-tests/result/:submissionId" element={<SelfTestResult />} />
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

describe("SelfTestResult page", () => {
  it("renders total score", async () => {
    mockFetchResult();
    renderPage();
    await waitFor(() => expect(screen.getByText("3")).toBeTruthy());
  });
});

