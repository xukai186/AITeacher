import { Link, useParams } from "react-router-dom";
import ExamProfileWizard from "@/components/exam/ExamProfileWizard";
import {
  confirmAdminStudentExamProfile,
  getAdminStudentExamProfile,
  saveAdminStudentExamProfile,
} from "@/api/examProfile";

export default function StudentExamProfile() {
  const { studentId = "" } = useParams();

  return (
    <div className="space-y-4 max-w-3xl">
      <Link to="/admin/students" className="text-sm text-blue-600 hover:underline">
        ← 返回学员列表
      </Link>
      <ExamProfileWizard
        studentId={studentId}
        title="完善报考档案（管理员）"
        getExamProfile={getAdminStudentExamProfile}
        saveExamProfile={saveAdminStudentExamProfile}
        confirmExamProfile={confirmAdminStudentExamProfile}
      />
    </div>
  );
}
