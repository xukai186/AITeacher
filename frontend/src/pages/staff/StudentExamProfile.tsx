import { Link, useParams } from "react-router-dom";
import ExamProfileWizard from "@/components/exam/ExamProfileWizard";
import {
  confirmStaffStudentExamProfile,
  getStaffStudentExamProfile,
  saveStaffStudentExamProfile,
} from "@/api/examProfile";

export default function StudentExamProfile() {
  const { studentId = "" } = useParams();

  return (
    <div className="space-y-4 max-w-3xl">
      <Link to="/staff/students" className="text-sm text-blue-600 hover:underline">
        ← 返回我的学员
      </Link>
      <ExamProfileWizard
        studentId={studentId}
        title="完善报考档案（员工）"
        getExamProfile={getStaffStudentExamProfile}
        saveExamProfile={saveStaffStudentExamProfile}
        confirmExamProfile={confirmStaffStudentExamProfile}
      />
    </div>
  );
}
