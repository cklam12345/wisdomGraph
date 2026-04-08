# Architecture

wisdomGraph is a Claude Code / OpenClaw skill backed by a Python library and a Neo4j graph database. The skill orchestrates the library. The library can be used standalone. The database is the memory.

---

## Core principle

**The graph topology is isomorphic to the reasoning process.**

graphify stores flat nodes in NetworkX. wisdomGraph stores typed nodes in Neo4j where the node label *is* its epistemic role. The database structure mirrors how expert cognition organizes knowledge — not as a metaphor, but as a functional constraint on what Cypher queries can express.

---

## Pipeline

```
detect()
  → extract()          (AST for code, LLM subagents for docs/papers/images)
  → classify()         (DIKW tier assignment)
  → merge_to_neo4j()   (MERGE — deduplicates, links sources, updates confidence)
  → reflect()          (optional: LLM promotion pass up the DIKW hierarchy)
  → traverse()         (Cypher: answer queries by walking the graph)
  → report()           (WISDOM_REPORT.md + browser query)
```

Each stage is a single function in its own module. They communicate through plain Python dicts and Neo4j driver sessions — no shared state, no side effects outside the graph and `wisdom-out/`.

---

## Module responsibilities

| Module | Function | Input → Output |
|--------|----------|----------------|
| `detect.py` | `collect_files(root)` | directory → `[Path]` filtered list |
| `extract.py` | `extract(path)` | file path → `{nodes, edges}` dict |
| `classify.py` | `classify(nodes, edges)` | extraction dict → DIKW-typed dict |
| `merge.py` | `merge_to_neo4j(session, data)` | typed dict → Neo4j MERGE transactions |
| `reflect.py` | `reflect(session, project=None)` | Neo4j session → promotion Cypher writes |
| `traverse.py` | `traverse(session, query)` | natural language → Cypher → result |
| `report.py` | `render_report(session)` | Neo4j session → WISDOM_REPORT.md string |
| `export.py` | `export(session, out_dir, format)` | session → Cypher dump / graph.json / Obsidian |
| `ingest.py` | `ingest(url, ...)` | URL → file saved to corpus dir |
| `cache.py` | `check_semantic_cache / save_semantic_cache` | files → (cached, uncached) split |
| `security.py` | validation helpers | URL / path / label → validated or raises |
| `validate.py` | `validate_extraction(data)` | extraction dict → raises on schema errors |
| `connect.py` | `connect(uri, user, password)` | credentials → Neo4j driver, saved to config |
| `docker.py` | `docker_up() / docker_down()` | — → subprocess docker commands |

---

## Neo4j schema

### Node labels (DIKW tiers)

```cypher
(:Knowledge {
  id:            string,   // SHA256 of (label + source_file)
  label:         string,   // human name
  content:       string,   // extracted text / docstring / description
  source_file:   string,   // origin file path
  source_loc:    string,   // "L42" or "p.7"
  confidence:    float,    // 0.0–1.0 (EXTRACTED=1.0, INFERRED<1.0)
  confidence_tag: string,  // "EXTRACTED" | "INFERRED" | "AMBIGUOUS"
  project:       string,   // root path or corpus slug
  timestamp:     datetime,
  access_count:  integer   // incremented on each traversal hit
})

(:Experience {
  id:              string,
  label:           string,
  content:         string,
  context:         string,  // what was happening when this was observed
  outcome:         string,  // what resulted
  project:         string,
  timestamp:       datetime,
  access_count:    integer
})

(:Insight {
  id:               string,
  label:            string,
  content:          string,
  pattern_strength: float,    // = source_count / max_source_count, normalized
  source_count:     integer,  // number of Experiences that revealed this
  timestamp:        datetime,
  last_reinforced:  datetime
})

(:Wisdom {
  id:                  string,
  label:               string,
  principle:           string,  // actionable statement
  confidence:          float,
  reinforcement_count: integer, // times this was returned in a traversal
  timestamp:           datetime,
  last_reinforced:     datetime
})

(:Source {
  uri:          string,  // file path or URL
  author:       string,
  contributor:  string,
  ingested_at:  datetime,
  content_hash: string   // SHA256 for cache invalidation
})
```

### Relationship types

```cypher
// DIKW hierarchy — upward flow
(Knowledge)-[:GROUNDS]->(Experience)
(Experience)-[:REVEALS]->(Insight)
(Insight)-[:CRYSTALLIZES_INTO]->(Wisdom)

// Feedback loop — the neuroplasticity mechanism
(Wisdom)-[:REINFORCES {weight: float}]->(Knowledge)

// Cross-tier lateral connections
(Knowledge)-[:SEMANTICALLY_SIMILAR_TO {confidence: float}]->(Knowledge)
(Knowledge)-[:CALLS]->(Knowledge)       // code call graph
(Knowledge)-[:IMPORTS]->(Knowledge)     // code import graph
(Knowledge)-[:CONTRADICTS]->(Knowledge) // conflict within same tier

// Cross-tier tension
(Insight)-[:CONTRADICTS]->(Insight)     // surfaces during reflect pass
(Wisdom)-[:SUPERSEDES]->(Wisdom)        // resolved contradiction, old wisdom archived

// Provenance
(Knowledge|Experience|Insight|Wisdom)-[:SOURCED_FROM]->(Source)
```

### Indexes

```cypher
// Composite index for cross-agent memory queries
CREATE INDEX wisdom_composite IF NOT EXISTS
FOR (n:Knowledge|Experience|Insight|Wisdom)
ON (n.id, n.timestamp, n.confidence)

// Full-text search index for natural language queries
CREATE FULLTEXT INDEX wisdom_content IF NOT EXISTS
FOR (n:Knowledge|Experience|Insight|Wisdom)
ON EACH [n.label, n.content, n.principle]

// Source deduplication
CREATE CONSTRAINT source_uri_unique IF NOT EXISTS
FOR (s:Source) REQUIRE s.uri IS UNIQUE
```

---

## The DIKW classification pass

After `extract()` returns the raw `{nodes, edges}` dict, `classify()` assigns each node to a DIKW tier. This is *not* post-processing — it's a structural constraint that determines what Cypher operations are legal on the node.

### Classification heuristics

**Knowledge tier** (default for first extraction of any node):
- Verified facts: function signatures, class hierarchies, import chains
- Documented behaviors: docstrings, explicit comments (`# NOTE:`, `# WHY:`)
- Extracted structure: schema fields, API endpoints, config keys

**Experience tier** (promoted from Knowledge when):
- Same concept appears in 2+ distinct projects with different implementations
- A decision node has a documented `outcome` (e.g., a commit message that explains *why* an approach was changed)
- A `CONTRADICTS` edge exists between two Knowledge nodes on the same concept

**Insight tier** (promoted from Experience when):
- A pattern appears across 3+ Experiences
- The LLM `reflect()` pass identifies a recurring theme with `pattern_strength` > 0.5
- A graph algorithm (Neo4j GDS Louvain) clusters related Experiences into a community

**Wisdom tier** (promoted from Insight when):
- `pattern_strength` > 0.7 AND `source_count` >= 3
- The LLM `reflect()` pass generates a falsifiable, actionable principle
- User explicitly promotes via `/wisdom reflect --promote <insight_id>`

### MERGE semantics

Every write to Neo4j uses `MERGE`, never `CREATE`. This is the deduplication guarantee:

```cypher
MERGE (k:Knowledge {id: $id})
ON CREATE SET k += $props, k.access_count = 0
ON MATCH SET
  k.source_file = CASE WHEN $confidence > k.confidence THEN $source_file ELSE k.source_file END,
  k.confidence  = CASE WHEN $confidence > k.confidence THEN $confidence  ELSE k.confidence  END,
  k.timestamp   = $timestamp
```

Running `/wisdom` twice on the same folder is idempotent. Running it on a new project that shares concepts with an old one *strengthens* the existing nodes (higher access_count, additional SOURCED_FROM links).

---

## The reflect() pass

`reflect()` is the promotion engine. It runs as a Claude subagent with access to the Neo4j session.

```
1. Query all Knowledge nodes with access_count >= 2 grouped by project
2. Detect cross-project duplicates → promote to Experience, write GROUNDS edges
3. Query all Experience nodes, cluster by semantic similarity
4. If cluster.size >= 3 → promote to Insight, write REVEALS edges
5. Query all Insight nodes with pattern_strength > 0.7
6. Generate Wisdom principle via LLM → MERGE Wisdom, write CRYSTALLIZES_INTO edges
7. Write REINFORCES edges from each new Wisdom back to its source Knowledge
```

The reflect pass is additive — it never deletes or overwrites. Old Knowledge nodes are not removed when they're promoted; the hierarchy of GROUNDS edges is the record of how the promotion happened.

---

## The traverse() pass

When you run `/wisdom ask "..."`, the traversal is:

```
1. Full-text search on wisdom_content index → candidate node IDs
2. For each candidate:
   - Walk up: (candidate)-[:GROUNDS|REVEALS|CRYSTALLIZES_INTO*1..3]->(Wisdom)
   - Walk down: (Wisdom)-[:REINFORCES]->(Knowledge) to get grounding facts
3. Score results by: tier rank × confidence × reinforcement_count × recency
4. Return top-k Wisdom nodes with their full DIKW provenance chains
5. Increment access_count on all traversed nodes
```

This is fundamentally different from RAG chunking. The traversal is path-aware — it knows that a Wisdom principle is only as strong as the Insight it crystallized from, which is only as strong as the Experiences that revealed it.

---

## The feedback loop

Every time a Wisdom node is returned in a traversal, `reinforcement_count` is incremented. At `reinforcement_count >= 5`, a `REINFORCES` edge is written back to the Knowledge nodes that grounded the Wisdom path.

This edge has a `weight` property that increases with reinforcement. Future traversals use this weight to surface the most battle-tested Knowledge nodes first.

```cypher
MATCH (w:Wisdom {id: $wisdom_id})-[:CRYSTALLIZES_INTO*1..3]-(k:Knowledge)
MERGE (w)-[r:REINFORCES]->(k)
ON CREATE SET r.weight = 1.0
ON MATCH SET r.weight = r.weight + 0.1
```

The graph literally learns what it knows. Knowledge that supports durable Wisdom grows stronger; orphaned facts decay (tracked by `last_reinforced`).

---

## Confidence propagation

Confidence flows upward through the DIKW hierarchy at promotion time:

```python
# Experience confidence = mean(Knowledge.confidence) for all grounding Knowledge nodes
experience.confidence = mean([k.confidence for k in grounds_knowledge])

# Insight pattern_strength = min(experience.confidence) * log(source_count) / log(10)
insight.pattern_strength = min(exp.confidence) * math.log10(source_count)

# Wisdom confidence = insight.pattern_strength * (1 - decay_factor(days_since_reinforced))
wisdom.confidence = insight.pattern_strength * decay(wisdom.last_reinforced)
```

A Wisdom node with `confidence < 0.3` is surfaced in WISDOM_REPORT.md as a "fragile principle" — it needs more Experience to strengthen it.

---

## Skill interface design

The Claude Code / OpenClaw skill (`skill.md`) is the entry point for all user-facing commands. It:

1. Parses the `/wisdom <args>` invocation
2. Reads the connection config from `~/.wisdom/config.json`
3. Dispatches to the appropriate Python module via subprocess
4. Surfaces the output in the assistant's context

The skill does not hold graph state. State lives in Neo4j. The skill is stateless and idempotent — any `/wisdom` command can be re-run safely.

### WISDOM_REPORT.md (always-on hook)

After every `/wisdom` run, `report()` writes `wisdom-out/WISDOM_REPORT.md`. This is the equivalent of graphify's `GRAPH_REPORT.md` — a plain-language summary that Claude reads before answering architecture questions.

Format:
```markdown
# Wisdom Report — {project} ({date})

## Graph status
- {N} Knowledge · {N} Experience · {N} Insight · {N} Wisdom nodes
- {N} total edges · last reflect: {date}

## Top Wisdom (by confidence × reinforcement)
1. "{principle}" [confidence: 0.91, reinforced: 8x]
   Grounded in: {3 source files}

## Fragile principles (need more experience)
...

## Cross-project god nodes
...

## Contradictions to resolve
...

## Suggested questions
...
```

The always-on hook in `settings.json` fires before every Glob and Grep call:
```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "Glob|Grep",
      "hooks": [{
        "type": "command",
        "command": "wisdom hook-check"
      }]
    }]
  }
}
```

If `wisdom-out/WISDOM_REPORT.md` exists, the hook prints: *"wisdomGraph: Wisdom graph exists. Read wisdom-out/WISDOM_REPORT.md for principles and god nodes before searching raw files."*

---

## Deployment: DozerDB vs Aura

### DozerDB (local)

`rundb.sh` starts DozerDB (Neo4j 5.x compatible, APOC bundled):

```bash
docker run -d \
  -p 7474:7474 -p 7687:7687 \
  -v $HOME/neo4j/data:/data \
  -v $HOME/neo4j/logs:/logs \
  -v $HOME/neo4j/import:/var/lib/neo4j/import \
  -v $HOME/neo4j/plugins:/plugins \
  --env NEO4J_AUTH=neo4j/password \
  --env NEO4J_PLUGINS='["apoc"]' \
  --env NEO4J_apoc_export_file_enabled=true \
  --env NEO4J_apoc_import_file_enabled=true \
  --env NEO4J_dbms_security_procedures_unrestricted='*' \
  graphstack/dozerdb:5.26.3.0
```

`wisdom docker up` runs this. `wisdom docker down` stops and removes the container (data persists in `$HOME/neo4j/data`).

### Aura (cloud)

Connection string format:
```
bolt+s://<instance-id>.databases.neo4j.io:7687
```

`wisdom connect` saves credentials to `~/.wisdom/config.json` (mode 600). The Python driver uses this at runtime. Credentials are never written to project files or committed to git.

### Config schema

```json
{
  "neo4j_uri": "bolt+s://xxx.databases.neo4j.io",
  "neo4j_user": "neo4j",
  "neo4j_password_env": "WISDOM_NEO4J_PASSWORD",
  "default_mode": "standard",
  "cache_dir": "~/.wisdom/cache"
}
```

Passwords are stored as environment variable names, not values. `wisdom connect` writes the actual password to the shell environment file (`~/.zshrc` or `~/.bashrc`), not to config.

---

## Security

All external input passes through `wisdom/security.py` before use:

- URLs → `validate_url()` (http/https only, no file:// redirects)
- Fetched content → `safe_fetch()` (size cap 10MB, timeout 30s)
- Node labels → `sanitize_label()` (strips control chars, caps 256 chars, HTML-escapes for Cypher injection prevention)
- Neo4j params → always passed as parameterized Cypher (`$param`), never string-interpolated

Cypher injection is prevented by the parameterized query requirement enforced in `merge.py` — no raw string formatting of user input into Cypher is permitted.

---

## Adding a new DIKW promotion heuristic

1. Add the heuristic function to `reflect.py` following the existing pattern
2. Return `{from_id, to_tier, reason, confidence}` dicts
3. The shared `_promote()` function handles the MERGE and edge-writing
4. Add a test in `tests/test_reflect.py` with a fixture Neo4j graph (neo4j-testcontainers)

---

## Testing

One test file per module under `tests/`. Neo4j integration tests use `testcontainers-python` to spin up a real Neo4j instance.

```bash
pytest tests/ -q                    # unit tests only
pytest tests/ -q --neo4j            # include Neo4j integration tests (requires Docker)
```

All unit tests are pure — no network calls, no Docker, no file system side effects outside `tmp_path`.

---

## Comparison with graphify internals

| | graphify | wisdomGraph |
|---|---|---|
| **Graph library** | NetworkX (in-process) | Neo4j (persistent server) |
| **Community detection** | Leiden / graspologic | Neo4j GDS Louvain (native) |
| **Deduplication** | SHA256 cache on files | MERGE on node ID in Neo4j |
| **Cross-run memory** | None (graph.json overwritten) | MERGE accumulates |
| **Query at inference** | Read GRAPH_REPORT.md | Live Cypher traversal |
| **Node semantics** | Flat (entity type) | Typed (epistemic role) |
| **Feedback** | None | REINFORCES edges, weight propagation |
| **Export** | HTML, JSON, Obsidian, cypher.txt | All of the above + live MCP server |
