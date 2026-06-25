import { api } from "./client";

export type Student = {
  id: string;
  email: string;
  name: string;
  exam_year: number;
  exam_date: string | null;
  package_id: string | null;
  pending_task_count?: number;
  open_review_job_count?: number;
  requires_plan_confirmation?: boolean;
  wrong_added_7d?: number;
  exam_profile_complete?: boolean;
};

export type CreateStudentBody = {
  email: string;
  name: string;
  password: string;
  exam_year: number;
};

export function listStudents() {
  return api<Student[]>("/admin/students");
}

export function createStudent(body: CreateStudentBody) {
  return api<Student>("/admin/students", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function listMyStudents() {
  return api<Student[]>("/staff/students");
}
