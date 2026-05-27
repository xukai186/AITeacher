import { api } from "./client";

export type LoginRequest = { email: string; password: string };
export type LoginResponse = { access_token: string; token_type: string };

export type Me = {
  id: string;
  org_id: string;
  email: string;
  role: "student" | "org_staff" | "org_admin";
  name: string;
};

export function login(body: LoginRequest) {
  return api<LoginResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function fetchMe() {
  return api<Me>("/me");
}
