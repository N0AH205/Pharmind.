const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const ts = require("typescript");

// Compile the pure application helpers with the project's existing TypeScript compiler.
function load(name) {
  const source = fs.readFileSync(path.join(__dirname, "../lib", `${name}.ts`), "utf8");
  const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } });
  const compiled = { exports: {} };
  new Function("module", "exports", outputText)(compiled, compiled.exports);
  return compiled.exports;
}

const { normalizeChatCitations } = load("citations");
const { parseNotebookBackup, validateNotebooks, mergeNotebooks } = load("notebooks");
const { readEvents } = load("events");
const { selectedOllamaModel, ollamaModelWarning } = load("ollamaModels");
const paper = { document_id: "paper-1", filename: "trial.pdf", pages: 2, chunks: 3 };
const notebook = { id: "notebook-1", title: "Trial findings", createdAt: 1, updatedAt: 2, messages: [], activeDocument: paper, mode: "paper_learning" };

test("PDF references survive without external URLs and unknown markers are removed", () => {
  const source = { id: "SOURCE_4", num: 1, name: "trial.pdf p.2", text: "The retrieved passage", url: "" };
  const result = normalizeChatCitations("Result [SOURCE_4]. Unknown [99].", [source]);
  assert.equal(result.text, "Result [1]. Unknown .");
  assert.equal(result.sources[0].text, source.text);
});

test("citations reject unsafe schemes and preserve local PDF links", () => {
  const result = normalizeChatCitations("[1, 2]", [
    { id: "SOURCE_1", num: 1, name: "Bad", url: "javascript:alert(1)" },
    { id: "SOURCE_2", num: 2, name: "Paper", url: "/api/documents/abc/file#page=2" },
  ]);
  assert.equal(result.sources[0].url, "");
  assert.equal(result.sources[1].url, "/api/documents/abc/file#page=2");
});

test("notebook backup restores the active paper and merges the newer notebook", () => {
  const imported = parseNotebookBackup(JSON.stringify({ format: "pharmind-notebooks", version: 1, notebooks: [notebook] }));
  assert.deepEqual(imported[0].activeDocument, paper);
  const merged = mergeNotebooks([{ ...notebook, updatedAt: 1 }], imported);
  assert.equal(merged.length, 1);
  assert.equal(merged[0].updatedAt, 2);
  assert.equal(mergeNotebooks([notebook], [{ ...notebook, updatedAt: 1 }])[0].updatedAt, 2);
});

test("invalid backups and duplicate notebook IDs are rejected before state changes", () => {
  assert.throws(() => parseNotebookBackup('{"format":"other","version":1}'));
  assert.throws(() => validateNotebooks([notebook, notebook]));
  assert.throws(() => validateNotebooks([{ ...notebook, messages: [{ role: "script" }] }]));
  assert.throws(() => validateNotebooks([{ ...notebook, activeDocument: { filename: "missing ID" } }]));
});

test("SSE handles byte boundaries, Unicode, CRLF and an unterminated final frame", async () => {
  const bytes = new TextEncoder().encode('data: {"type":"token","content":"café"}\r\n\r\ndata:{"type":"result","data":{"ok":true}}');
  const stream = new ReadableStream({ start(controller) { for (const byte of bytes) controller.enqueue(new Uint8Array([byte])); controller.close(); } });
  const events = [];
  await readEvents(stream, event => events.push(event));
  assert.equal(events[0].content, "café");
  assert.equal(events[1].data.ok, true);
});

test("malformed stream events fail visibly instead of being silently swallowed", async () => {
  const stream = new ReadableStream({ start(controller) { controller.enqueue(new TextEncoder().encode("data: invalid\n\n")); controller.close(); } });
  await assert.rejects(readEvents(stream, () => undefined), SyntaxError);
});

test("installed model matching accepts latest aliases and flags the missing default", () => {
  const models = [{ name: "qwen2.5:7b", can_chat: true }, { name: "custom:latest", can_chat: null }];
  assert.equal(selectedOllamaModel(models, "custom").name, "custom:latest");
  assert.equal(ollamaModelWarning(models, "qwen2.5:7b"), "");
  assert.match(ollamaModelWarning(models, "qwen2.5:3b"), /not installed/);
});

test("model notices distinguish no models from embedding-only installations", () => {
  assert.match(ollamaModelWarning([], "qwen2.5:3b"), /no models/);
  const embedding = { name: "nomic-embed-text:latest", can_chat: false };
  assert.match(ollamaModelWarning([embedding], embedding.name), /cannot generate answers/);
  assert.match(ollamaModelWarning([embedding, { name: "qwen2.5:7b", can_chat: true }], embedding.name), /cannot generate answers/);
});
