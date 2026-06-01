import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { listMyStudents, Student } from "@/api/students";

export default function MyStudents() {
  const { data, isLoading, error } = useQuery<Student[]>({
    queryKey: ["staff", "students"],
    queryFn: listMyStudents,
  });

  return (
    <div className="space-y-4 max-w-3xl">
      <h1 className="text-xl font-semibold">我的学员</h1>
      {isLoading && <p className="text-slate-500">加载中…</p>}
      {error && <p className="text-red-600">{(error as Error).message}</p>}
      {data && (
        <table className="w-full text-sm bg-white shadow rounded">
          <thead className="bg-slate-100 text-left">
            <tr>
              <th className="px-4 py-2">姓名</th>
              <th className="px-4 py-2">邮箱</th>
              <th className="px-4 py-2">考试年份</th>
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
                  <Link
                    to={`/staff/students/${s.id}`}
                    className="text-blue-600 hover:underline"
                  >
                    详情
                  </Link>
                </td>
              </tr>
            ))}
            {data.length === 0 && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-slate-500">
                  暂无分配学员
                </td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}
