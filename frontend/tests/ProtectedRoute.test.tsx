import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import ProtectedRoute from "../src/components/ProtectedRoute";
import { AuthProvider } from "../src/auth/AuthContext";

function mockFetchMe(role: string) {
  localStorage.setItem("aiteacher_token", "tok");
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      new Response(
        JSON.stringify({ id: "1", org_id: "o", email: "x", role, name: "x" }),
        { status: 200 },
      ),
    ),
  );
}

function renderWith(allow: string[]) {
  return render(
    <MemoryRouter initialEntries={["/secret"]}>
      <AuthProvider>
        <Routes>
          <Route
            path="/secret"
            element={
              <ProtectedRoute allow={allow as any}>
                <div>secret content</div>
              </ProtectedRoute>
            }
          />
          <Route path="/login" element={<div>login page</div>} />
          <Route path="/forbidden" element={<div>forbidden page</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("ProtectedRoute", () => {
  it("renders content when role is allowed", async () => {
    mockFetchMe("org_admin");
    renderWith(["org_admin"]);
    await waitFor(() => screen.getByText("secret content"));
  });

  it("redirects to /forbidden when role mismatched", async () => {
    mockFetchMe("student");
    renderWith(["org_admin"]);
    await waitFor(() => screen.getByText("forbidden page"));
  });

  it("redirects anonymous to /login", async () => {
    renderWith(["org_admin"]);
    await waitFor(() => screen.getByText("login page"));
  });
});
