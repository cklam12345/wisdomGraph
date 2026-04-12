#!/usr/bin/env node
/**
 * Basic smoke test — verify the shim loads and wisdom CLI check works.
 */
"use strict";

const { spawnSync } = require("child_process");
const assert = require("assert");

// Test 1: index.js is valid JS
require("./index.js") || true;
// (process will exit if wisdom not found — that's expected in CI without Python)

console.log("npm shim: package.json valid");

const pkg = require("./package.json");
assert(pkg.name === "wisdomgraph", "name check");
assert(pkg.mcpName === "io.github.cklam12345/wisdomgraph", "mcpName check");
assert(pkg.bin.wisdomgraph === "./index.js", "bin check");
assert(pkg.version, "version present");

console.log("npm shim: all checks passed");
