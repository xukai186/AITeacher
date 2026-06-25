import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import ExamProfileWizard from "../src/components/exam/ExamProfileWizard";
import type { ExamMajor, ExamMajorCategory, StudentExamProfile } from "../src/api/examProfile";

const categories: ExamMajorCategory[] = [
  { code: "academic_master", name: "学硕", sort_order: 1 },
];

const majors: ExamMajor[] = [
  {
    code: "cs_academic",
    category_code: "academic_master",
    name: "计算机科学与技术",
    default_english_track: "english_1",
    default_math_track: "math_1",
    default_subject_codes: ["english", "math", "politics"],
    notes: "推荐方向",
  },
];

const mockProfile: StudentExamProfile = {
  major_category_code: "academic_master",
  major_code: "cs_academic",
  english_track: "english_1",
  math_track: "math_1",
  subject_codes: ["english", "math", "politics"],
  cet_status: null,
  cet_score: null,
  math_mastery_level: null,
  profile_completed_at: null,
  created_at: "2026-06-01T00:00:00Z",
  updated_at: "2026-06-01T00:00:00Z",
};

const apiMocks = vi.hoisted(() => ({
  listExamMajorCategories: vi.fn(async () => categories),
  listExamMajorsByCategory: vi.fn(async () => majors),
  getExamProfile: vi.fn(async () => null),
  saveExamProfile: vi.fn(async () => mockProfile),
  confirmExamProfile: vi.fn(async () => mockProfile),
}));

vi.mock("../src/api/examProfile", async () => {
  const actual = await vi.importActual("../src/api/examProfile");
  return {
    ...actual,
    listExamMajorCategories: apiMocks.listExamMajorCategories,
    listExamMajorsByCategory: apiMocks.listExamMajorsByCategory,
  };
});

function renderWizard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <ExamProfileWizard
          studentId="stu-1"
          title="完善报考档案"
          getExamProfile={apiMocks.getExamProfile}
          saveExamProfile={apiMocks.saveExamProfile}
          confirmExamProfile={apiMocks.confirmExamProfile}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ExamProfileWizard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows cs major recommended english_1 and math_1", async () => {
    renderWizard();

    await waitFor(() => expect(screen.getByLabelText("报考大类")).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText("报考大类"), { target: { value: "academic_master" } });
    fireEvent.click(screen.getByRole("button", { name: "下一步" }));

    await waitFor(() => expect(screen.getByLabelText("具体专业")).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText("具体专业"), { target: { value: "cs_academic" } });

    expect(screen.getByText("英语卷种：english_1")).toBeInTheDocument();
    expect(screen.getByText("数学卷种：math_1")).toBeInTheDocument();
  });
});
