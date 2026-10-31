"use client";

import { useRef, useEffect, useState } from "react";
import type { ChatMessage, ChatSource } from "@/lib/types";
import DrugInfoCard from "./DrugInfoCard";
import CitationModal from "./CitationModal";
import { normalizeChatCitations } from "@/lib/citations";
import styles from "./ChatInterface.module.css";

interface Props {
  onSuggestion?: (query: string) => void;
  messages: ChatMessage[];
  loading: boolean;
  streamStatus?: string;
}

export default function ChatInterface({ messages, loading, streamStatus, onSuggestion }: Props) {
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

          {msg.role === "assistant" && msg.notice && <p className={styles.researchNotice} role="status">{msg.notice}</p>}
          {msg.role === "assistant" && !!msg.suggestions?.length && <div className={styles.suggestions}>{msg.suggestions.map(suggestion => <button type="button" key={suggestion.query} disabled={loading} onClick={() => onSuggestion?.(suggestion.query)}>Search {suggestion.label}</button>)}</div>}

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
  onSource,
}: {
  text: string;
  sources: ChatSource[];
  onSource: (source: ChatSource) => void;
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
              if (!src) return null;
              return <button key={`cite-${num}`} type="button" className={styles.citationPill}
                title={`View source ${num}: ${src.name}`} onClick={() => onSource(src)}>{num}</button>;
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
  const { text, sources } = normalizeChatCitations(msg.text || "", msg.sources);
  const [selectedSource, setSelectedSource] = useState<ChatSource | null>(null);

  return (
    <div className={styles.assistantTextCard}>
      <FormattedProse text={text} sources={sources} onSource={setSelectedSource} />
      {selectedSource && <CitationModal citation={{ source: selectedSource.name, url: selectedSource.url || undefined, text: selectedSource.text, document_id: selectedSource.document_id }} onClose={() => setSelectedSource(null)} />}

      {sources.length > 0 && (
        <div className={styles.sourcesContainer}>
          <div className={styles.sourcesHeader}>
            <span className={styles.sourcesTitle}>{sources.some(source => source.cited !== false) ? "Cited sources" : "Consulted passages (not claim citations)"}</span>
            <span className={styles.sourcesCount}>· {sources.length}</span>
          </div>

          <div className={styles.sourcesGrid}>
            {sources.map((src) => {
              return (
                <button type="button" key={src.num} className={styles.sourceCard}
                  onClick={() => setSelectedSource(src)} title={`Inspect ${src.name}`}>
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
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
