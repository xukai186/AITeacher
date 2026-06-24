import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { assignPackage, listPackages } from "@/api/packages";
import { createStudent, listStudents, Student } from "@/api/students";
import { StudentSignals } from "@/components/org/StudentSignals";

export default function StudentsList() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery<Student[]>({
    queryKey: ["admin", "students"],
    queryFn: listStudents,
  });

  const { data: packages } = useQuery({
    queryKey: ["admin", "packages"],
    queryFn: listPackages,
  });

  const createMut = useMutation({
    mutationFn: createStudent,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "students"] }),
  });

  const assignMut = useMutation({
    mutationFn: ({ studentId, packageId }: { studentId: string; packageId: string }) =>
      assignPackage(studentId, packageId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "students"] }),
  });

  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [examYear, setExamYear] = useState(new Date().getFullYear() + 1);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    createMut.mutate(
      { email, name, password, exam_year: examYear },
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
    <div className="space-y-6 max-w-4xl">
      <h1 className="text-xl font-semibold">学员</h1>

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
          className="border rounded px-3 py-2"
          type="password"
          placeholder="初始密码"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <input
          className="border rounded px-3 py-2"
          type="number"
          placeholder="考试年份"
          value={examYear}
          onChange={(e) => setExamYear(Number(e.target.value))}
          required
        />
        <button
          type="submit"
          disabled={createMut.isPending}
          className="col-span-2 bg-slate-900 text-white rounded py-2 disabled:opacity-50"
        >
          {createMut.isPending ? "创建中…" : "新增学员"}
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
                <th className="px-4 py-2">考试年份</th>
                <th className="px-4 py-2">学情摘要</th>
                <th className="px-4 py-2">套餐</th>
                <th className="px-4 py-2">报考档案</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {data.map((s) => (
                <tr key={s.id} className="border-t">
                  <td className="px-4 py-2">{s.name}</td>
                  <td className="px-4 py-2">{s.email}</td>
                  <td className="px-4 py-2">{s.exam_year}</td>
                  <td className="px-4 py-2">
                    <StudentSignals student={s} />
                  </td>
                  <td className="px-4 py-2">
                    <select
                      className="border rounded px-2 py-1 text-sm"
                      value={s.package_id ?? ""}
                      onChange={(e) => assignMut.mutate({ studentId: s.id, packageId: e.target.value })}
                      disabled={!packages || packages.length === 0}
                    >
                      <option value="" disabled>
                        未分配
                      </option>
                      {packages?.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-4 py-2">
                    <Link
                      to={`/admin/students/${s.id}/exam-profile`}
                      className="text-blue-600 hover:underline inline-flex items-center gap-2"
                    >
                      报考档案
                      {s.exam_profile_complete === false && (
                        <span className="text-[10px] px-2 py-0.5 rounded bg-amber-100 text-amber-800">
                          未完成
                        </span>
                      )}
                    </Link>
                  </td>
                  <td className="px-4 py-2">
                    <Link
                      to={`/admin/students/${s.id}`}
                      className="text-blue-600 hover:underline"
                    >
                      详情
                    </Link>
                  </td>
                </tr>
              ))}
              {data.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-6 text-center text-slate-500">
                    暂无学员
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
