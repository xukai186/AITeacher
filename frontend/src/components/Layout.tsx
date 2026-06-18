import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";

type NavItem = { to: string; label: string };

const NAV_BY_ROLE: Record<string, NavItem[]> = {
  org_admin: [
    { to: "/admin/students", label: "学员" },
    { to: "/admin/staff", label: "员工" },
    { to: "/admin/packages", label: "套餐" },
    { to: "/admin/model-policies", label: "模型策略" },
  ],
  org_staff: [{ to: "/staff/students", label: "我的学员" }],
  student: [
    { to: "/student/workspace", label: "今日计划" },
    { to: "/student/master-plan", label: "总计划" },
    { to: "/student/papers", label: "试卷中心" },
    { to: "/student/wrong-book", label: "错题本" },
    { to: "/student/report", label: "学情报告" },
  ],
};

export default function Layout() {
  const { state, logout } = useAuth();
  if (state.status !== "authed") return null;
  const items = NAV_BY_ROLE[state.me.role] ?? [];

  return (
    <div className="min-h-screen flex">
      <aside className="w-56 bg-slate-900 text-slate-100 p-4 flex flex-col">
        <div className="text-lg font-semibold mb-6">AITeacher</div>
        <nav className="flex-1 space-y-1">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end
              className={({ isActive }) =>
                `block px-3 py-2 rounded ${
                  isActive ? "bg-slate-700" : "hover:bg-slate-800"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="text-sm text-slate-400">
          <div>{state.me.name}</div>
          <button onClick={logout} className="mt-2 underline">
            退出
          </button>
        </div>
      </aside>
      <main className="flex-1 bg-slate-50 p-6 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
