import { describe, it, expect } from "vitest";
import { groupLeavesByParent } from "../src/pages/student/roadmapDisplay";

describe("groupLeavesByParent", () => {
  it("groups by parent_name", () => {
    const lines = groupLeavesByParent([
      { name: "细节题", parent_name: "阅读" },
      { name: "主旨题", parent_name: "阅读" },
      { name: "词义选择", parent_name: "翻译" },
    ]);
    expect(lines).toEqual(["阅读：细节题、主旨题", "翻译：词义选择"]);
  });
});
