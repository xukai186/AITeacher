import { api } from "./client";

export type Staff = { id: string; email: string; name: string };

export type CreateStaffBody = { email: string; name: string; password: string };

export function listStaff() {
  return api<Staff[]>("/admin/staff");
}

export function createStaff(body: CreateStaffBody) {
  return api<Staff>("/admin/staff", { method: "POST", body: JSON.stringify(body) });
}

export function assignStaff(studentId: string, staffUserId: string) {
  return api<{ student_id: string; staff_user_ids: string[] }>(
    `/admin/students/${studentId}/staff`,
    { method: "POST", body: JSON.stringify({ staff_user_id: staffUserId }) },
  );
}

export function unassignStaff(studentId: string, staffUserId: string) {
  return api<{ student_id: string; staff_user_ids: string[] }>(
    `/admin/students/${studentId}/staff/${staffUserId}`,
    { method: "DELETE" },
  );
}
