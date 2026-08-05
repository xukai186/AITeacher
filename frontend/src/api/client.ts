const API_BASE = "/api";

let currentToken: string | null = null;

export function setToken(token: string | null) {
  currentToken = token;
  if (token) localStorage.setItem("aiteacher_token", token);
  else localStorage.removeItem("aiteacher_token");
}

export function loadToken(): string | null {
  if (currentToken) return currentToken;
  currentToken = localStorage.getItem("aiteacher_token");
  return currentToken;
}

export function formatApiDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const body = detail as { reasons?: unknown; detail?: unknown; message?: unknown };
    if (Array.isArray(body.reasons) && body.reasons.length > 0) {
      return body.reasons.map(String).join("；");
    }
    if (typeof body.detail === "string") return body.detail;
    if (typeof body.message === "string") return body.message;
    try {
      return JSON.stringify(detail);
    } catch {
      return "请求失败";
    }
  }
  return detail == null ? "请求失败" : String(detail);
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
  ) {
    super(`API ${status}: ${formatApiDetail(detail)}`);
  }

  /** Human-readable reasons when detail is a structured eligibility payload. */
  get reasonText(): string {
    return formatApiDetail(this.detail);
  }

  get openPaperId(): string | null {
    if (!this.detail || typeof this.detail !== "object") return null;
    const id = (this.detail as { open_paper_id?: unknown }).open_paper_id;
    return typeof id === "string" && id ? id : null;
  }
}

export async function api<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const token = loadToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const resp = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!resp.ok) {
    let detail: unknown = resp.statusText;
    try {
      const body = await resp.json();
      detail = body?.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(resp.status, detail);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}
