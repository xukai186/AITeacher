import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import SelfTests from "../src/pages/student/SelfTests";

function mockFetchSelfTests() {
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
      if (url.includes("/api/student/self-tests") && !url.includes("/generate")) {
        return new Response(JSON.stringify([]), { status: 200 });
      }
      if (url.includes("/api/student/self-tests/generate")) {
        return new Response(
          JSON.stringify({
            id: "p1",
            subject_code: "english",
            status: "ready",
            created_at: "2026-05-28T00:00:00Z",
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
      <MemoryRouter initialEntries={["/student/self-tests"]}>
        <Routes>
          <Route path="/student/self-tests" element={<SelfTests />} />
          <Route path="/student/self-tests/:paperId" element={<div>paper</div>} />
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

describe("SelfTests page", () => {
  it("opens subject picker and generates self test", async () => {
    mockFetchSelfTests();
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "生成自测" }));
    fireEvent.click(screen.getByRole("button", { name: "生成并开始" }));

    await waitFor(() => expect(screen.getByText("paper")).toBeTruthy());
  });
});

