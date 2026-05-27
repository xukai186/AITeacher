import { api } from "./client";

export type StudentMe = {
  id: string;
  email: string;
  name: string;
  exam_year: number;
  subject_codes: string[];
};

export function fetchStudentMe() {
  return api<StudentMe>("/student/me");
}
