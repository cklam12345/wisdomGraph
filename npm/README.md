# wisdomGraph

> Accumulative Neo4j-native DIKW memory for Claude Code — permanent knowledge across sessions.

[![PyPI](https://img.shields.io/pypi/v/wisdomgraph)](https://pypi.org/project/wisdomgraph/)
[![npm](https://img.shields.io/npm/v/wisdomgraph)](https://www.npmjs.com/package/wisdomgraph)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)

This is the **npm shim** for wisdomGraph. All logic lives in the Python package.

## Quick start

```bash
# 1. Install Python package
pip install 'wisdomgraph[mcp]'

# 2. Create embedded storage and register MCP (no Docker)
wisdom quickstart
```

## MCP config (via npx)

```json
{
  "mcpServers": {
    "wisdomGraph": {
      "command": "npx",
      "args": ["wisdomgraph"]
    }
  }
}
```

## What it does

wisdomGraph gives Claude Code permanent, accumulative memory backed by embedded Relate by Neo4j, with optional Neo4j Aura support.

MCP tools include:
- `wisdom_storage` — inspect or switch Relate, Neo4j/Aura, and managed Docker storage
- `wisdom_ingest` — absorb files, directories, or URLs
- `wisdom_remember` — store facts, decisions, insights explicitly
- `wisdom_query` — read-only Cypher traversal
- `wisdom_reflect` — DIKW promotion pipeline
- `wisdom_report` — tier counts + top Wisdom nodes

The graph never resets. Every session compounds.

## Links

- **GitHub:** https://github.com/cklam12345/wisdomGraph
- **PyPI:** https://pypi.org/project/wisdomgraph/
- **Docs:** https://github.com/cklam12345/wisdomGraph#readme
