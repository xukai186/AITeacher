import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import Placement from "../src/pages/student/Placement";

function mockFetchPlacement() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: any, init?: any) => {
      const url = String(input);
      if (url.includes("/api/student/placement/p1") && (!init?.method || init.method === "GET")) {
        return new Response(
          JSON.stringify({
            id: "p1",
            subject_code: "english",
            status: "ready",
            title: "english",
            created_at: "2026-05-28T00:00:00Z",
            questions: [
              {
                id: "q1",
                seq: 1,
                q_type: "single_choice",
                stem: "题干",
                choices: [
                  { key: "A", text: "A" },
                  { key: "B", text: "B" },
                  { key: "C", text: "C" },
                  { key: "D", text: "D" },
                ],
                answer_key: "A",
              },
            ],
          }),
          { status: 200 },
        );
      }
      if (url.includes("/api/student/placement/p1/submit")) {
        return new Response(JSON.stringify({ paper_id: "p1", total_score: 1, mastery_json: {} }), {
          status: 200,
        });
      }
      return new Response(JSON.stringify({ detail: "not found" }), { status: 404 });
    }),
  );
}

function renderPlacement() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={["/student/placement/p1"]}>
        <Routes>
          <Route path="/student/placement/:paperId" element={<Placement />} />
          <Route path="/student/workspace" element={<div>workspace</div>} />
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

describe("Placement page", () => {
  it("fills correct answers and submits", async () => {
    mockFetchPlacement();
    renderPlacement();

    await waitFor(() => expect(screen.getByText(/摸底测评/)).toBeTruthy());

    fireEvent.click(screen.getByRole("button", { name: /一键填入正确答案/ }));
    fireEvent.click(screen.getByRole("button", { name: "提交" }));

    await waitFor(() => expect(screen.getByText("workspace")).toBeTruthy());
  });
});

