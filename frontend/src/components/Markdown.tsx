import { Fragment, type ReactNode } from "react";

/**
 * A deliberately small markdown renderer: headings, lists, tables, bold, italic.
 *
 * Section 7 of the plan allows writing one rather than adding a library, and the
 * generated documents only ever use this subset. Nothing here interprets raw HTML, so
 * model output cannot inject markup into the page.
 */
export function Markdown({ source }: { source: string }) {
  return <div className="doc">{renderBlocks(source)}</div>;
}

function renderBlocks(source: string): ReactNode[] {
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  const out: ReactNode[] = [];
  let index = 0;
  let key = 0;

  while (index < lines.length) {
    const line = lines[index];

    if (!line.trim()) {
      index += 1;
      continue;
    }

    const heading = /^(#{1,4})\s+(.*)$/.exec(line);
    if (heading) {
      const level = heading[1].length;
      const text = inline(heading[2], key++);
      out.push(
        level <= 1 ? (
          <h2 key={key++}>{text}</h2>
        ) : level === 2 ? (
          <h2 key={key++}>{text}</h2>
        ) : (
          <h3 key={key++}>{text}</h3>
        ),
      );
      index += 1;
      continue;
    }

    // Table: a header row, a separator of dashes, then body rows.
    if (line.trim().startsWith("|") && /^\s*\|[\s:|-]+\|\s*$/.test(lines[index + 1] ?? "")) {
      const header = splitRow(line);
      const rows: string[][] = [];
      index += 2;
      while (index < lines.length && lines[index].trim().startsWith("|")) {
        rows.push(splitRow(lines[index]));
        index += 1;
      }
      out.push(
        <div key={key++} className="my-3 overflow-x-auto">
          <table className="w-full border-collapse text-[0.9375rem]">
            <thead>
              <tr>
                {header.map((cell, i) => (
                  <th
                    key={i}
                    className="border-b border-line pb-1.5 pr-3 text-left font-sans text-xs font-semibold text-ink-soft"
                  >
                    {inline(cell, i)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, r) => (
                <tr key={r}>
                  {row.map((cell, c) => (
                    <td key={c} className="border-b border-line py-1.5 pr-3 align-top">
                      {inline(cell, c)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      );
      continue;
    }

    if (/^\s*([-*+]|\d+\.)\s+/.test(line)) {
      const items: string[] = [];
      const ordered = /^\s*\d+\.\s+/.test(line);
      while (index < lines.length && /^\s*([-*+]|\d+\.)\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^\s*([-*+]|\d+\.)\s+/, ""));
        index += 1;
      }
      const List = ordered ? "ol" : "ul";
      out.push(
        <List key={key++} className={ordered ? "list-decimal pl-5" : undefined}>
          {items.map((item, i) => (
            <li key={i}>{inline(item, i)}</li>
          ))}
        </List>,
      );
      continue;
    }

    const paragraph: string[] = [];
    while (index < lines.length && lines[index].trim() && !/^(#{1,4}\s|\s*[-*+]\s|\|)/.test(lines[index])) {
      paragraph.push(lines[index].trim());
      index += 1;
    }
    out.push(<p key={key++}>{inline(paragraph.join(" "), key)}</p>);
  }

  return out;
}

function splitRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\||\|$/g, "")
    .split("|")
    .map((cell) => cell.trim());
}

/** Bold and italic only. Everything else stays literal text. */
function inline(text: string, keySeed: number): ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*|_[^_]+_)/g);
  return (
    <>
      {parts.map((part, i) => {
        const k = `${keySeed}-${i}`;
        if (/^(\*\*|__)/.test(part)) {
          return <strong key={k}>{part.slice(2, -2)}</strong>;
        }
        if (/^(\*|_)/.test(part) && part.length > 2) {
          return <em key={k}>{part.slice(1, -1)}</em>;
        }
        return <Fragment key={k}>{part}</Fragment>;
      })}
    </>
  );
}
