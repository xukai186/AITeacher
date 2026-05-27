import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";

const ROLE_HOME: Record<string, string> = {
  org_admin: "/admin/students",
  org_staff: "/staff/students",
  student: "/student/workspace",
};

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const me = await login(email, password);
      navigate(ROLE_HOME[me.role] ?? "/", { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <form onSubmit={onSubmit} className="bg-white shadow rounded p-8 w-full max-w-sm">
        <h1 className="text-2xl font-semibold mb-6">AITeacher 登录</h1>
        <label className="block mb-3">
          <span className="text-sm text-slate-600">邮箱</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="mt-1 w-full border rounded px-3 py-2"
          />
        </label>
        <label className="block mb-4">
          <span className="text-sm text-slate-600">密码</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="mt-1 w-full border rounded px-3 py-2"
          />
        </label>
        {error && <p role="alert" className="text-sm text-red-600 mb-3">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="w-full bg-slate-900 text-white py-2 rounded disabled:opacity-50"
        >
          {busy ? "登录中…" : "登录"}
        </button>
      </form>
    </div>
  );
}
