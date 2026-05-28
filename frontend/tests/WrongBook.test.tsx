import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import WrongBook from "../src/pages/student/WrongBook";

function mockFetchWrongBook() {
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
              question_snapshot_json: { stem: "题干" },
              answer_snapshot_json: { content: "Z" },
              correct_snapshot_json: { answer_key: "A" },
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
  it("renders wrong item list", async () => {
    mockFetchWrongBook();
    renderPage();
    await waitFor(() => expect(screen.getByText("题干")).toBeTruthy());
  });
});

