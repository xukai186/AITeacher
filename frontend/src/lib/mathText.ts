export type MathTextSegment =
  | { type: "text"; content: string }
  | { type: "math"; content: string; display: boolean };

const CJK_RE = /[\u4e00-\u9fff]/;

function isMathStart(text: string, index: number): boolean {
  const ch = text[index];
  const next = text[index + 1] ?? "";
  if (ch === "\\") return true;
  if (/[A-Za-z]/.test(ch) && (next === "_" || next === "^")) return true;
  if (ch === "E" && next === "(") return true;
  return false;
}

/** Wrap bare LaTeX (`\theta`, `X_1`, `x^{2}`) in `$...$` when the model omits delimiters. */
export function wrapBareLatexInText(text: string): string {
  if (!text.includes("\\") && !/[A-Za-z][_^]/.test(text)) {
    return text;
  }

  let out = "";
  let textBuf = "";
  let mathBuf = "";
  let inMath = false;

  const flushText = () => {
    if (textBuf) {
      out += textBuf;
      textBuf = "";
    }
  };
  const flushMath = () => {
    const trimmed = mathBuf.trim();
    if (trimmed) out += `$${trimmed}$`;
    mathBuf = "";
    inMath = false;
  };

  const pullMathPrefix = (buf: string): { prefix: string; rest: string } => {
    const match = buf.match(/[A-Za-z]\([^)]*?[;,]\s*$/);
    if (!match) return { prefix: "", rest: buf };
    return { prefix: match[0], rest: buf.slice(0, -match[0].length) };
  };

  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (!inMath) {
      if (isMathStart(text, i)) {
        if (ch === "\\") {
          const { prefix, rest } = pullMathPrefix(textBuf);
          textBuf = rest;
          flushText();
          mathBuf = prefix + ch;
        } else {
          flushText();
          mathBuf += ch;
        }
        inMath = true;
      } else {
        textBuf += ch;
      }
      continue;
    }

    if (CJK_RE.test(ch)) {
      flushMath();
      textBuf += ch;
    } else {
      mathBuf += ch;
    }
  }

  if (inMath) flushMath();
  else flushText();

  return out;
}

/** Normalize a full stem: keep existing `$`/`$$` spans, wrap bare LaTeX elsewhere. */
export function normalizeMathDelimiters(text: string): string {
  if (!text.includes("$")) {
    return wrapBareLatexInText(text);
  }

  const parts: string[] = [];
  let index = 0;

  while (index < text.length) {
    if (text.startsWith("$$", index)) {
      const end = text.indexOf("$$", index + 2);
      if (end === -1) {
        parts.push(wrapBareLatexInText(text.slice(index)));
        break;
      }
      parts.push(text.slice(index, end + 2));
      index = end + 2;
      continue;
    }

    if (text[index] === "$") {
      const end = text.indexOf("$", index + 1);
      if (end === -1) {
        parts.push(wrapBareLatexInText(text.slice(index)));
        break;
      }
      parts.push(text.slice(index, end + 1));
      index = end + 1;
      continue;
    }

    const nextDollar = text.indexOf("$", index);
    const chunk = nextDollar === -1 ? text.slice(index) : text.slice(index, nextDollar);
    parts.push(wrapBareLatexInText(chunk));
    index = nextDollar === -1 ? text.length : nextDollar;
  }

  return parts.join("");
}

/** Split plain text with `$...$` / `$$...$$` LaTeX segments. */
export function splitMathSegments(text: string): MathTextSegment[] {
  const segments: MathTextSegment[] = [];
  let index = 0;

  while (index < text.length) {
    const displayStart = text.indexOf("$$", index);
    const inlineStart = text.indexOf("$", index);
    const next =
      displayStart === -1
        ? inlineStart
        : inlineStart === -1
          ? displayStart
          : Math.min(displayStart, inlineStart);

    if (next === -1) {
      if (index < text.length) {
        segments.push({ type: "text", content: text.slice(index) });
      }
      break;
    }

    if (next > index) {
      segments.push({ type: "text", content: text.slice(index, next) });
    }

    const display = text.startsWith("$$", next);
    const openLen = display ? 2 : 1;
    const close = display ? "$$" : "$";
    const closeIndex = text.indexOf(close, next + openLen);
    if (closeIndex === -1) {
      segments.push({ type: "text", content: text.slice(next) });
      break;
    }

    segments.push({
      type: "math",
      content: text.slice(next + openLen, closeIndex),
      display,
    });
    index = closeIndex + close.length;
  }

  return segments;
}

export function prepareMathText(text: string): MathTextSegment[] {
  return splitMathSegments(normalizeMathDelimiters(text));
}

export function shouldDisplayMath(tex: string, display: boolean): boolean {
  if (display) return true;
  return /\\begin\{/.test(tex);
}
