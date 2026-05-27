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

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(`API ${status}: ${detail}`);
  }
}

export async function api<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  const token = loadToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const resp = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!resp.ok) {
    let detail = resp.statusText;
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
