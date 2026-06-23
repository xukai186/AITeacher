import { useMemo } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";
import { prepareMathText, shouldDisplayMath } from "@/lib/mathText";

type Props = {
  text: string;
  className?: string;
};

export default function MathText({ text, className }: Props) {
  const segments = useMemo(() => prepareMathText(text), [text]);

  return (
    <span className={className}>
      {segments.map((segment, index) => {
        if (segment.type === "text") {
          return <span key={index}>{segment.content}</span>;
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
    </span>
  );
}
