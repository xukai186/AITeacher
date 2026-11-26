import { describe, expect, it } from "vitest";
import { groupQuestionsByMaterial, splitQuestionStem } from "../src/lib/questionMaterial";

const passage = "Schools still need teachers who can explain ideas.";

describe("splitQuestionStem", () => {
  it("separates a shared passage from the question", () => {
    const stem = `【材料】\n${passage}\n\n【题目】\nWhat is the main idea?`;
    expect(splitQuestionStem(stem)).toEqual({
      material: passage,
      prompt: "What is the main idea?",
    });
  });

  it("leaves a standalone stem unchanged", () => {
    expect(splitQuestionStem("Choose the best word.")).toEqual({
      material: null,
      prompt: "Choose the best word.",
    });
  });
});

describe("groupQuestionsByMaterial", () => {
  it("shows one passage for consecutive questions that share it", () => {
    const stem = `【材料】\n${passage}\n\n【题目】\n`;
    const groups = groupQuestionsByMaterial([
      { id: "q1", stem: `${stem}What is the main idea?` },
      { id: "q2", stem: `${stem}What does the author imply?` },
      { id: "q3", stem: "Choose the best word." },
    ]);
    expect(groups).toHaveLength(2);
    expect(groups[0].material).toBe(passage);
    expect(groups[0].items.map((item) => item.prompt)).toEqual([
      "What is the main idea?",
      "What does the author imply?",
    ]);
    expect(groups[1].material).toBeNull();
  });
});
