import { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";
import { Me } from "@/api/auth";

type Props = {
  allow: Me["role"][];
  children: ReactNode;
};

export default function ProtectedRoute({ allow, children }: Props) {
  const { state } = useAuth();
  if (state.status === "loading") {
    return <div className="p-6 text-slate-500">加载中…</div>;
  }
  if (state.status === "anon") {
    return <Navigate to="/login" replace />;
  }
  if (!allow.includes(state.me.role)) {
    return <Navigate to="/forbidden" replace />;
  }
  return <>{children}</>;
}
