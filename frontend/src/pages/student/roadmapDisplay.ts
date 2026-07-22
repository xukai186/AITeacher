import type { SyllabusNodeResolved } from "../../api/roadmap";

export function groupLeavesByParent(nodes: SyllabusNodeResolved[]): string[] {
  const order: string[] = [];
  const map = new Map<string, string[]>();
  for (const n of nodes) {
    const parent = n.parent_name?.trim() || "考纲";
    if (!map.has(parent)) {
      map.set(parent, []);
      order.push(parent);
    }
    map.get(parent)!.push(n.name);
  }
  return order.map((p) => `${p}：${map.get(p)!.join("、")}`);
}
