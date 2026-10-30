"use client";

import { useState, useCallback, useRef, useEffect, type KeyboardEvent } from "react";
import Link from "next/link";
import { getConnection, PROVIDERS } from "@/lib/connection";
import type { ChatMessage, ChatMode, ChatSession, DrugInfo, ResearchDocument } from "@/lib/types";
import { useBrowserReady } from "@/lib/useBrowserReady";
import { mergeNotebooks, parseNotebookBackup, validateNotebooks } from "@/lib/notebooks";
import { queryDrugStream } from "@/lib/api";
import ChatInterface from "@/components/ChatInterface";
import PDFDropzone from "@/components/PDFDropzone";
import DrugComparisonModal from "@/components/DrugComparisonModal";
import MoleculeDrawerModal from "@/components/MoleculeDrawerModal";
import OllamaConnectionNotice from "@/components/OllamaConnectionNotice";
import styles from "./chat.module.css";

interface Props {
  initialQuery?: string;
  initialMode?: ChatMode;
}

const CHAT_MODES: { id: ChatMode; title: string; description: string }[] = [
  { id: "paper_learning", title: "Paper learning", description: "Understand journal papers, methods, findings, and limitations." },
  { id: "structure_science", title: "Structure & science", description: "Explore molecule profiles, structures, properties, and sourced evidence." },
  { id: "molecule_theory", title: "Molecule theory", description: "Explore mechanisms, molecular interactions, and structure–activity relationships." },
];

export default function ChatWorkspace(props: Props) {
  const ready = useBrowserReady();
  return ready ? <LocalWorkspace {...props} /> : <main id="main-content" aria-busy="true" className={styles.workspaceNotice}>Opening workspace…</main>;
}

function LocalWorkspace({ initialQuery = "", initialMode = "structure_science" }: Props) {
  const [connection] = useState(getConnection);
  const [saved] = useState(() => {
    try {
      const raw = localStorage.getItem("pharmind_chat_sessions_v1");
      return { notebooks: raw ? validateNotebooks(JSON.parse(raw)) : [], error: "" };
    } catch {
      return { notebooks: [], error: "Saved notebooks could not be read. Import a backup to recover them." };
    }
  });
  const [sessions, setSessions] = useState<ChatSession[]>(saved.notebooks);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const activeSessionIdRef = useRef<string | null>(null);

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatMode, setChatMode] = useState<ChatMode>(initialMode);
  const requestRef = useRef<AbortController | null>(null);
  const backupInputRef = useRef<HTMLInputElement>(null);
  const [storageNotice, setStorageNotice] = useState(saved.error);
  const [comparison, setComparison] = useState([0, 1]);
  const [loading, setLoading] = useState(false);
  const [streamStatus, setStreamStatus] = useState<string>("");
  const [compareModalOpen, setCompareModalOpen] = useState(false);
  const [pdfModalOpen, setPdfModalOpen] = useState(false);
  const pdfDialogRef = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (pdfModalOpen) pdfDialogRef.current?.showModal();
  }, [pdfModalOpen]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(() => !window.matchMedia("(max-width: 760px)").matches);
  const [inputText, setInputText] = useState("");
  const [activePdf, setActivePdf] = useState<ResearchDocument | null>(null);
  const heroTextareaRef = useRef<HTMLTextAreaElement>(null);
  const bottomTextareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    activeSessionIdRef.current = activeSessionId;
  }, [activeSessionId]);

  useEffect(() => {
    // Leave unreadable stored data intact so a manual recovery remains possible.
    if (saved.error && !sessions.length) return;
    try {
      localStorage.setItem("pharmind_chat_sessions_v1", JSON.stringify(sessions));
    } catch {
      queueMicrotask(() => setStorageNotice("Notebook storage is full or unavailable. Export a backup before closing this page."));
    }
  }, [sessions, saved.error]);

  useEffect(() => () => requestRef.current?.abort(), []);

  function exportNotebooks() {
    const blob = new Blob([JSON.stringify({ format: "pharmind-notebooks", version: 1, notebooks: sessions }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url; link.download = `pharmind-notebooks-${new Date().toISOString().slice(0, 10)}.json`; link.click();
    URL.revokeObjectURL(url);
    setStorageNotice("Notebook backup exported. PDFs and model settings are stored separately.");
  }

  async function importNotebooks(file?: File) {
    if (!file) return;
    try {
      if (file.size > 20 * 1024 * 1024) throw new Error("Backups must be 20 MB or smaller.");
      const imported = parseNotebookBackup(await file.text());
      setSessions(current => mergeNotebooks(current, imported));
      setStorageNotice(`Imported ${imported.length} notebooks. Paper links require the same local document library.`);
    } catch (error) { setStorageNotice(error instanceof Error ? error.message : "Could not import this backup."); }
  }

  const drugInfos = messages.filter((m) => m.drugInfo).map((m) => m.drugInfo as DrugInfo);
  const hasStarted = messages.length > 0 || loading;

  const handleQuery = useCallback(async (queryStr: string) => {
    if (loading) return;
    const trimmed = queryStr.trim();
    if (!trimmed) return;
    const controller = new AbortController();
    requestRef.current = controller;

    let currentSessionId = activeSessionIdRef.current;
    const isNewSession = !currentSessionId;
    if (isNewSession) {
      currentSessionId = `sess-${Date.now()}`;
      setActiveSessionId(currentSessionId);
      activeSessionIdRef.current = currentSessionId;
    }

    const titleCandidate = trimmed.length > 30 ? trimmed.slice(0, 28).trim() + "…" : trimmed;

    const lower = trimmed.toLowerCase();
    const words = trimmed.split(/\s+/).filter(Boolean);

    const isSmilesPattern = !trimmed.includes(" ") && (/[=#()@\\/]/.test(trimmed) || /^[A-Z][a-z]?\d*$/.test(trimmed));
    const isPubChemCidPattern = /^cid\s*\d+$/i.test(trimmed);

    const hasQuestionSign = trimmed.includes("?") || trimmed.includes("!");
    const conversationalStarters = [
      "what", "how", "why", "when", "who", "which", "where",
      "can", "could", "would", "should", "is", "are", "does", "do", "will",
      "tell", "explain", "describe", "summarize", "compare", "difference",
      "show", "list", "give", "help", "find", "search", "check", "verify"
    ];
    const startsConversational = conversationalStarters.some((s) => lower.startsWith(s + " ") || lower === s);

    const conversationalKeywords = [
      "side effect", "side-effect", "adverse", "toxicity", "mechanism", "pharmacodynamics",
      "pharmacokinetics", "adme", "half-life", "half life", "metabolism", "metabolize",
      "interaction", "interact", "indication", "contraindication", "dosage", "dose",
      "symptom", "disease", "treatment", "treat", "cure", "prescribe", "safe with", "taken with"
    ];
    const hasConversationalKeyword = conversationalKeywords.some((kw) => lower.includes(kw));

    const isSmilesOrDrug = chatMode === "structure_science" && (
      isSmilesPattern ||
      isPubChemCidPattern ||
      (words.length <= 2 && !hasQuestionSign && !startsConversational && !hasConversationalKeyword)
    );

    if (isSmilesOrDrug) {
      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        smiles: trimmed,
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMsg]);
      setSessions((prev) => {
        if (isNewSession) {
          const newSession: ChatSession = {
            id: currentSessionId!,
            title: titleCandidate,
            createdAt: Date.now(),
            updatedAt: Date.now(),
            messages: [userMsg],
            mode: chatMode,
            activeDocument: activePdf ?? undefined,
          };
          return [newSession, ...prev.filter((s) => s.id !== currentSessionId)];
        } else {
          return prev.map((s) =>
            s.id === currentSessionId
              ? { ...s, updatedAt: Date.now(), messages: [...s.messages, userMsg] }
              : s
          );
        }
      });

      setLoading(true);
      setStreamStatus("Initializing local query...");

      let finalData: any = null;
      let errorMessage: string | null = null;
      let generatedCharacters = 0;

      await queryDrugStream(trimmed, {
        onStatus: (status) => {
          setStreamStatus(status.message);
        },
        onToken: (fragment) => {
          generatedCharacters += fragment.length;
          if (generatedCharacters % 200 < fragment.length) {
            setStreamStatus(
              `Generating structured profile… ${generatedCharacters.toLocaleString()} characters received`
            );
          }
        },
        onResult: (data) => {
          finalData = data;
        },
        onError: (err) => {
          errorMessage = err;
        },
      }, controller.signal);

      requestRef.current = null;
      setLoading(false);
      setStreamStatus("");

      const assistantMsg: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        drugInfo: finalData || undefined,
        error: errorMessage || (finalData ? undefined : "Network error — could not connect to local backend."),
        timestamp: new Date().toISOString(),
      };

      if (activeSessionIdRef.current === currentSessionId) {
        setMessages((prev) => [...prev, assistantMsg]);
      }
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id !== currentSessionId) return s;
          const refinedTitle = finalData?.drug_name?.generic || s.title || titleCandidate;
          return {
            ...s,
            title: refinedTitle,
            updatedAt: Date.now(),
            messages: [...s.messages, assistantMsg],
          };
        })
      );
    } else {

      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        text: trimmed,
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, userMsg]);
      setSessions((prev) => {
        if (isNewSession) {
          const newSession: ChatSession = {
            id: currentSessionId!,
            title: titleCandidate,
            createdAt: Date.now(),
            updatedAt: Date.now(),
            messages: [userMsg],
            mode: chatMode,
            activeDocument: activePdf ?? undefined,
          };
          return [newSession, ...prev.filter((s) => s.id !== currentSessionId)];
        } else {
          return prev.map((s) =>
            s.id === currentSessionId
              ? { ...s, updatedAt: Date.now(), messages: [...s.messages, userMsg] }
              : s
          );
        }
      });

      setLoading(true);
      setStreamStatus("Searching evidence & generating answer...");

      const history = messages
        .filter((m) => m.text || m.smiles || m.drugInfo)
        .map((m) => ({
          role: m.role,
          content:
            m.text ||
            (m.smiles
              ? `Drug query: ${m.smiles}`
              : m.drugInfo
                ? `Retrieved profile for ${m.drugInfo.drug_overview?.identity?.generic_name?.content || m.drugInfo.drug_name?.generic || "compound"}; CID ${m.drugInfo.drug_overview?.identifiers?.pubchem_cid ?? m.drugInfo.chemical_structure?.pubchem_cid ?? "unknown"}.`
                : ""),
        }))
        .filter((m) => m.content)
        .slice(-20) as { role: "user" | "assistant"; content: string }[];

      const lastDrugInfo = [...messages].reverse().find((m) => m.drugInfo)?.drugInfo;
      const activeDrug = lastDrugInfo
        ? {
          name: lastDrugInfo.drug_overview?.identity?.generic_name?.content || lastDrugInfo.drug_name?.generic || "",
          cid: (lastDrugInfo.drug_overview?.identifiers?.pubchem_cid ?? lastDrugInfo.chemical_structure?.pubchem_cid)?.toString(),
        }
        : activePdf?.associated_drug
        ? { name: activePdf.associated_drug }
        : { name: "" };

      const { sendChatMessage } = await import("@/lib/api");
      const res = await sendChatMessage(trimmed, history, activeDrug, chatMode, { documentId: activePdf?.document_id, signal: controller.signal });

      setLoading(false);
      setStreamStatus("");

      requestRef.current = null;
      const assistantMsg: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        text: res.success ? res.answer : undefined,
        sources: res.success ? (res.sources || []) : undefined,
        error: res.success ? undefined : res.error || "Could not generate answer.",
        timestamp: new Date().toISOString(),
      };

      if (activeSessionIdRef.current === currentSessionId) {
        setMessages((prev) => [...prev, assistantMsg]);
      }
      setSessions((prev) =>
        prev.map((s) =>
          s.id === currentSessionId
            ? {
              ...s,
              updatedAt: Date.now(),
              messages: [...s.messages, assistantMsg],
            }
            : s
        )
      );
    }
  }, [activePdf, chatMode, loading, messages]);

  const handleQueryRef = useRef(handleQuery);
  useEffect(() => {
    handleQueryRef.current = handleQuery;
  }, [handleQuery]);

  // Run initial query from searchParams if provided
  const ranInitialRef = useRef(false);
  useEffect(() => {
    if (ranInitialRef.current) return;
    const q = (initialQuery || "").trim();
    if (!q) return;
    ranInitialRef.current = true;
    handleQueryRef.current(q);
  }, [initialQuery]);

  const handleSelectSession = useCallback((sessionId: string) => {
    if (loading) return;
    const target = sessions.find((s) => s.id === sessionId);
    if (target) {
      setActiveSessionId(target.id);
      setMessages(target.messages || []);
      setChatMode(target.mode || "structure_science");
      setActivePdf(target.activeDocument ?? null);
      setStreamStatus("");
      setInputText("");
    }
  }, [loading, sessions]);

  const handleModeChange = (mode: ChatMode) => {
    if (loading) return;
    setChatMode(mode);
    const sessionId = activeSessionIdRef.current;
    if (sessionId) {
      setSessions((prev) => prev.map((session) =>
        session.id === sessionId ? { ...session, mode } : session
      ));
    }
  };

  const handleDeleteSession = useCallback((e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    if (loading) return;
    setSessions((prev) => prev.filter((s) => s.id !== sessionId));
    if (activeSessionIdRef.current === sessionId) {
      setActiveSessionId(null);
      setMessages([]);
      setStreamStatus("");
    }
  }, [loading]);

  const handleNewChat = useCallback(() => {
    if (loading) return;
    setActiveSessionId(null);
    setMessages([]);
    setStreamStatus("");
    setInputText("");
    setActivePdf(null);
  }, [loading]);

  const handlePdfIngested = useCallback(
    (doc: ResearchDocument) => {
      setChatMode("paper_learning");
      setActivePdf(doc);
      setPdfModalOpen(false);

      let currentSessionId = activeSessionIdRef.current;
      const isNew = !currentSessionId;
      if (isNew) {
        currentSessionId = `sess-${Date.now()}`;
        setActiveSessionId(currentSessionId);
        activeSessionIdRef.current = currentSessionId;
      }

      const introMsg: ChatMessage = {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        text: `### ${doc.filename} Selected for paper learning\n\nThis local paper has **${doc.chunks} passages** across **${doc.pages} page(s)** in local vector memory${
          doc.associated_drug ? ` (associated with **${doc.associated_drug}**)` : ""
        }.\n\nYou can ask questions specifically about this paper, request a structured summary, or explore the authors’ conclusions. Answers use this selected paper until you unlink it.`,
        timestamp: new Date().toISOString(),
      };

      setMessages((prev) => [...prev, introMsg]);
      setSessions((prev) => {
        if (isNew) {
          return [
            {
              id: currentSessionId!,
              title: `Paper: ${doc.filename.slice(0, 20)}...`,
              createdAt: Date.now(),
              updatedAt: Date.now(),
              messages: [introMsg],
              mode: "paper_learning",
              activeDocument: doc,
            },
            ...prev,
          ];
        } else {
          return prev.map((s) =>
            s.id === currentSessionId
              ? { ...s, updatedAt: Date.now(), messages: [...s.messages, introMsg], mode: "paper_learning", activeDocument: doc }
              : s
          );
        }
      });
    },
    []
  );

  const unlinkPaper = () => {
    if (loading) return;
    setActivePdf(null);
    setSessions(current => current.map(session => session.id === activeSessionIdRef.current ? { ...session, activeDocument: undefined } : session));
  };

  const documentDeleted = (documentId: string) => {
    if (activePdf?.document_id === documentId) setActivePdf(null);
    setSessions(current => current.map(session => session.activeDocument?.document_id === documentId ? { ...session, activeDocument: undefined } : session));
  };

  const handleSubmit = (e?: React.SyntheticEvent) => {
    if (e?.preventDefault) {
      e.preventDefault();
    }
    if (loading) return;
    const query = (
      inputText ||
      heroTextareaRef.current?.value ||
      bottomTextareaRef.current?.value ||
      ""
    ).trim();
    if (query) {
      handleQuery(query);
      setInputText("");
      if (heroTextareaRef.current) heroTextareaRef.current.value = "";
      if (bottomTextareaRef.current) bottomTextareaRef.current.value = "";
    } else {
      (heroTextareaRef.current || bottomTextareaRef.current)?.focus();
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className={styles.layout}>
      <aside className={`${styles.sidebar} ${!sidebarOpen ? styles.sidebarCollapsed : ""}`}>
        <div className={styles.sidebarHeader}>
          <div className={styles.sidebarBrand}>
            <span className={styles.brandName}>Pharmind</span>
          </div>
          <button
            type="button"
            className={styles.collapseBtn}
            onClick={() => setSidebarOpen(false)}
            aria-label="Collapse sidebar"
            title="Collapse sidebar"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <line x1="9" y1="3" x2="9" y2="21" />
            </svg>
          </button>
        </div>
        <div className={styles.newChatWrap}>
          <button
            type="button"
            className={styles.newChatBtn}
            onClick={handleNewChat}
            aria-label="Start new research"
          >
            <span className={styles.newChatBtnLeft}>
              <span style={{ fontSize: "1.1rem" }}>+</span>
              <span>New research</span>
            </span>
            <svg className={styles.newChatSearchIcon} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </button>
        </div>
        <div className={styles.sidebarScroll}>
          <div className={styles.navSection}>
            <button
              type="button"
              className={styles.navItem}
              disabled={loading}
              onClick={() => setPdfModalOpen(true)}
              aria-label="Open document library"
            >
              <span className={styles.navItemIcon}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
              </span>
              <span>Document library</span>
            </button>
          </div>
          <div>
            <div className={styles.sectionHeader}>
              <span>YOUR NOTEBOOKS</span>
            </div>
            <div className={styles.backupActions}>
              <button type="button" onClick={exportNotebooks} disabled={!sessions.length}>Export</button>
              <button type="button" onClick={() => backupInputRef.current?.click()} disabled={loading}>Import</button>
              <input ref={backupInputRef} type="file" accept="application/json,.json" hidden onChange={event => { void importNotebooks(event.target.files?.[0]); event.target.value = ""; }} />
            </div>
            <div className={styles.recentChatList}>
              {sessions.length === 0 ? (
                <div className={styles.emptyRecent}>No saved research yet.</div>
              ) : (
                sessions.map((session) => (
                  <div
                    key={session.id}
                    role="button"
                    tabIndex={0}
                    className={`${styles.recentSessionRow} ${activeSessionId === session.id ? styles.activeRecentSession : ""}`}
                    onClick={() => handleSelectSession(session.id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        handleSelectSession(session.id);
                      }
                    }}
                    title={session.title}
                  >
                    <span className={styles.recentSessionIcon} aria-hidden="true">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                      </svg>
                    </span>
                    <span className={styles.recentSessionTitle}>{session.title}</span>
                    <button
                      type="button"
                      className={styles.deleteSessionBtn}
                      onClick={(e) => handleDeleteSession(e, session.id)}
                      title="Delete chat"
                      aria-label={`Delete chat ${session.title}`}
                    >
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <line x1="18" y1="6" x2="6" y2="18" />
                        <line x1="6" y1="6" x2="18" y2="18" />
                      </svg>
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
        <Link href="/settings" className={styles.userProfile}>
          <svg className={styles.connectionIcon} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="m9 3-.6 2.4-1.8 1L4.2 6 2 10l1.8 1.6v2L2 15l2.2 4 2.4-.4 1.8 1L9 22h5l.6-2.4 1.8-1 2.4.4 2.2-4-1.8-1.4v-2L21 10l-2.2-4-2.4.4-1.8-1L14 3Z" />
            <circle cx="11.5" cy="12.5" r="3" />
          </svg>
          <div className={styles.userInfo}>
            <span className={styles.userName}>Model & connection</span>
            <span className={styles.userEmail}>{PROVIDERS[connection.provider].name} · {connection.provider === "ollama" ? "On device" : "BYOK"}</span>
          </div>
        </Link>
      </aside>
      <main id="main-content" className={styles.main}>
        <header className={styles.topbar}>
          <div className={styles.topbarLeft}>
            {!sidebarOpen && (
              <button
                type="button"
                className={styles.expandSidebarBtn}
                onClick={() => setSidebarOpen(true)}
                title="Open sidebar"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="3" y="3" width="18" height="18" rx="2" />
                  <line x1="9" y1="3" x2="9" y2="21" />
                </svg>
              </button>
            )}
            <span className={styles.workspaceTitle}>{sessions.find(session => session.id === activeSessionId)?.title || "Research workspace"}</span>
          </div>

          <div className={styles.topbarRight}>
            <button type="button" className={styles.toolsBtn} disabled={loading} onClick={() => setDrawerOpen(true)}>Structure editor</button>
            {drugInfos.length >= 2 && (
              <button
                type="button"
                style={{
                  padding: "5px 12px",
                  background: "var(--blue)",
                  border: "1px solid var(--steel)",
                  borderRadius: "6px",
                  color: "var(--slate)",
                  fontSize: "0.82rem",
                  fontWeight: 600,
                  cursor: "pointer",
                }}
                onClick={() => { setComparison([0, 1]); setCompareModalOpen(true); }}
              >
                Compare Candidates ({drugInfos.length})
              </button>
            )}
          </div>
        </header>
        <OllamaConnectionNotice connection={connection} />
        {storageNotice && <div className={styles.workspaceNotice} role="status">{storageNotice}<button type="button" onClick={() => setStorageNotice("")} aria-label="Dismiss notice">×</button></div>}
        {loading && <div className={styles.workspaceNotice} role="status"><span>{streamStatus || "Working…"}</span><button type="button" onClick={() => requestRef.current?.abort()}>Stop request</button></div>}
        {!hasStarted ? (
          <div className={styles.emptyStateScroll}>
            <div className={styles.emptyHero}>

              <h1 className={styles.heroHeading}>New research</h1><p className={styles.heroSubtitle}>Ask about a compound or add a paper to begin.</p>

              <div className={styles.modePicker} role="group" aria-label="Choose a research mode">
                {CHAT_MODES.map((mode) => (
                  <button
                    key={mode.id}
                    type="button"
                    className={styles.modeCard}
                    aria-pressed={chatMode === mode.id}
                    onClick={() => handleModeChange(mode.id)}
                  >
                    <span className={styles.modeCardTitle}>{mode.title}</span>
                    <span className={styles.modeCardDescription}>{mode.description}</span>
                  </button>
                ))}
              </div>

              {activePdf && (
                <div className={styles.activePdfPill}>
                  <span className={styles.activePdfIcon}>📄</span>
                  <span className={styles.activePdfName} title={activePdf.filename}>
                    Active Paper: <strong>{activePdf.filename}</strong> ({activePdf.pages}p)
                  </span>
                  <button
                    type="button"
                    className={styles.clearPdfBtn}
                    onClick={unlinkPaper}
                    title="Unlink paper from active chat context"
                    aria-label="Remove active paper"
                  >
                    ✕
                  </button>
                </div>
              )}

              {activePdf && (
                <div className={styles.pdfSuggestionChips}>
                  <button
                    type="button"
                    className={styles.chipBtn}
                    onClick={() => handleQuery(`Summarize the core findings and clinical significance of "${activePdf.filename}".`)}
                  >
                    Summarize paper
                  </button>
                  <button
                    type="button"
                    className={styles.chipBtn}
                    onClick={() => handleQuery(`Extract all reported dosages, pharmacokinetics, and mechanism of action from "${activePdf.filename}".`)}
                  >
                    Extract PK & Mechanism
                  </button>
                  <button
                    type="button"
                    className={styles.chipBtn}
                    onClick={() => handleQuery(`What adverse effects or contraindications are documented in "${activePdf.filename}"?`)}
                  >
                    Safety & Adverse Effects
                  </button>
                </div>
              )}
              <form onSubmit={handleSubmit} className={styles.promptBox}>
                <textarea
                  ref={heroTextareaRef}
                  className={styles.promptTextarea}
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  onInput={(e) => setInputText((e.target as HTMLTextAreaElement).value)}
                  onKeyDown={handleKeyDown}
                  placeholder={activePdf
                    ? `Ask questions about ${activePdf.filename}...`
                    : chatMode === "paper_learning"
                      ? "Ask about a paper, study design, results, or limitations..."
                      : chatMode === "molecule_theory"
                        ? "Explore a molecule's mechanism, interactions, or structure–activity relationship..."
                        : "Enter a molecule name or SMILES, or ask a scientific question..."}
                  rows={2}
                  disabled={loading}
                  aria-label="Research task or drug query input"
                />

                <div className={styles.promptToolbar}>
                  <div className={styles.toolsMenuWrap}>
                    <button
                      type="button"
                      className={styles.toolsBtn}
                      disabled={loading}
              onClick={() => setPdfModalOpen(true)}
                    >
                      <span>+</span>
                      <span>Add a paper</span>
                      <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
                        <path fillRule="evenodd" d="M4.22 6.22a.75.75 0 0 1 1.06 0L8 8.94l2.72-2.72a.75.75 0 1 1 1.06 1.06l-3.25 3.25a.75.75 0 0 1-1.06 0L4.22 7.28a.75.75 0 0 1 0-1.06z" clipRule="evenodd" />
                      </svg>
                    </button>
                  </div>

                  <div className={styles.toolbarRight}>
                    <Link href="/settings" className={styles.modelBadge}>
                      <span>{PROVIDERS[connection.provider].name}</span>
                      <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
                        <path fillRule="evenodd" d="M4.22 6.22a.75.75 0 0 1 1.06 0L8 8.94l2.72-2.72a.75.75 0 1 1 1.06 1.06l-3.25 3.25a.75.75 0 0 1-1.06 0L4.22 7.28a.75.75 0 0 1 0-1.06z" clipRule="evenodd" />
                      </svg>
                    </Link>
                    <button
                      type="button"
                      onClick={handleSubmit}
                      className={styles.sendBtn}
                      disabled={loading}
                      aria-label="Send message"
                      title="Send message"
                      style={{
                        backgroundColor: "var(--slate)",
                        color: "var(--bg-surface)",
                        cursor: loading ? "not-allowed" : "pointer",
                      }}
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                        <line x1="12" y1="19" x2="12" y2="5" />
                        <polyline points="5 12 12 5 19 12" />
                      </svg>
                    </button>
                  </div>
                </div>
              </form>
              <p className={styles.workspaceNote}>Conversations saved in this browser. {connection.provider === "ollama" ? "Inference uses your local Ollama model." : "Prompts and evidence go to your selected provider."}</p>
            </div>
          </div>
        ) : (
          /* Active Chat Workspace */
          <div className={styles.chatWorkspace}>
            <div className={styles.chatMessagesArea}>
              <ChatInterface messages={messages} loading={loading} streamStatus={streamStatus} />
            </div>
            <div className={styles.chatInputBottomBar}>
              <div className={styles.chatInputWrapper}>
                {activePdf && (
                  <div className={styles.activePdfPill}>
                    <span className={styles.activePdfIcon}>📄</span>
                    <span className={styles.activePdfName} title={activePdf.filename}>
                      Active Paper: <strong>{activePdf.filename}</strong> ({activePdf.pages}p)
                    </span>
                    <button
                      type="button"
                      className={styles.clearPdfBtn}
                      onClick={unlinkPaper}
                      title="Unlink paper from active chat context"
                      aria-label="Remove active paper"
                    >
                      ✕
                    </button>
                  </div>
                )}
                {activePdf && messages.length <= 2 && (
                  <div className={styles.pdfSuggestionChips}>
                    <button
                      type="button"
                      className={styles.chipBtn}
                      onClick={() => handleQuery(`Summarize the core findings and clinical significance of "${activePdf.filename}".`)}
                    >
                      Summarize paper
                    </button>
                    <button
                      type="button"
                      className={styles.chipBtn}
                      onClick={() => handleQuery(`Extract all reported dosages, pharmacokinetics, and mechanism of action from "${activePdf.filename}".`)}
                    >
                      Extract PK & Mechanism
                    </button>
                    <button
                      type="button"
                      className={styles.chipBtn}
                      onClick={() => handleQuery(`What adverse effects or contraindications are documented in "${activePdf.filename}"?`)}
                    >
                      Safety & Adverse Effects
                    </button>
                  </div>
                )}
                <form onSubmit={handleSubmit} className={styles.promptBox}>
                  <textarea
                    ref={bottomTextareaRef}
                    className={styles.promptTextarea}
                    value={inputText}
                    onChange={(e) => setInputText(e.target.value)}
                    onInput={(e) => setInputText((e.target as HTMLTextAreaElement).value)}
                    onKeyDown={handleKeyDown}
                    placeholder={activePdf
                      ? `Ask questions about ${activePdf.filename}...`
                      : chatMode === "paper_learning"
                        ? "Ask a follow-up about the papers or study evidence..."
                        : chatMode === "molecule_theory"
                          ? "Ask a follow-up about mechanisms or molecular theory..."
                          : "Ask a follow-up, enter SMILES, or request a comparison..."}
                    rows={1}
                    disabled={loading}
                    aria-label="Follow-up question or drug query input"
                  />
                  <div className={styles.promptToolbar}>
                    <div className={styles.toolsMenuWrap}>
                      <button
                        type="button"
                        className={styles.toolsBtn}
                        disabled={loading}
              onClick={() => setPdfModalOpen(true)}
                      >
                        <span>+</span>
                        <span>Add a paper</span>
                      </button>
                    </div>
                    <div className={styles.toolbarRight}>
                      <button
                        type="button"
                        onClick={handleSubmit}
                        className={styles.sendBtn}
                        disabled={loading}
                        aria-label="Send message"
                        title="Send message"
                        style={{
                          backgroundColor: "var(--slate)",
                          color: "var(--bg-surface)",
                          cursor: loading ? "not-allowed" : "pointer",
                        }}
                      >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                          <line x1="12" y1="19" x2="12" y2="5" />
                          <polyline points="5 12 12 5 19 12" />
                        </svg>
                      </button>
                    </div>
                  </div>
                </form>
              </div>
            </div>
          </div>
        )}
        {pdfModalOpen && (
          <dialog ref={pdfDialogRef} className={styles.modalBackdrop} aria-labelledby="pdf-title" onCancel={() => setPdfModalOpen(false)} onClick={event => { if (event.target === event.currentTarget) setPdfModalOpen(false); }}>
            <div className={styles.modalCard} onClick={(e) => e.stopPropagation()}>
              <div className={styles.modalHeader}>
                <h3 id="pdf-title" className={styles.modalTitle}>Your document library</h3>
                <button
                  type="button"
                  className={styles.closeModalBtn}
                  aria-label="Close document library"
                  onClick={() => setPdfModalOpen(false)}
                >
                  ✕
                </button>
              </div>
              <div className={styles.modalBody}>
                <PDFDropzone onSuccess={handlePdfIngested} onSelect={handlePdfIngested} onDeleted={documentDeleted} />
              </div>
            </div>
          </dialog>
        )}
        <MoleculeDrawerModal
          isOpen={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          onApply={(smiles) => {
            setInputText(smiles);
            setChatMode("structure_science");
          }}
        />
        {compareModalOpen && drugInfos.length >= 2 && (
          <DrugComparisonModal
            candidates={drugInfos}
            leftIndex={comparison[0]}
            rightIndex={comparison[1]}
            onSelect={(side, index) => setComparison(current => side === "left" ? [index, current[1]] : [current[0], index])}
            leftDrug={drugInfos[comparison[0]]}
            rightDrug={drugInfos[comparison[1]]}
            onClose={() => setCompareModalOpen(false)}
          />
        )}
      </main>
    </div>
  );
}
