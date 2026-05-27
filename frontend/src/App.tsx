import { Routes, Route, Navigate } from "react-router-dom";
import Login from "@/pages/Login";
import Layout from "@/components/Layout";
import ProtectedRoute from "@/components/ProtectedRoute";

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
        <Route path="/admin/students" element={<div>admin students placeholder</div>} />
        <Route path="/admin/staff" element={<div>admin staff placeholder</div>} />
        <Route path="/admin/packages" element={<div>admin packages placeholder</div>} />
      </Route>

      <Route
        element={
          <ProtectedRoute allow={["org_staff"]}>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/staff/students" element={<div>staff students placeholder</div>} />
      </Route>

      <Route
        element={
          <ProtectedRoute allow={["student"]}>
            <Layout />
          </ProtectedRoute>
        }
      >
        <Route path="/student/workspace/*" element={<div>student workspace placeholder</div>} />
      </Route>

      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}
