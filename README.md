# wisdomGraph

[English](README.md) | [简体中文](README.zh-CN.md)

[![PyPI](https://img.shields.io/pypi/v/wisdomgraph)](https://pypi.org/project/wisdomgraph/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Neo4j](https://img.shields.io/badge/Neo4j-native-008CC1?logo=neo4j)](https://neo4j.com)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-MCP-blueviolet)](https://claude.ai/code)
[![Codex](https://img.shields.io/badge/Codex-MCP-black)](https://openai.com/codex)
[![OpenClaw](https://img.shields.io/badge/OpenClaw-skill-orange)](https://openclaw.ai)

> **Graph-native persistent cognition for AI agents.**
>
> **graphify gives you a snapshot. wisdomGraph gives you memory that compounds.**

Use wisdomGraph from Claude Code, Codex, OpenClaw, or any MCP host. Feed it your codebases, notes, papers, conversations — every run **merges** into a living Neo4j graph. The graph doesn't reset. It accumulates. Facts become patterns. Patterns become insights. Insights become wisdom.

```
/wisdom .                      # absorb this project into the wisdom graph
/wisdom ask "what patterns repeat across all my projects?"
/wisdom reflect                # promote insights → wisdom, close the feedback loop
```

---

## The step function over graphify

graphify is excellent at what it does: turn a folder into a knowledge graph snapshot. One run, one `graph.json`, one `GRAPH_REPORT.md`. Read it. Next session, start over.

wisdomGraph does something fundamentally different.

| | graphify | wisdomGraph |
|---|---|---|
| **Storage** | `graph.json` file (per-project) | Neo4j (persistent, all projects) |
| **Node types** | flat (code entities, concepts) | typed DIKW: Knowledge / Experience / Insight / Wisdom |
| **Runs** | snapshot, overwrites | MERGE — each run grows the graph |
| **Query** | read GRAPH_REPORT.md | live Cypher traversal at inference time |
| **Memory** | resets each session | accumulates across sessions, projects, months |
| **Reasoning** | community detection (topology) | graph path traversal + DIKW hierarchy |
| **Feedback loop** | none | Wisdom → Knowledge (neuroplasticity) |
| **Database** | none required | Neo4j Aura (free) or DozerDB Docker |

The difference is not incremental. It's architectural. graphify compresses a codebase into a readable report. wisdomGraph builds an artificial epistemology — one that remembers, connects, and grows.

---

## The DIKW pyramid, operationalized

Human experts don't store flat facts. They organize experience into layers:

```
Wisdom    ← actionable principles derived from patterns
  ↑
Insight   ← patterns detected across multiple experiences
  ↑
Experience ← events, decisions, outcomes with context
  ↑
Knowledge ← verified facts, documented behaviors, extracted structure
```

Every node in the wisdomGraph carries a `tier` label. The graph topology **is** the cognitive architecture. When you ask a question, Cypher traverses upward through the tiers — not keyword-matching flat text, but reasoning across lived experience.

The feedback loop is critical: when a Wisdom node is queried and found useful, it reinforces connected Knowledge nodes. The graph learns what matters.

---

## Install

**Requires:** Python 3.10+ and one of: [Claude Code](https://claude.ai/code), [Codex](https://openai.com/codex), [OpenClaw](https://openclaw.ai), or another MCP host

**And one of:** [Neo4j Aura Free](https://neo4j.com/cloud/platform/aura-graph-database/) (cloud, no install) or [DozerDB](https://dozerdb.org) (local Docker, APOC included)

```bash
pip install 'wisdomgraph[mcp]'
wisdom quickstart
```

`wisdom quickstart` is the end-to-end first-time setup. It prepares storage, verifies the Neo4j connection, and registers wisdomGraph with detected MCP hosts.

```bash
# Local managed Neo4j/DozerDB backend + detected MCP hosts
wisdom quickstart

# Local backend + Codex only
wisdom quickstart --host codex

# Existing Neo4j or DozerDB instance
wisdom quickstart --storage existing --uri bolt://localhost:7689 --user neo4j --password <password>

# Neo4j Aura
wisdom quickstart --storage aura --uri bolt+s://xxxxxxxx.databases.neo4j.io --user neo4j --password <password>
```

The MCP server itself never starts Docker or creates databases. Storage setup is explicit through `quickstart`, `local`, `docker`, or `connect`.

### Option A — Managed local backend (recommended first run)

```bash
wisdom local up
wisdom doctor
```

This starts a managed DozerDB/Neo4j container named `wisdomgraph-neo4j`, stores data under `~/.wisdom/neo4j`, generates a local password, saves the connection, and leaves MCP startup cleanly separate.

Useful commands:

```bash
wisdom local status
wisdom local logs
wisdom local down
```

### Option B — Neo4j Aura (zero local database)

1. Create a free account at [neo4j.com/cloud/aura](https://neo4j.com/cloud/aura)
2. Create a free AuraDB instance — copy the connection URI and password
3. Run:

```bash
wisdom connect bolt+s://xxxxxxxx.databases.neo4j.io --user neo4j --password <your-password>
```

Free tier: 200,000 nodes. Enough for years of accumulated wisdom.

### Option C — Legacy/manual DozerDB Docker (full control, APOC included)

```bash
wisdom docker up        # pulls graphstack/dozerdb:5.26.3.0 and starts it
wisdom connect bolt://localhost:7687 --user neo4j --password password
```

Or manually:

```bash
docker run -d \
  -p 7474:7474 -p 7687:7687 \
  -v $HOME/neo4j-wisdom/data:/data \
  -v $HOME/neo4j-wisdom/logs:/logs \
  --env NEO4J_AUTH=neo4j/password \
  --env NEO4J_PLUGINS='["apoc"]' \
  graphstack/dozerdb:5.26.3.0
```

Open [localhost:7474](http://localhost:7474) — Neo4j Browser is your visual window into the wisdom graph.

---

## Platform support

| Platform | Install command |
|----------|----------------|
| Claude Code (Linux/Mac) | `wisdom install` |
| Claude Code MCP | `wisdom mcp-install` |
| Codex MCP | `wisdom mcp-install --host codex` |
| Claude Code (Windows) | `wisdom install --platform windows` |
| OpenClaw | `wisdom install --platform claw` |

Then open your AI coding assistant and type:

```
/wisdom .
```

---

## MCP integration (v0.2.0+)

wisdomGraph ships as a native **Model Context Protocol (MCP) server**. Once registered, Claude, Codex, or another MCP host can call wisdomGraph tools directly — no `/wisdom` slash command needed.

### Claude Code setup

```bash
wisdom mcp-install
```

This writes the MCP server entry to `.claude/settings.json` in your current project:

```json
{
  "mcpServers": {
    "wisdomGraph": {
      "command": "wisdom",
      "args": ["mcp"]
    }
  }
}
```

Restart Claude Code. wisdomGraph is now live in that project.

### Codex setup (v0.3.0+)

```bash
wisdom mcp-install --host codex
```

This runs the Codex MCP registration:

```bash
codex mcp add wisdomGraph -- wisdom mcp
```

Start a new Codex session. Codex can now launch `wisdom mcp` and use the same Neo4j-backed DIKW graph as Claude Code.

### MCP tools

| Tool | What agents use it for |
|---|---|
| `wisdom_ingest` | Absorb a file, directory, or URL into Neo4j |
| `wisdom_remember` | Store a fact, decision, or insight explicitly |
| `wisdom_learn` | Record an attempt, outcome, and lesson learned |
| `wisdom_status` | Read DIKW tier counts and edge/source totals |
| `wisdom_list` | List nodes by DIKW tier, project, and connectivity |
| `wisdom_trace` | Trace why an insight or wisdom node exists |
| `wisdom_explain` | Explain a node with its DIKW chain and sources |
| `wisdom_query` | Run a read-only Cypher traversal |
| `wisdom_reflect` | Trigger DIKW promotion pipeline |
| `wisdom_report` | Get tier counts + top Wisdom nodes as markdown |

### Example — Claude remembering across sessions

**Session 1:**
> Claude calls `wisdom_remember` with label *"DozerDB ignores NEO4J_AUTH if data dir exists"*, tier *experience*.

**Session 2 (days later, fresh terminal):**
> You ask "how do I reset DozerDB credentials?"
> Claude calls `wisdom_query` → finds the Experience node → answers from your own history.

The graph remembered. Claude didn't forget.

### Global vs project MCP install

```bash
# Register for the current project only
wisdom mcp-install

# Register globally (all projects on this machine)
wisdom mcp-install --project ~

# Register globally with Codex
wisdom mcp-install --host codex
```

---

## Usage

```
/wisdom                              # absorb current directory
/wisdom ./raw                        # absorb a specific folder
/wisdom ./raw --mode deep            # aggressive INFERRED edge extraction
/wisdom ./raw --update               # re-absorb only changed files, MERGE into graph
/wisdom ./raw --tier knowledge       # force all extractions into Knowledge tier only

/wisdom add https://arxiv.org/abs/1706.03762   # absorb a paper
/wisdom add https://x.com/...                  # absorb a tweet thread
/wisdom add https://...  --author "Name"        # tag the source author

/wisdom ask "what patterns repeat across all my projects?"
/wisdom ask "what do I know about authentication flows?"
/wisdom ask "trace the path from attention to optimizer"
/wisdom ask "..." --tier wisdom      # only traverse Wisdom-tier nodes in answer

/wisdom reflect                      # LLM promotion pass: Knowledge→Experience→Insight→Wisdom
/wisdom reflect --project ./raw      # reflect only on nodes from this corpus

/wisdom path "DigestAuth" "OAuth"    # shortest path between two concepts
/wisdom explain "CausalSelfAttention"  # full DIKW context for a node
/wisdom god-nodes                    # highest-degree concepts across all projects

/wisdom export --cypher              # dump all nodes/edges as Cypher CREATE statements
/wisdom export --json                # export to graph.json (graphify-compatible)
/wisdom export --obsidian            # export to Obsidian vault

/wisdom status                       # graph stats: node counts by tier, edge counts, last update
/wisdom purge --project ./raw        # remove nodes from one corpus, touch nothing else
```

---

## How wisdom accumulates

**Run 1** — absorb your auth library:
```
Knowledge: JWT, session tokens, cookie flags, PKCE flow
Experience: (none yet — single source)
```

**Run 2** — absorb a different project's auth:
```
Knowledge: JWT, PKCE — MERGE deduplicates, adds a source link
Experience: two implementations, same pattern detected
Insight: JWT + PKCE is the converged pattern in your work
```

**Run 3** — `/wisdom reflect`:
```
Wisdom: "Use stateless JWT for APIs, PKCE for browser flows.
         Shipped this pattern across 3 projects without incident."
```

**Run 4** — `/wisdom ask "how should I handle auth in this new service?"`:
```
Traversal: Knowledge → Experience → Insight → Wisdom
Answer: your own battle-tested principle, grounded in your actual history
```

This is not RAG. This is not summarization. This is the graph traversing your accumulated experience to return *your own wisdom back to you*.

---

## Graph schema

```cypher
// DIKW node labels
(:Knowledge  {id, label, content, source_file, confidence, timestamp, project})
(:Experience {id, label, content, context, outcome, timestamp, project})
(:Insight    {id, label, content, pattern_strength, source_count, timestamp})
(:Wisdom     {id, label, principle, confidence, reinforcement_count, timestamp})

// Relationships
(Knowledge)-[:GROUNDS]->(Experience)
(Experience)-[:REVEALS]->(Insight)
(Insight)-[:CRYSTALLIZES_INTO]->(Wisdom)
(Wisdom)-[:REINFORCES]->(Knowledge)           // feedback loop — the graph learns

(Knowledge)-[:SEMANTICALLY_SIMILAR_TO]->(Knowledge)
(Insight)-[:CONTRADICTS]->(Insight)           // tension surfaces, needs reflection
(any)-[:SOURCED_FROM]->(Source {uri, author, ingested_at})

// Cross-agent composite index
CREATE INDEX wisdom_composite IF NOT EXISTS
FOR (n:Knowledge|Experience|Insight|Wisdom)
ON (n.id, n.timestamp, n.confidence)
```

Confidence flows through the graph. An Insight grounded in 8 Experiences has higher `pattern_strength` than one from 2. Wisdom nodes track `reinforcement_count` — how many traversals confirmed the principle.

---

## What you get

**Cross-project god nodes** — concepts central across *all* your projects and corpora, not just one repo.

**Contradiction detection** — two Insights pointing in opposite directions surface as `CONTRADICTS` edges. The graph shows the conflict; you resolve it into better Wisdom.

**Temporal decay** — nodes carry timestamps. Old Knowledge not reinforced by recent Experience gets flagged. The graph ages gracefully, like expert memory.

**Full provenance chain** — every node links back to its `Source`. `/wisdom explain "node"` returns the full DIKW path: fact → context → pattern → principle.

**The "why" chain** — not just *what* but *why it matters*, extracted from docstrings, `# NOTE:` comments, design rationale in docs, and the DIKW promotion reasoning.

---

## Deployment options

| | Aura Free | DozerDB Local |
|---|---|---|
| **Setup** | 3 clicks + URI | 1 docker command |
| **Cost** | Free (200K nodes) | Free forever |
| **APOC** | Available | Included |
| **Data location** | Neo4j cloud | Your machine |
| **Visual browser** | neo4j.com console | localhost:7474 |
| **Best for** | Quick start, individuals | Teams, air-gap, full control |

---

## Privacy

wisdomGraph sends file contents to your AI coding assistant's model API for semantic extraction — Anthropic (Claude Code) or whichever provider your platform uses. Code files are processed locally via tree-sitter AST. All graph data lives in *your* Neo4j instance (Aura or local). No telemetry, no usage tracking, no analytics.

---

## Tech stack

Neo4j (Aura or DozerDB) + tree-sitter + APOC. Semantic extraction via Claude (Claude Code) or your platform's model. The graph database is the intelligence layer — traversal, path-finding, and community detection run natively in Cypher via Neo4j GDS (Graph Data Science library). MCP integration via the [Model Context Protocol](https://modelcontextprotocol.io) Python SDK.

---

<details>
<summary>Contributing</summary>

**Worked examples** are the highest-trust contribution. Run `/wisdom` on a real multi-project corpus, let it reflect a few times, document what Wisdom nodes emerged and whether they match your intuition. Submit to `worked/{slug}/`.

**Schema proposals** — have a relationship type that captures something the current schema misses? Open an issue with the Cypher pattern and a worked example.

**DIKW promotion heuristics** — better prompts or rules for when to promote Knowledge → Experience → Insight → Wisdom. The promotion logic is the heart of the system.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full pipeline design, Cypher schemas, and how to extend the tiers.

</details>
