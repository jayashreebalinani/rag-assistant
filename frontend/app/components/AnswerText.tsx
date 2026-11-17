import type { ReactNode } from "react";

// Matches **bold** and citations like [1, page 2] or [1] (the model sometimes uses 【】 brackets)
const TOKEN = /\*\*(.+?)\*\*|[\[【](\d+)(?:,\s*page\s*\d+)?[\]】]/gi;

type Props = {
  text: string;
  sourceCount: number;
  onCite: (index: number) => void;
};

export default function AnswerText({ text, sourceCount, onCite }: Props) {
  return <div className="whitespace-pre-wrap leading-relaxed">{render(text, sourceCount, onCite)}</div>;
}

function render(text: string, sourceCount: number, onCite: (index: number) => void): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;

  for (const m of text.matchAll(TOKEN)) {
    const start = m.index ?? 0;
    if (start > last) out.push(text.slice(last, start));

    if (m[1] !== undefined) {
      out.push(
        <strong key={start} className="font-semibold">
          {render(m[1], sourceCount, onCite)}
        </strong>,
      );
    } else {
      const n = Number(m[2]);
      if (n >= 1 && n <= sourceCount) {
        out.push(
          <button
            key={start}
            type="button"
            onClick={() => onCite(n - 1)}
            className="mx-0.5 rounded bg-blue-100 px-1 text-sm font-medium text-blue-700 hover:bg-blue-200 dark:bg-blue-900/50 dark:text-blue-300 dark:hover:bg-blue-900"
            title={`Show source ${n}`}
          >
            {m[0]}
          </button>,
        );
      } else {
        out.push(m[0]);
      }
    }
    last = start + m[0].length;
  }

  if (last < text.length) out.push(text.slice(last));
  return out;
}
