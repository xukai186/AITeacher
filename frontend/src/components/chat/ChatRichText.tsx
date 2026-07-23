import { Fragment, useMemo, type ReactNode } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";
import { prepareMathText, shouldDisplayMath } from "@/lib/mathText";

type Props = {
  text: string;
  className?: string;
};

/** Render chat text: newlines, light markdown (**bold**, `code`), and KaTeX math. */
export default function ChatRichText({ text, className }: Props) {
  const segments = useMemo(() => prepareMathText(text), [text]);

  return (
    <div className={className ?? "whitespace-pre-wrap break-words"}>
      {segments.map((segment, index) => {
        if (segment.type === "text") {
          return <Fragment key={index}>{renderFormattedText(segment.content)}</Fragment>;
        }

        const displayMode = shouldDisplayMath(segment.content, segment.display);
        const html = katex.renderToString(segment.content, {
          throwOnError: false,
          displayMode,
          strict: "ignore",
        });

        if (displayMode) {
          return (
            <span
              key={index}
              className="block my-2 overflow-x-auto"
              dangerouslySetInnerHTML={{ __html: html }}
            />
          );
        }

        return <span key={index} dangerouslySetInnerHTML={{ __html: html }} />;
      })}
    </div>
  );
}

function renderFormattedText(content: string) {
  const lines = content.split("\n");
  return lines.map((line, lineIndex) => (
    <Fragment key={lineIndex}>
      {lineIndex > 0 ? <br /> : null}
      {renderInlineMarkdown(line)}
    </Fragment>
  ));
}

/** Support **bold**, *italic*, `code`, and markdown headings / list markers lightly. */
function renderInlineMarkdown(line: string) {
  const trimmed = line.trimStart();
  const indent = line.slice(0, line.length - trimmed.length);

  let prefix: ReactNode = null;
  let body = trimmed;
  if (/^#{1,3}\s+/.test(trimmed)) {
    body = trimmed.replace(/^#{1,3}\s+/, "");
    return (
      <span className="font-semibold block">
        {indent}
        {renderInlineParts(body)}
      </span>
    );
  }
  if (/^[-*]\s+/.test(trimmed)) {
    body = trimmed.replace(/^[-*]\s+/, "");
    prefix = <span className="mr-1">•</span>;
  } else if (/^\d+\.\s+/.test(trimmed)) {
    const m = trimmed.match(/^(\d+)\.\s+(.*)$/);
    if (m) {
      prefix = <span className="mr-1">{m[1]}.</span>;
      body = m[2];
    }
  }

  return (
    <span>
      {indent}
      {prefix}
      {renderInlineParts(body)}
    </span>
  );
}

function renderInlineParts(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g).filter((p) => p.length > 0);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
      return (
        <code key={i} className="rounded bg-slate-200/80 px-1 py-0.5 text-[0.85em]">
          {part.slice(1, -1)}
        </code>
      );
    }
    if (part.startsWith("*") && part.endsWith("*") && part.length > 2 && !part.startsWith("**")) {
      return <em key={i}>{part.slice(1, -1)}</em>;
    }
    return <Fragment key={i}>{part}</Fragment>;
  });
}
