#!/usr/bin/env node
/**
 * wisdomGraph npm shim — spawns the Python MCP server over stdio.
 *
 * This package is a thin wrapper. All logic lives in the Python package:
 *   pip install 'wisdomgraph[mcp]'
 *
 * Usage (via MCP client config):
 *   { "command": "npx", "args": ["wisdomgraph"] }
 *
 * Or after npm install -g wisdomgraph:
 *   { "command": "wisdomgraph" }
 */

"use strict";

const { spawn, spawnSync } = require("child_process");

// ── Check Python wisdom CLI is available ──────────────────────────────────────

function checkWisdom() {
  const result = spawnSync("wisdom", ["--help"], { stdio: "pipe" });
  return result.status === 0 || result.error === undefined && result.status !== null;
}

function checkPip() {
  const cmds = ["pip", "pip3", "python -m pip", "python3 -m pip"];
  for (const cmd of cmds) {
    const parts = cmd.split(" ");
    const r = spawnSync(parts[0], parts.slice(1).concat(["--version"]), { stdio: "pipe" });
    if (r.status === 0) return cmd;
  }
  return null;
}

if (!checkWisdom()) {
  process.stderr.write(
    [
      "error: wisdomGraph Python package not found.",
      "",
      "Install it first:",
      "  pip install 'wisdomgraph[mcp]'",
      "",
      "Then configure your Neo4j connection:",
      "  wisdom docker up                          # local DozerDB",
      "  wisdom connect bolt://localhost:7687 \\",
      "    --user neo4j --password password",
      "",
    ].join("\n")
  );
  process.exit(1);
}

// ── Spawn wisdom mcp over stdio ───────────────────────────────────────────────

const child = spawn("wisdom", ["mcp"], {
  stdio: "inherit",   // pass stdin/stdout/stderr straight through — MCP over stdio
  env: process.env,
});

child.on("error", (err) => {
  process.stderr.write(`wisdomgraph: failed to start: ${err.message}\n`);
  process.exit(1);
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
  } else {
    process.exit(code ?? 0);
  }
});

// Forward signals to child
for (const sig of ["SIGINT", "SIGTERM", "SIGHUP"]) {
  process.on(sig, () => child.kill(sig));
}
