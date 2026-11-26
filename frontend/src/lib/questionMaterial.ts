export type StemParts = {
  material: string | null;
  prompt: string;
};

const STEM_RE = /^【材料】\r?\n([\s\S]*?)\r?\n\r?\n【题目】\r?\n([\s\S]*)$/;

export function splitQuestionStem(stem: string): StemParts {
  const match = stem.match(STEM_RE);
  if (!match) return { material: null, prompt: stem };
  const material = match[1].trim();
  const prompt = match[2].trim();
  if (!material || !prompt) return { material: null, prompt: stem };
  return { material, prompt };
}

export type QuestionGroup<T> = {
  material: string | null;
  items: Array<{ question: T; prompt: string }>;
};

export function groupQuestionsByMaterial<T extends { stem: string }>(
  questions: T[],
): QuestionGroup<T>[] {
  const groups: QuestionGroup<T>[] = [];
  for (const question of questions) {
    const { material, prompt } = splitQuestionStem(question.stem);
    const last = groups[groups.length - 1];
    if (material && last?.material === material) {
      last.items.push({ question, prompt });
    } else {
      groups.push({ material, items: [{ question, prompt }] });
    }
  }
  return groups;
}
