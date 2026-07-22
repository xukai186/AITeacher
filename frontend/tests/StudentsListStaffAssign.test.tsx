import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import StudentsList from "../src/pages/admin/StudentsList";

const assignStaff = vi.fn();
const unassignStaff = vi.fn();
const listStaff = vi.fn();
const listStudents = vi.fn();
const listPackages = vi.fn();

vi.mock("@/api/staff", () => ({
  listStaff: () => listStaff(),
  assignStaff: (...args: unknown[]) => assignStaff(...args),
  unassignStaff: (...args: unknown[]) => unassignStaff(...args),
  createStaff: vi.fn(),
}));

vi.mock("@/api/students", () => ({
  listStudents: () => listStudents(),
  createStudent: vi.fn(),
  listMyStudents: vi.fn(),
}));

vi.mock("@/api/packages", () => ({
  listPackages: () => listPackages(),
  assignPackage: vi.fn(),
}));

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <StudentsList />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("StudentsList staff assign", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listPackages.mockResolvedValue([]);
    listStaff.mockResolvedValue([{ id: "staff-1", email: "t@demo.example", name: "张老师" }]);
    listStudents.mockResolvedValue([
      {
        id: "stu-1",
        email: "s@demo.example",
        name: "学员甲",
        exam_year: 2027,
        exam_date: null,
        package_id: null,
        staff_user_ids: [],
        exam_profile_complete: false,
      },
    ]);
    assignStaff.mockResolvedValue({ student_id: "stu-1", staff_user_ids: ["staff-1"] });
    unassignStaff.mockResolvedValue({ student_id: "stu-1", staff_user_ids: [] });
  });

  it("assigns a teacher from the staff select", async () => {
    renderPage();
    const select = await screen.findByTestId("staff-assign-stu-1");
    fireEvent.change(select, { target: { value: "staff-1" } });
    await waitFor(() => {
      expect(assignStaff).toHaveBeenCalledWith("stu-1", "staff-1");
    });
  });
});
