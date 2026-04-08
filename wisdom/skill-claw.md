---
name: wisdom
description: accumulative Neo4j-native DIKW wisdom memory — absorb any input, merge into persistent graph, ask questions that traverse Knowledge→Experience→Insight→Wisdom
trigger: /wisdom
---

# /wisdom (OpenClaw)

Same as the Claude Code skill but uses sequential extraction (OpenClaw does not yet support parallel subagents).

All commands and pipeline steps are identical to skill.md. The only difference:
- Extract files sequentially, not in parallel batches
- Use the Bash tool to run `python3 -m wisdom <cmd>` for CLI operations
- Write AGENTS.md instead of CLAUDE.md for always-on integration

See `skill.md` for the full pipeline documentation.

## Install for OpenClaw

```bash
pip install wisdomgraph && wisdom install --platform claw
```

Then in your project:
```bash
wisdom claw install   # writes wisdomGraph section to AGENTS.md
```

## Always-on (AGENTS.md)

After running `wisdom claw install`, your AGENTS.md will contain:

```markdown
## wisdomGraph

This project uses wisdomGraph — accumulative Neo4j-native wisdom memory.

Rules:
- Before answering architecture or codebase questions, read wisdom-out/WISDOM_REPORT.md
- Use the wisdom CLI to query the graph: wisdom ask "your question"
```

OpenClaw reads AGENTS.md before every session — the wisdom graph is always-on.
