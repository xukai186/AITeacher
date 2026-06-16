import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import ModelPolicies from "../src/pages/admin/ModelPolicies";
import { setToken } from "../src/api/client";

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ModelPolicies />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ModelPolicies admin page", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    setToken("test-token");
  });

  it("loads chat policy and saves via PUT", async () => {
    const listPayload = [
      {
        id: "p1",
        org_id: "o1",
        scene: "chat",
        provider: "mock",
        model: "mock-v1",
        params: {},
      },
    ];

    const fetchMock = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/admin/model-policies/chat") && init?.method === "PUT") {
        return new Response(
          JSON.stringify({
            id: "p1",
            org_id: "o1",
            scene: "chat",
            provider: "mock",
            model: "mock-v1",
            params: {},
          }),
          { status: 200 },
        );
      }
      if (url.includes("/admin/model-policies") && (!init?.method || init.method === "GET")) {
        return new Response(JSON.stringify(listPayload), { status: 200 });
      }
      return new Response("not found", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    await waitFor(() => expect(screen.getByDisplayValue("mock-v1")).toBeTruthy());

    const form = document.querySelector("form");
    expect(form).toBeTruthy();
    fireEvent.submit(form!);

    await waitFor(() => {
      const putCall = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).includes("/admin/model-policies/chat") && init?.method === "PUT",
      );
      expect(putCall).toBeTruthy();
    });

    const putCall = fetchMock.mock.calls.find(
      ([url, init]) =>
        String(url).includes("/admin/model-policies/chat") && init?.method === "PUT",
    );
    const putBody = JSON.parse(String(putCall![1]!.body));
    expect(putBody.scene).toBe("chat");
    expect(putBody.provider).toBe("mock");
    expect(putBody.model).toBe("mock-v1");
  });

  it("renders grading policy form and saves via PUT", async () => {
    const listPayload = [
      {
        id: "p2",
        org_id: "o1",
        scene: "grading",
        provider: "openai_compat",
        model: "qwen-plus",
        params: { base_url: "https://example.invalid/v1", api_key: "k" },
      },
    ];

    const fetchMock = vi.fn(async (input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/admin/model-policies/grading") && init?.method === "PUT") {
        return new Response(JSON.stringify(listPayload[0]), { status: 200 });
      }
      if (url.includes("/admin/model-policies") && (!init?.method || init.method === "GET")) {
        return new Response(JSON.stringify(listPayload), { status: 200 });
      }
      return new Response("not found", { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    await waitFor(() => expect(screen.getByText(/批改场景（grading）/)).toBeTruthy());
    await waitFor(() => expect(screen.getByDisplayValue("qwen-plus")).toBeTruthy());

    const gradingForm = screen.getByText(/保存 grading 策略/).closest("form");
    expect(gradingForm).toBeTruthy();
    fireEvent.submit(gradingForm!);

    await waitFor(() => {
      const putCall = fetchMock.mock.calls.find(
        ([url, init]) =>
          String(url).includes("/admin/model-policies/grading") && init?.method === "PUT",
      );
      expect(putCall).toBeTruthy();
    });
  });
});
