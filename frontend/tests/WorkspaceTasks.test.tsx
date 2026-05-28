import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import Workspace from "../src/pages/student/Workspace";

function mockFetchRouter() {
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
      if (url.includes("/api/student/tasks/today")) {
        return new Response(
          JSON.stringify({
            date: "2026-05-28",
            tasks: [
              {
                id: "t1",
                date: "2026-05-28",
                subject_code: "english",
                type: "study",
                ref_id: null,
                status: "pending",
                est_minutes: 60,
                title: "英语 学习任务",
                created_at: "2026-05-28T00:00:00Z",
              },
            ],
          }),
          { status: 200 },
        );
      }
      if (url.includes("/api/student/placement/start")) {
        return new Response(
          JSON.stringify({ subjects: [{ subject_code: "english", status: "ready", paper_id: "p1" }] }),
          { status: 200 },
        );
      }
      return new Response(JSON.stringify({ detail: "not found" }), { status: 404 });
    }),
  );
}

function renderWorkspace() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/student/workspace"]}>
        <Routes>
          <Route path="/student/workspace" element={<Workspace />} />
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

describe("Workspace tasks", () => {
  it("renders today task list", async () => {
    mockFetchRouter();
    renderWorkspace();
    await waitFor(() => expect(screen.getByText("英语 学习任务")).toBeTruthy());
  });
});

