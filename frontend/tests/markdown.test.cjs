const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const ts = require("typescript");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");

function compile(file, dependencies = {}) {
  const source = fs.readFileSync(path.join(__dirname, "..", file), "utf8");
  const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 } });
  const compiled = { exports: {} };
  new Function("module", "exports", "require", outputText)(compiled, compiled.exports, name => dependencies[name] || require(name));
  return compiled.exports;
}

const { normalizeChatMarkdown } = compile("lib/markdown.ts");
async function render(text, sources = []) {
  const Markdown = await import("react-markdown");
  const { default: FormattedProse } = compile("components/FormattedProse.tsx", {
    "react-markdown": Markdown,
    "@/lib/markdown": { normalizeChatMarkdown },
    "./ChatInterface.module.css": { default: {} },
  });
  return renderToStaticMarkup(React.createElement(FormattedProse, { text, sources, onSource() {} }));
}

test("inline Unicode bullets from older answers render as separate list items", async () => {
  const html = await render('The study identified these findings: • **Patient-reported factors**: First finding. • **Mixed methods**: Second finding. • **Study limitations**: Third finding.\n\nA separate concluding paragraph.');
  assert.equal((html.match(/<li>/g) || []).length, 3);
  assert.match(html, /<ul>/);
  assert.match(html, /<li><strong>Mixed methods<\/strong>: Second finding\./);
  assert.match(html, /<\/ul>\s*<p>A separate concluding paragraph\./);
});

test("ordered and nested lists preserve numbering and citation controls", async () => {
  const html = await render('3. First result [1]\n4. Second result\n   - A nested limitation [1]', [{ num: 1, name: "trial.pdf", url: "", id: "SOURCE_1" }]);
  assert.match(html, /<ol start="3">/);
  assert.equal((html.match(/<li>/g) || []).length, 3);
  assert.match(html, /<ul>/);
  assert.equal((html.match(/title="View source 1: trial.pdf"/g) || []).length, 2);
});

test("inline consecutive numbered bold items become an ordered list", async () => {
  const html = await render('1. **Design**: A cohort. 2. **Findings**: An association. 3. **Limits**: Confounding.');
  assert.match(html, /<ol>/);
  assert.equal((html.match(/<li>/g) || []).length, 3);
});

test("scientific punctuation, decimal values and code remain unchanged", () => {
  const source = 'Patient-reported outcomes at 1.5 mg; 95% CI 1.1–2.3.\n\n`literal • marker`\n\n```text\n• example\n1. **literal** 2. **literal**\n```';
  assert.equal(normalizeChatMarkdown(source), source);
});

test("Markdown renders headings and emphasis without executing HTML or loading images", async () => {
  const html = await render('### Findings\n\nA **supported** finding.\n\n<script>alert(1)</script>\n\n![remote image](https://outside.example/image.png)\n\n[Link](javascript:alert(1))');
  assert.match(html, /<h4>Findings<\/h4>/);
  assert.match(html, /<strong>supported<\/strong>/);
  assert.doesNotMatch(html, /<script|<img|href=/);
});
