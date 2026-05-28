import { Routes, Route, Navigate } from "react-router-dom";
import Login from "@/pages/Login";
import Layout from "@/components/Layout";
import ProtectedRoute from "@/components/ProtectedRoute";
import StudentsList from "@/pages/admin/StudentsList";
import StaffList from "@/pages/admin/StaffList";
import PackagesList from "@/pages/admin/PackagesList";
import MyStudents from "@/pages/staff/MyStudents";
import Workspace from "@/pages/student/Workspace";
import Placement from "@/pages/student/Placement";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/forbidden" element={<div className="p-6">无权访问</div>} />

      <Route
        element={
          <ProtectedRoute allow={["org_admin"]}>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/admin/students" element={<StudentsList />} />
        <Route path="/admin/staff" element={<StaffList />} />
        <Route path="/admin/packages" element={<PackagesList />} />
      </Route>

      <Route
        element={
          <ProtectedRoute allow={["org_staff"]}>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/staff/students" element={<MyStudents />} />
      </Route>

      <Route
        element={
          <ProtectedRoute allow={["student"]}>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/student/workspace/*" element={<Workspace />} />
        <Route path="/student/placement/:paperId" element={<Placement />} />
      </Route>

      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
