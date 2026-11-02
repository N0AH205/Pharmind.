"use client";

import { Children, type ReactNode } from "react";
import Markdown from "react-markdown";
import type { ChatSource } from "@/lib/types";
import { normalizeChatMarkdown } from "@/lib/markdown";
import styles from "./ChatInterface.module.css";

interface Props {
  text: string;
  sources: ChatSource[];
  onSource: (source: ChatSource) => void;
}

export default function FormattedProse({ text, sources, onSource }: Props) {
  const citations = (children: ReactNode) => Children.map(children, child => {
    if (typeof child !== "string") return child;
    return child.split(/(\[\s*\d+(?:\s*,\s*\d+)*\s*\])/g).map((part, index) => {
      if (!/^\[\s*\d+(?:\s*,\s*\d+)*\s*\]$/.test(part)) return part;
      return <span key={index} className={styles.citationGroup}>
        {part.slice(1, -1).split(",").map(Number).map(num => {
          const source = sources.find(item => item.num === num);
          return source ? <button key={num} type="button" className={styles.citationPill} title={`View source ${num}: ${source.name}`} onClick={() => onSource(source)}>{num}</button> : null;
        })}
      </span>;
    });
  });
  const heading = ({ children }: { children?: ReactNode }) => <h4>{citations(children)}</h4>;

  return <div className={styles.prose}>
    <Markdown skipHtml disallowedElements={["img"]} components={{
      p: ({ children }) => <p>{citations(children)}</p>,
      li: ({ children }) => <li>{citations(children)}</li>,
      strong: ({ children }) => <strong>{citations(children)}</strong>,
      em: ({ children }) => <em>{citations(children)}</em>,
      a: ({ children }) => <span>{citations(children)}</span>,
      h1: heading, h2: heading, h3: heading, h4: heading, h5: heading, h6: heading,
    }}>{normalizeChatMarkdown(text)}</Markdown>
  </div>;
}
