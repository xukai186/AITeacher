import { describe, expect, it } from "vitest";
import katex from "katex";
import {
  normalizeMathDelimiters,
  prepareMathText,
  shouldDisplayMath,
  splitMathSegments,
  wrapBareLatexInText,
} from "../src/lib/mathText";

const SAMPLE_STEM =
  "设总体 X 的概率密度为 f(x; \\theta) = \\theta x^{\\theta-1}, 0 < x < 1, 0, 其他, 其中 \\theta > 0 为未知参数。X_1, X_2, \\dots, X_n 为来自总体 X 的简单随机样本。 (1) 求 \\theta 的矩估计量； (2) 求 \\theta 的最大似然估计量； (3) 求 E(-\\ln X) 的值，并据此说明 \\theta 的最大似然估计量是否为 \\theta 的无偏估计。(10 分)";

describe("wrapBareLatexInText", () => {
  it("wraps undelimited LaTeX commands and subscripts", () => {
    const normalized = wrapBareLatexInText(SAMPLE_STEM);
    expect(normalized).toContain("$f(x; \\theta)");
    expect(normalized).toContain("$X_1, X_2, \\dots, X_n$");
    expect(normalized).toContain("$E(-\\ln X)$");
  });
});

describe("splitMathSegments", () => {
  it("splits inline math delimited by single dollar signs", () => {
    expect(splitMathSegments("设总体 $X$ 的概率密度")).toEqual([
      { type: "text", content: "设总体 " },
      { type: "math", content: "X", display: false },
      { type: "text", content: " 的概率密度" },
    ]);
  });

  it("splits display math delimited by double dollar signs", () => {
    expect(splitMathSegments("前缀 $$a+b$$ 后缀")).toEqual([
      { type: "text", content: "前缀 " },
      { type: "math", content: "a+b", display: true },
      { type: "text", content: " 后缀" },
    ]);
  });
});

describe("prepareMathText", () => {
  it("renders sample short-answer stem with katex", () => {
    const segments = prepareMathText(SAMPLE_STEM);
    const mathSegments = segments.filter((s) => s.type === "math");
    expect(mathSegments.length).toBeGreaterThan(3);
    for (const segment of mathSegments) {
      if (segment.type !== "math") continue;
      const html = katex.renderToString(segment.content, {
        throwOnError: false,
        displayMode: shouldDisplayMath(segment.content, segment.display),
      });
      expect(html).toContain("katex");
    }
  });
});

describe("katex rendering", () => {
  it("renders fractions and greek letters", () => {
    const html = katex.renderToString("\\frac{2x}{\\theta^2}", { throwOnError: false });
    expect(html).toContain("katex");
    expect(html).toContain("mfrac");
  });

  it("renders cases environment in display mode", () => {
    const tex = String.raw`\begin{cases} \frac{2x}{\theta^2}, & 0 < x < \theta \\ 0, & \text{其他} \end{cases}`;
    const html = katex.renderToString(tex, {
      throwOnError: false,
      displayMode: shouldDisplayMath(tex, false),
    });
    expect(html).toContain("katex");
  });
});
