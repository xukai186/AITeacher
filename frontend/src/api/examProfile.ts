import { ApiError, api } from "./client";

export type EnglishTrack = "english_1" | "english_2";
export type MathTrack = "math_1" | "math_2" | "none";
export type SubjectCode = "english" | "math" | "politics";
export type CetStatus = "not_taken" | "cet4" | "cet6" | null;
export type MathMasteryLevel = "zero" | "basic" | "good" | "strong" | null;

export type ExamMajorCategory = {
  code: string;
  name: string;
  sort_order: number;
};

export type ExamMajor = {
  code: string;
  category_code: string;
  name: string;
  default_english_track: EnglishTrack;
  default_math_track: MathTrack;
  default_subject_codes: SubjectCode[];
  notes?: string | null;
};

export type StudentExamProfile = {
  major_category_code: string;
  major_code: string;
  english_track: EnglishTrack | null;
  math_track: MathTrack | null;
  subject_codes: SubjectCode[];
  cet_status: CetStatus;
  cet_score: number | null;
  math_mastery_level: MathMasteryLevel;
  profile_completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type UpsertStudentExamProfileInput = {
  major_category_code: string;
  major_code: string;
  english_track: EnglishTrack | null;
  math_track: MathTrack | null;
  subject_codes: SubjectCode[];
  cet_status: CetStatus;
  cet_score: number | null;
  math_mastery_level: MathMasteryLevel;
};

export function listExamMajorCategories() {
  return api<ExamMajorCategory[]>("/exam-majors/categories");
}

export function listExamMajorsByCategory(categoryCode: string) {
  return api<ExamMajor[]>(`/exam-majors?category=${encodeURIComponent(categoryCode)}`);
}

async function getExamProfileByPath(path: string) {
  try {
    return await api<StudentExamProfile>(path);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export function getAdminStudentExamProfile(studentId: string) {
  return getExamProfileByPath(`/admin/students/${studentId}/exam-profile`);
}

export function saveAdminStudentExamProfile(
  studentId: string,
  body: UpsertStudentExamProfileInput,
) {
  return api<StudentExamProfile>(`/admin/students/${studentId}/exam-profile`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function confirmAdminStudentExamProfile(studentId: string) {
  return api<StudentExamProfile>(`/admin/students/${studentId}/exam-profile/confirm`, {
    method: "POST",
  });
}

export function getStaffStudentExamProfile(studentId: string) {
  return getExamProfileByPath(`/staff/students/${studentId}/exam-profile`);
}

export function saveStaffStudentExamProfile(
  studentId: string,
  body: UpsertStudentExamProfileInput,
) {
  return api<StudentExamProfile>(`/staff/students/${studentId}/exam-profile`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function confirmStaffStudentExamProfile(studentId: string) {
  return api<StudentExamProfile>(`/staff/students/${studentId}/exam-profile/confirm`, {
    method: "POST",
  });
}

export function getStudentExamProfile() {
  return getExamProfileByPath("/student/exam-profile");
}
