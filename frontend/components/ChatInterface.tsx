"use client";

import { useRef, useEffect } from "react";
import type { ChatMessage, ChatSource } from "@/lib/types";
import DrugInfoCard from "./DrugInfoCard";
import styles from "./ChatInterface.module.css";

interface Props {
  messages: ChatMessage[];
  loading: boolean;
  streamStatus?: string;
}

export default function ChatInterface({ messages, loading, streamStatus }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "auto" });
  }, [messages, loading]);

  if (messages.length === 0 && !loading) {
    return (
      <div className={styles.empty}>
        <div className={styles.emptyIcon} aria-hidden="true">
          <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
            <circle cx="24" cy="24" r="8" stroke="var(--accent-primary)" strokeWidth="1.5" />
            <circle cx="8" cy="16" r="4" stroke="var(--accent-primary)" strokeWidth="1.5" strokeOpacity="0.5" />
            <circle cx="40" cy="16" r="4" stroke="var(--accent-primary)" strokeWidth="1.5" strokeOpacity="0.5" />
            <circle cx="8" cy="32" r="4" stroke="var(--accent-primary)" strokeWidth="1.5" strokeOpacity="0.5" />
            <circle cx="40" cy="32" r="4" stroke="var(--accent-primary)" strokeWidth="1.5" strokeOpacity="0.5" />
            <line x1="16" y1="20" x2="12" y2="18" stroke="var(--accent-primary)" strokeWidth="1.5" strokeOpacity="0.5" />
            <line x1="32" y1="20" x2="36" y2="18" stroke="var(--accent-primary)" strokeWidth="1.5" strokeOpacity="0.5" />
            <line x1="16" y1="28" x2="12" y2="30" stroke="var(--accent-primary)" strokeWidth="1.5" strokeOpacity="0.5" />
            <line x1="32" y1="28" x2="36" y2="30" stroke="var(--accent-primary)" strokeWidth="1.5" strokeOpacity="0.5" />
          </svg>
        </div>
        <h2 className={styles.emptyTitle}>Start a drug query</h2>
        <p className={styles.emptyDesc}>
          Enter a drug name, SMILES notation, or PubChem CID to retrieve available pharmacological information.
        </p>
        <div className={styles.emptyHints}>
          <span className={styles.hint}>
            <span className={styles.hintDot} />
            Responses are grounded in cited sources.
          </span>
          <span className={styles.hint}>
            <span className={styles.hintDot} />
            Missing information is explicitly flagged.
          </span>
          <span className={styles.hint}>
            <span className={styles.hintDot} />
            Educational use only — not clinical advice.
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.thread}>
      {messages.map((msg) => (
        <div key={msg.id} className={styles.message}>
          {msg.role === "user" && (
            <div className={styles.userBubble}>
              <div className={styles.userContent}>
                <div className={styles.userBubbleText}>
                  {msg.smiles || msg.text}
                </div>
              </div>
            </div>
          )}

          {msg.role === "assistant" && msg.text && (
            <div className={styles.assistantBubble}>
              <div className={styles.assistantContent}>
                <AssistantTextCard msg={msg} />
              </div>
            </div>
          )}

          {msg.role === "assistant" && msg.drugInfo && (
            <div className={styles.assistantBubble}>
              <div className={styles.assistantContent}>
                <DrugInfoCard data={msg.drugInfo} />
              </div>
            </div>
          )}

          {msg.role === "assistant" && msg.error && (
            <div className={styles.errorBubble}>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <circle cx="8" cy="8" r="7" stroke="var(--color-error)" strokeWidth="1.2" />
                <path d="M8 4v5M8 11v1" stroke="var(--color-error)" strokeWidth="1.2" strokeLinecap="round" />
              </svg>
              {msg.error}
            </div>
          )}
        </div>
      ))}

      {loading && (
        <div className={styles.loadingBubble}>
          <div className={styles.loadingContent}>
            <div className={styles.loadingDots}>
              <span /><span /><span />
            </div>
            <span className={styles.loadingText}>
              {streamStatus || "Retrieving drug information…"}
            </span>
          </div>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}

function cleanUrl(url?: string): string {
  if (!url) return "";
  const m = url.match(/pug_view\/data\/compound\/(\d+)\/JSON(?:\?heading=([^&#]+))?/i);
  if (m) {
    const cid = m[1];
    const heading = m[2];
    if (heading) {
      return `https://pubchem.ncbi.nlm.nih.gov/compound/${cid}#section=${heading}`;
    }
    return `https://pubchem.ncbi.nlm.nih.gov/compound/${cid}`;
  }
  return url;
}

function getSourceMeta(url: string, name?: string): { tag: string; label: string } {
  const lower = (url || "").toLowerCase();
  if (lower.startsWith("doc:") || (name || "").toLowerCase().includes("pdf")) {
    return { tag: "PDF Document", label: name || "Indexed Literature PDF" };
  }
  if (lower.includes("dailymed.nlm.nih.gov")) {
    return { tag: "DailyMed", label: name || "DailyMed FDA Drug Label" };
  }
  if (lower.includes("pubchem.ncbi.nlm.nih.gov")) {
    return { tag: "PubChem", label: name || "PubChem Compound Record" };
  }
  if (lower.includes("pubmed.ncbi.nlm.nih.gov")) {
    return { tag: "PubMed", label: name || "PubMed Scientific Citation" };
  }
  if (lower.includes("fda.gov")) {
    return { tag: "FDA", label: name || "FDA Drug Approval Monograph" };
  }
  if (lower.includes("ebi.ac.uk/chembl") || lower.includes("chembl")) {
    return { tag: "ChEMBL", label: name || "ChEMBL Bioactivity Record" };
  }
  if (lower.includes("clinicaltrials.gov")) {
    return { tag: "ClinicalTrials", label: name || "ClinicalTrials.gov Registry" };
  }
  return { tag: "Literature", label: name || "Scientific Literature Reference" };
}

function parseSourcesAndText(rawText: string, initialSources?: ChatSource[]) {
  let text = rawText || "";
  const sourcesMap = new Map<string, ChatSource>();

  // Ingest existing sources
  (initialSources || []).forEach((s) => {
    const cleaned = cleanUrl(s.url);
    if (cleaned && !sourcesMap.has(cleaned)) {
      const meta = getSourceMeta(cleaned, s.name);
      sourcesMap.set(cleaned, {
        ...s,
        num: sourcesMap.size + 1,
        name: meta.label,
        url: cleaned,
      });
    }
  });

  // Extract inline markdown citations with URLs: [1](http...) or [SOURCE_1](http...)
  const inlineMarkdownRegex = /\[(?:SOURCE_)?\d*\]\((https?:\/\/[^\s)]+)\)/gi;
  let matchMd: RegExpExecArray | null;
  while ((matchMd = inlineMarkdownRegex.exec(text)) !== null) {
    const rawUrl = cleanUrl(matchMd[1]);
    if (rawUrl && !sourcesMap.has(rawUrl)) {
      const meta = getSourceMeta(rawUrl);
      sourcesMap.set(rawUrl, {
        id: `SOURCE_${sourcesMap.size + 1}`,
        num: sourcesMap.size + 1,
        name: meta.label,
        url: rawUrl,
      });
    }
  }

  // Extract any raw trailing Sources / References block
  const sourcesHeaderRegex = /(?:\r?\n)+\s*(?:Sources|References):?\s*(?:\r?\n)+/i;
  const parts = text.split(sourcesHeaderRegex);
  if (parts.length > 1) {
    text = parts[0].trim();
    const blockText = parts.slice(1).join("\n");
    const lines = blockText.split(/\r?\n/);
    lines.forEach((line) => {
      const urlMatch = line.match(/(https?:\/\/[^\s)]+)/i);
      if (urlMatch) {
        const rawUrl = cleanUrl(urlMatch[1]);
        if (rawUrl && !sourcesMap.has(rawUrl)) {
          const meta = getSourceMeta(rawUrl);
          sourcesMap.set(rawUrl, {
            id: `SOURCE_${sourcesMap.size + 1}`,
            num: sourcesMap.size + 1,
            name: meta.label,
            url: rawUrl,
          });
        }
      }
    });
  }

  // Remove all distracting inline tags from prose:
  // 1. Markdown link tags: [1](http...) -> remove
  text = text.replace(/\[\s*(?:SOURCE_)?\d+(?:\s*,\s*(?:SOURCE_)?\d+)*\s*\]\([^)]*\)/gi, "");
  // 2. Generic markdown links with URLs: [text](http...) -> keep text only if text is descriptive, or remove if citation
  text = text.replace(/\[(?:\d+|SOURCE_\d+|ref|citation)\]\([^)]*\)/gi, "");
  // 3. Bracket citation tags: [1], [1, 2], [SOURCE_1], [SOURCE_1, SOURCE_2]
  text = text.replace(/\[\s*(?:SOURCE_)?\d+(?:\s*,\s*(?:SOURCE_)?\d+)*\s*\]/gi, "");
  text = text.replace(/\[\s*SOURCE_\w+\s*\]/gi, "");
  text = text.replace(/\[(?:Citation|Evidence)\s*\d+\]/gi, "");
  // 4. Any leftover empty brackets or isolated citation tags
  text = text.replace(/\[\s*\]/g, "");
  text = text.replace(/\[(?:PubChem|DailyMed|PubMed|ChEMBL)\]/gi, "");
  // 5. XML/HTML tags
  text = text.replace(/<\/?(?:ref|source|citation|evidence)[^>]*>/gi, "");

  // Clean and normalize headings:
  // Convert •**Heading:*, •**Heading:**, **Heading:*, **Heading:** into clean ### Heading
  text = text.replace(
    /(?:^|\n)\s*[•*-]?\s*\*\*+([^*\n]+?)(?:\*+:|\*+|\*\*|:\*)\s*(?=\n|$)/g,
    "\n\n### $1\n\n"
  );
  // Remove trailing colon or stray asterisks in markdown headings
  text = text.replace(/(?:^|\n)\s*###\s+([^\n]+?):+\s*(?=\n|$)/g, "\n\n### $1\n\n");
  // Clean malformed bold headers like **Heading:* -> **Heading:**
  text = text.replace(/\*\*([^*\n]+?)\*:/g, "**$1:**");
  text = text.replace(/\*\*([^*\n]+?):\*/g, "**$1:**");

  // Ensure double newlines before every bullet point and heading
  text = text.replace(/([^\n])\n\s*([•*-]\s+)/g, "$1\n\n$2");
  text = text.replace(/([^\n])\n\s*(###\s+)/g, "$1\n\n$2");
  // Normalize bullet spacing: ensure bullet character has space after it
  text = text.replace(/(?:^|\n)\s*[•]\s*([^\s•\n])/g, "\n• $1");

  // Fix punctuation spacing resulting from stripped citations (e.g. "stimulant ." -> "stimulant.")
  text = text.replace(/\s+([.,;:!?])/g, "$1");
  text = text.replace(/[ \t]{2,}/g, " ");

  const sources = Array.from(sourcesMap.values());
  return { text: text.trim(), sources };
}

function renderInlineWithFormatting(str: string, baseKey: string) {
  const chunks = str.split(/(\*\*[^*\n]+\*\*)/g);
  return chunks.map((chunk, cIdx) => {
    if (chunk.startsWith("**") && chunk.endsWith("**") && chunk.length > 4) {
      return (
        <strong key={`${baseKey}-b-${cIdx}`} className={styles.proseBold}>
          {chunk.slice(2, -2)}
        </strong>
      );
    }
    return <span key={`${baseKey}-t-${cIdx}`}>{chunk}</span>;
  });
}

function FormattedProse({
  text,
  sources,
}: {
  text: string;
  sources: ChatSource[];
}) {
  const normalizedText = text
    .replace(/(?:^|\n)\s*[•*-]\s*\*\*+([^*\n]+?)(?:\*+:|\*+|\*\*|:\*)\s*(?=\n|$)/g, "\n\n### $1\n\n")
    .replace(/([^\n])\s*([*•-])\s+(\*\*|[A-Z])/g, "$1\n\n$2 $3")
    .replace(/(?:^|\n)\s*[•]\s*([^\s•\n])/g, "\n• $1")
    .replace(/\n{3,}/g, "\n\n");

  const paragraphs = normalizedText.split(/\n\n+/).map((p) => p.trim()).filter(Boolean);

  const renderSegment = (segText: string, pIdx: number) => {
    const parts = segText.split(/(\[\s*\d+(?:\s*,\s*\d+)*\s*\](?:\([^)]*\))?)/g);

    return parts.map((part, idx) => {
      const match = part.match(/^\[\s*(\d+(?:\s*,\s*\d+)*)\s*\](?:\(([^)]*)\))?$/);
      if (match) {
        const nums = match[1]
          .split(",")
          .map((n) => parseInt(n.trim(), 10))
          .filter((n) => !isNaN(n));
        const inlineUrl = match[2]?.trim();

        return (
          <span key={`cite-grp-${pIdx}-${idx}`} className={styles.citationGroup}>
            {nums.map((num) => {
              const src = sources.find((s) => s.num === num);
              const targetUrl = src?.url || inlineUrl || `#source-${num}`;
              return (
                <a
                  key={`cite-${num}`}
                  href={targetUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={styles.citationPill}
                  title={src ? `${src.name}\n${src.url}` : `Citation [${num}]`}
                  onClick={(e) => {
                    if (!src?.url && !inlineUrl) {
                      e.preventDefault();
                      document
                        .getElementById(`source-${num}`)
                        ?.scrollIntoView({ behavior: "auto" });
                    }
                  }}
                >
                  {num}
                </a>
              );
            })}
          </span>
        );
      }
      return (
        <span key={`text-${pIdx}-${idx}`}>
          {renderInlineWithFormatting(part, `p-${pIdx}-${idx}`)}
        </span>
      );
    });
  };

  return (
    <div>
      {paragraphs.map((p, pIdx) => {
        const isHeading = /^#{1,4}\s+/.test(p);
        if (isHeading) {
          const headingText = p.replace(/^#{1,4}\s+/, "");
          return (
            <h4 key={pIdx} className={styles.proseHeading}>
              {renderSegment(headingText, pIdx)}
            </h4>
          );
        }

        const isBullet = /^[*•-]\s+/.test(p);
        const cleanP = isBullet ? p.replace(/^[*•-]\s+/, "") : p;
        if (isBullet) {
          return (
            <div key={pIdx} className={styles.proseBulletItem}>
              <span className={styles.bulletDot}>•</span>
              <div style={{ flex: 1 }}>{renderSegment(cleanP, pIdx)}</div>
            </div>
          );
        }
        return (
          <p key={pIdx} className={styles.proseParagraph}>
            {renderSegment(cleanP, pIdx)}
          </p>
        );
      })}
    </div>
  );
}

function AssistantTextCard({ msg }: { msg: ChatMessage }) {
  const { text, sources } = parseSourcesAndText(msg.text || "", msg.sources);

  return (
    <div className={styles.assistantTextCard}>
      <FormattedProse text={text} sources={sources} />

      {sources.length > 0 && (
        <div className={styles.sourcesContainer}>
          <div className={styles.sourcesHeader}>
            <span className={styles.sourcesTitle}>Sources &amp; References</span>
            <span className={styles.sourcesCount}>· {sources.length}</span>
          </div>

          <div className={styles.sourcesGrid}>
            {sources.map((src) => {
              return (
                <a
                  key={src.num}
                  id={`source-${src.num}`}
                  href={src.url.startsWith("doc:") ? undefined : src.url}
                  target={src.url.startsWith("doc:") ? undefined : "_blank"}
                  rel={src.url.startsWith("doc:") ? undefined : "noopener noreferrer"}
                  className={styles.sourceCard}
                  title={src.url}
                  onClick={(e) => {
                    if (src.url.startsWith("doc:")) {
                      e.preventDefault();
                    }
                  }}
                >
                  <span className={styles.sourceNum}>{src.num}</span>
                  <div className={styles.sourceInfo}>
                    <span className={styles.sourceName}>{src.name}</span>
                    {src.text && (
                      <div className={styles.sourceSnippet} title={src.text}>
                        {src.text.trim()}
                      </div>
                    )}
                  </div>
                  {!src.url.startsWith("doc:") && (
                    <svg
                      className={styles.sourceIcon}
                      width="13"
                      height="13"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      aria-hidden="true"
                    >
                      <line x1="7" y1="17" x2="17" y2="7" />
                      <polyline points="7 7 17 7 17 17" />
                    </svg>
                  )}
                </a>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
