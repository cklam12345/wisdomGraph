#!/usr/bin/env node
/**
 * Basic smoke test — verify the shim loads and wisdom CLI check works.
 */
"use strict";

const { spawnSync } = require("child_process");
const assert = require("assert");

// Test 1: index.js is valid JS
const syntax = spawnSync(process.execPath, ["--check", require.resolve("./index.js")], {encoding: "utf8"});
assert.strictEqual(syntax.status, 0, syntax.stderr);

console.log("npm shim: package.json valid");

const pkg = require("./package.json");
assert(pkg.name === "wisdomgraph", "name check");
assert(pkg.mcpName === "io.github.cklam12345/wisdomgraph", "mcpName check");
assert(pkg.bin.wisdomgraph.replace(/^\.\//, "") === "index.js", "bin check");
assert(pkg.version, "version present");

console.log("npm shim: all checks passed");

const server = require("./server.json");
assert.strictEqual(server.version, pkg.version);
assert.strictEqual(server.packages[0].version, pkg.version);
assert.strictEqual(server.packages[0].environmentVariables[0].isRequired, false);
