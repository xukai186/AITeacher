import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listKnowledgeNodes } from "@/api/questionBank";

type Props = {
  subjectCode: string;
  value: string | null;
  onChange: (id: string | null) => void;
  disabled?: boolean;
};

function optionLabel(name: string, parentName: string | null) {
  return parentName ? `${parentName} / ${name}` : name;
}

export default function KnowledgeNodeSelect({
  subjectCode,
  value,
  onChange,
  disabled = false,
}: Props) {
  const [filter, setFilter] = useState("");
  const nodesQuery = useQuery({
    queryKey: ["knowledge-nodes", subjectCode],
    queryFn: () => listKnowledgeNodes(subjectCode),
    enabled: Boolean(subjectCode),
  });

  const options = useMemo(() => {
    const nodes = nodesQuery.data ?? [];
    const needle = filter.trim().toLowerCase();
    if (!needle) return nodes;
    return nodes.filter((node) =>
      optionLabel(node.name, node.parent_name).toLowerCase().includes(needle),
    );
  }, [filter, nodesQuery.data]);

  return (
    <div className="space-y-2">
      <input
        type="search"
        value={filter}
        onChange={(event) => setFilter(event.target.value)}
        placeholder="搜索知识点"
        disabled={disabled || !subjectCode || nodesQuery.isLoading}
        className="w-full rounded border px-3 py-2 text-sm disabled:opacity-50"
        aria-label="搜索知识点"
      />
      <select
        value={value ?? ""}
        onChange={(event) =>
          onChange(event.target.value ? event.target.value : null)
        }
        disabled={disabled || !subjectCode || nodesQuery.isLoading}
        className="w-full rounded border px-3 py-2 disabled:opacity-50"
        aria-label="知识点"
      >
        <option value="">未标注</option>
        {options.map((node) => (
          <option key={node.id} value={node.id}>
            {optionLabel(node.name, node.parent_name)}
          </option>
        ))}
      </select>
      {nodesQuery.error ? (
        <p role="alert" className="text-sm text-red-600">
          {(nodesQuery.error as Error).message}
        </p>
      ) : null}
    </div>
  );
}
