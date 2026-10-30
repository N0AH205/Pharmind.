const { cpSync, mkdirSync } = require("node:fs");
const path = require("node:path");

const destination = path.join(__dirname, "../public/jsme");
mkdirSync(destination, { recursive: true });
cpSync(path.dirname(require.resolve("jsme-editor/package.json")), destination, { recursive: true });
cpSync(path.join(__dirname, "../vendor/jsme"), destination, { recursive: true });
