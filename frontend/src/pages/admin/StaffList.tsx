import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createStaff, listStaff } from "@/api/staff";

export default function StaffList() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin", "staff"],
    queryFn: listStaff,
  });
  const createMut = useMutation({
    mutationFn: createStaff,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "staff"] }),
  });

  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    createMut.mutate(
      { email, name, password },
      {
        onSuccess: () => {
          setEmail("");
          setName("");
          setPassword("");
        },
      },
    );
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <h1 className="text-xl font-semibold">员工</h1>
      <form onSubmit={onSubmit} className="bg-white shadow rounded p-4 grid grid-cols-2 gap-3">
        <input
          className="border rounded px-3 py-2"
          placeholder="姓名"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <input
          className="border rounded px-3 py-2"
          type="email"
          placeholder="邮箱"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          className="border rounded px-3 py-2 col-span-2"
          type="password"
          placeholder="初始密码"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <button
          type="submit"
          disabled={createMut.isPending}
          className="col-span-2 bg-slate-900 text-white rounded py-2 disabled:opacity-50"
        >
          {createMut.isPending ? "创建中…" : "新增员工"}
        </button>
        {createMut.error && (
          <p role="alert" className="col-span-2 text-red-600 text-sm">
            {(createMut.error as Error).message}
          </p>
        )}
      </form>

      <section className="bg-white shadow rounded">
        {isLoading && <p className="p-4 text-slate-500">加载中…</p>}
        {error && <p className="p-4 text-red-600">{(error as Error).message}</p>}
        {data && (
          <table className="w-full text-sm">
            <thead className="bg-slate-100 text-left">
              <tr>
                <th className="px-4 py-2">姓名</th>
                <th className="px-4 py-2">邮箱</th>
              </tr>
            </thead>
            <tbody>
              {data.map((s) => (
                <tr key={s.id} className="border-t">
                  <td className="px-4 py-2">{s.name}</td>
                  <td className="px-4 py-2">{s.email}</td>
                </tr>
              ))}
              {data.length === 0 && (
                <tr>
                  <td colSpan={2} className="px-4 py-6 text-center text-slate-500">
                    暂无员工
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
