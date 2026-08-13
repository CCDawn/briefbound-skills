#!/usr/bin/env node

const { spawnSync } = require("node:child_process");
const path = require("node:path");

function findPython() {
  const candidates = process.platform === "win32" ? ["py", "python"] : ["python3", "python"];
  for (const candidate of candidates) {
    const result = spawnSync(candidate, ["--version"], { stdio: "ignore", shell: false });
    if (result.status === 0) {
      return candidate;
    }
  }
  return null;
}

const python = findPython();
if (!python) {
  console.error("No Python runtime found. Install Python or run the script directly.");
  process.exit(1);
}

const scriptPath = path.resolve(__dirname, "..", "scripts", "init_project_memory.py");
const args = process.argv.slice(2);
const pythonArgs = python === "py" ? ["-3", scriptPath, ...args] : [scriptPath, ...args];
const result = spawnSync(python, pythonArgs, { stdio: "inherit", shell: false });
process.exit(result.status ?? 1);
