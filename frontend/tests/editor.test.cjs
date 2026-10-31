const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function editorBridge() {
  const html = fs.readFileSync(path.join(__dirname, "../public/editor.html"), "utf8");
  const source = html.match(/<script type="text\/javascript">([\s\S]*?)<\/script>/)[1];
  const messages = [];
  const callbacks = {};
  let receive;
  let smiles = "";
  const editor = {
    setCallBack: (name, callback) => { callbacks[name] = callback; },
    readGenericMolecularInput: value => { smiles = value; },
    reset: () => { smiles = ""; },
    smiles: () => smiles,
  };
  const parent = { postMessage: message => {
    if (message.type === "JSME_READY") assert.equal(typeof callbacks.AfterStructureModified, "function");
    messages.push(message);
  } };
  const window = { parent, location: { origin: "http://localhost:3001" }, addEventListener: (_, callback) => { receive = callback; } };
  const context = vm.createContext({ window, JSApplet: { JSME: function () { return editor; } }, console });
  vm.runInContext(source, context);
  context.jsmeOnLoad();
  return { messages, callbacks, send: (smiles, overrides = {}) => receive({ origin: window.location.origin, source: parent, data: { type: "SET_SMILES", smiles }, ...overrides }) };
}

test("editor registers changes before reporting ready and returns loaded SMILES", () => {
  const bridge = editorBridge();
  assert.equal(bridge.messages[0].type, "JSME_READY");
  bridge.send("c1ccccc1");
  assert.equal(bridge.messages.at(-1).smiles, "c1ccccc1");
  bridge.callbacks.AfterStructureModified();
  assert.equal(bridge.messages.at(-1).type, "JSME_SMILES");
});

test("clearing the editor reports an empty structure", () => {
  const bridge = editorBridge();
  bridge.send("CCO");
  bridge.send("");
  assert.equal(bridge.messages.at(-1).smiles, "");
});

test("editor ignores commands from another origin or window", () => {
  const bridge = editorBridge();
  bridge.send("CCO", { origin: "https://outside.example" });
  bridge.send("CCO", { source: {} });
  assert.equal(bridge.messages.length, 1);
});
