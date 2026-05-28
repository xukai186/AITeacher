import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createPackage, listPackages } from "@/api/packages";

const SUBJECT_OPTIONS = [
  { code: "politics", label: "政治" },
  { code: "english", label: "英语" },
  { code: "math", label: "数学" },
];

export default function PackagesList() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin", "packages"],
    queryFn: listPackages,
  });
  const createMut = useMutation({
    mutationFn: createPackage,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "packages"] }),
  });

  const [name, setName] = useState("");
  const [subjects, setSubjects] = useState<string[]>([]);

  const toggle = (code: string) =>
    setSubjects((curr) =>
      curr.includes(code) ? curr.filter((c) => c !== code) : [...curr, code],
    );

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (subjects.length === 0) return;
    createMut.mutate(
      { name, subject_codes: subjects },
      {
        onSuccess: () => {
          setName("");
          setSubjects([]);
        },
      },
    );
  };

  return (
    <div className="space-y-6 max-w-3xl">
      <h1 className="text-xl font-semibold">套餐</h1>
      <form onSubmit={onSubmit} className="bg-white shadow rounded p-4 space-y-3">
        <input
          className="border rounded px-3 py-2 w-full"
          placeholder="套餐名"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <div className="flex gap-3 flex-wrap">
          {SUBJECT_OPTIONS.map((opt) => (
            <label key={opt.code} className="inline-flex items-center gap-2">
              <input
                type="checkbox"
                checked={subjects.includes(opt.code)}
                onChange={() => toggle(opt.code)}
              />
              {opt.label}
            </label>
          ))}
        </div>
        <button
          type="submit"
          disabled={createMut.isPending || subjects.length === 0}
          className="bg-slate-900 text-white rounded py-2 px-4 disabled:opacity-50"
        >
          {createMut.isPending ? "创建中…" : "新增套餐"}
        </button>
        {createMut.error && (
          <p role="alert" className="text-red-600 text-sm">
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
                <th className="px-4 py-2">名称</th>
                <th className="px-4 py-2">科目</th>
              </tr>
            </thead>
            <tbody>
              {data.map((p) => (
                <tr key={p.id} className="border-t">
                  <td className="px-4 py-2">{p.name}</td>
                  <td className="px-4 py-2">{p.subject_codes.join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
