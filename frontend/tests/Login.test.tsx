import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import Login from "../src/pages/Login";
import { AuthProvider } from "../src/auth/AuthContext";

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

function mockFetch(responses: Record<string, { status: number; body: unknown }>) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo) => {
      const url = typeof input === "string" ? input : input.url;
      const match = Object.entries(responses).find(([key]) => url.endsWith(key));
      if (!match) throw new Error(`no mock for ${url}`);
      const [, { status, body }] = match;
      return new Response(JSON.stringify(body), { status });
    }),
  );
}

function renderLogin(initial = "/login") {
  return render(
    <MemoryRouter initialEntries={[initial]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/admin/students" element={<div>admin home</div>} />
          <Route path="/staff/students" element={<div>staff home</div>} />
          <Route path="/student/workspace" element={<div>student home</div>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("Login", () => {
  it("redirects admin to /admin/students after login", async () => {
    mockFetch({
      "/auth/login": { status: 200, body: { access_token: "t", token_type: "bearer" } },
      "/me": { status: 200, body: { id: "1", org_id: "o", email: "a@d", role: "org_admin", name: "A" } },
    });
    renderLogin();
    fireEvent.change(screen.getByLabelText(/邮箱/), { target: { value: "a@d" } });
    fireEvent.change(screen.getByLabelText(/密码/), { target: { value: "pw" } });
    fireEvent.click(screen.getByRole("button", { name: /登录/ }));
    await waitFor(() => screen.getByText("admin home"));
  });

  it("shows error on 401", async () => {
    mockFetch({
      "/auth/login": { status: 401, body: { detail: "invalid credentials" } },
    });
    renderLogin();
    fireEvent.change(screen.getByLabelText(/邮箱/), { target: { value: "a@d" } });
    fireEvent.change(screen.getByLabelText(/密码/), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: /登录/ }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/invalid credentials/));
  });
});
