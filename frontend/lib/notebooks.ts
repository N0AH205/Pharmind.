import type { ChatSession } from "./types";

const modes = new Set(["paper_learning", "structure_science", "molecule_theory"]);
const record = (value: unknown): value is Record<string, any> => !!value && typeof value === "object" && !Array.isArray(value);

export function validateNotebooks(value: unknown): ChatSession[] {
  if (!Array.isArray(value)) throw new Error("Expected a notebook list.");
  const ids = new Set<string>();
  for (const session of value) {
    if (!record(session) || typeof session.id !== "string" || !session.id || ids.has(session.id) ||
        typeof session.title !== "string" || !Number.isFinite(session.createdAt) || !Number.isFinite(session.updatedAt) ||
        (session.mode !== undefined && !modes.has(session.mode)) || !Array.isArray(session.messages)) {
      throw new Error("This backup contains an invalid notebook.");
    }
    ids.add(session.id);
    for (const message of session.messages) {
      if (!record(message) || typeof message.id !== "string" || !["user", "assistant"].includes(message.role) ||
          typeof message.timestamp !== "string" || ["text", "smiles", "error"].some(key => message[key] !== undefined && typeof message[key] !== "string")) {
        throw new Error("This backup contains an invalid message.");
      }
      if (message.sources !== undefined && (!Array.isArray(message.sources) || message.sources.some((source: unknown) =>
        !record(source) || !Number.isInteger(source.num) || typeof source.id !== "string" || typeof source.name !== "string" || typeof source.url !== "string"))) {
        throw new Error("This backup contains invalid source references.");
      }
      if (message.drugInfo !== undefined && (!record(message.drugInfo) ||
          !["drug_overview", "pharmacodynamics", "pharmacokinetics", "toxicology_and_safety", "therapeutic_profile", "chemical_structure", "drug_name", "adme", "toxicology"].every(key => record(message.drugInfo[key])))) {
        throw new Error("This backup contains an invalid compound profile.");
      }
    }
    const doc = session.activeDocument;
    if (doc !== undefined && (!record(doc) || typeof doc.document_id !== "string" || typeof doc.filename !== "string" ||
        !Number.isInteger(doc.pages) || !Number.isInteger(doc.chunks))) throw new Error("This backup contains an invalid paper selection.");
  }
  return value as ChatSession[];
}

export function parseNotebookBackup(text: string): ChatSession[] {
  const backup: unknown = JSON.parse(text);
  if (!record(backup) || backup.format !== "pharmind-notebooks" || backup.version !== 1) {
    throw new Error("Choose a Pharmind notebook backup (version 1).");
  }
  return validateNotebooks(backup.notebooks);
}

export function mergeNotebooks(current: ChatSession[], incoming: ChatSession[]): ChatSession[] {
  const merged = new Map(current.map(session => [session.id, session]));
  for (const session of incoming) {
    const existing = merged.get(session.id);
    if (!existing || session.updatedAt > existing.updatedAt) merged.set(session.id, session);
  }
  return [...merged.values()].sort((a, b) => b.updatedAt - a.updatedAt);
}
