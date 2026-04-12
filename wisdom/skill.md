---
name: wisdom
description: accumulative Neo4j-native DIKW wisdom memory — absorb any input, merge into persistent graph, ask questions that traverse Knowledge→Experience→Insight→Wisdom
trigger: /wisdom
---

# /wisdom

Turn any folder of files, URLs, or mixed input into a living Neo4j wisdom graph. Every run **merges** — the graph accumulates across sessions, projects, and months. Facts become patterns. Patterns become insights. Insights become wisdom.

Unlike graphify (snapshot → file), wisdomGraph writes directly to Neo4j. Ask it a question next week and it remembers everything you've ever absorbed.

## Usage

```
/wisdom                              # absorb current directory
/wisdom <path>                       # absorb a specific folder
/wisdom <path> --mode deep           # aggressive INFERRED edge extraction
/wisdom <path> --update              # re-absorb only changed files

/wisdom add <url>                    # absorb a URL (paper, tweet, page)
/wisdom add <url> --author "Name"    # tag the source author

/wisdom ask "<question>"             # query the wisdom graph
/wisdom ask "<question>" --tier wisdom  # only traverse Wisdom-tier nodes
/wisdom reflect                      # run DIKW promotion pass
/wisdom reflect --project <path>     # reflect on one corpus only

/wisdom path "<A>" "<B>"             # shortest path between concepts
/wisdom explain "<concept>"          # full DIKW chain for a concept
/wisdom god-nodes                    # most-connected concepts across all projects

/wisdom export --cypher              # dump as Cypher statements
/wisdom export --json                # export graph.json (graphify-compatible)
/wisdom export --obsidian            # export Obsidian vault

/wisdom status                       # graph stats by tier
/wisdom purge --project <path>       # remove one corpus from graph
```

---

## Step 1 — Pre-flight: check Neo4j connection

Before doing anything else, verify the Neo4j connection is live.

Run in a subagent:
```python
import subprocess
result = subprocess.run(["python3", "-m", "wisdom", "status"], capture_output=True, text=True)
print(result.stdout or result.stderr)
```

**If connection fails:**
- Ask the user: "Do you want to use Neo4j Aura (cloud, free) or DozerDB local Docker?"
- **Aura**: "Create a free instance at https://neo4j.com/cloud/aura, then run: `wisdom connect <your-bolt-uri> --user neo4j --password <your-password>`"
- **Docker**: Run `python3 -m wisdom docker up` then `python3 -m wisdom connect bolt://localhost:7687 --user neo4j --password password`

Do NOT proceed with absorption until the connection is verified.

---

## Step 2 — Detect files

For `/wisdom <path>` or `/wisdom .`:

Run in a subagent:
```python
import sys
sys.path.insert(0, '.')
from wisdom.detect import detect
from pathlib import Path
result = detect(Path("<path>"))
import json
print(json.dumps(result, indent=2))
```

Print the detection summary:
- Total files found by type
- Any sensitive files skipped
- `.wisdomignore` patterns active

If 0 files found, tell the user and stop.

---

## Step 3 — Extract (parallel subagents)

### Code files (AST — no LLM needed, fast)

For each code file in `result["files"]["code"]`, run a subagent:
```python
# AST extraction — uses tree-sitter, no LLM tokens
import sys
sys.path.insert(0, '.')
# Re-use graphify's extract module for AST parsing
try:
    from graphify.extract import extract
    data = extract("<file_path>")
    # Add DIKW metadata
    for node in data.get("nodes", []):
        node["tier"] = "knowledge"
        node["confidence_tag"] = "EXTRACTED"
        node["confidence"] = 1.0
    import json
    print(json.dumps(data))
except ImportError:
    # Fallback: minimal extraction without tree-sitter
    from pathlib import Path
    path = Path("<file_path>")
    import hashlib
    node_id = hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:16]
    data = {
        "nodes": [{"id": node_id, "label": path.name, "content": "", "source_file": str(path), "tier": "knowledge", "confidence": 1.0, "confidence_tag": "EXTRACTED"}],
        "edges": [],
        "source_file": str(path)
    }
    import json
    print(json.dumps(data))
```

### Document / paper / image files (LLM extraction)

For each doc/paper/image, run a subagent with this prompt:

```
Extract a knowledge graph from the following file for the wisdomGraph system.

File: <file_path>
Content: <file_content_or_describe_image>

Return a JSON object with this exact schema:
{
  "nodes": [
    {
      "id": "<unique_slug_no_spaces>",
      "label": "<human readable name>",
      "content": "<1-2 sentence description>",
      "source_file": "<file_path>",
      "tier": "<knowledge|experience|insight|wisdom>",
      "confidence": <0.0-1.0>,
      "confidence_tag": "<EXTRACTED|INFERRED|AMBIGUOUS>",
      "principle": "<if tier=wisdom: actionable principle statement, else empty string>"
    }
  ],
  "edges": [
    {
      "source": "<node_id>",
      "target": "<node_id>",
      "relation": "<calls|imports|uses|semantically_similar_to|conceptually_related_to|contradicts|rationale_for>",
      "confidence": <0.0-1.0>,
      "confidence_tag": "<EXTRACTED|INFERRED|AMBIGUOUS>"
    }
  ],
  "source_file": "<file_path>"
}

Tier assignment rules:
- knowledge: a specific fact, function, class, concept, or documented behavior
- experience: a pattern observed in context (decision + outcome), or same concept in multiple implementations
- insight: a recurring pattern across 3+ examples, a principle emerging from experience
- wisdom: a falsifiable, actionable principle you would stake your reputation on

Be honest: use EXTRACTED for things explicitly stated, INFERRED for reasonable deductions, AMBIGUOUS for uncertain connections.
Focus on: what connects to what, why things were designed a certain way, what problems they solve.
Extract rationale from: docstrings, # NOTE:, # WHY:, # IMPORTANT: comments, design decision prose.
```

**For --mode deep**: add to the prompt: "Extract more INFERRED edges. Identify semantic similarity between concepts across different parts of the file. Look for implicit dependencies, conceptual relationships, and design patterns."

---

## Step 4 — Classify and MERGE into Neo4j

After all extractions complete, run in a subagent:

```python
import sys, json
sys.path.insert(0, '.')
from wisdom.connect import get_driver, ensure_schema
from wisdom.classify import classify_nodes, build_dikw_edges
from wisdom.merge import merge_extraction
from wisdom.cache import save_extractions

driver = get_driver()
ensure_schema(driver)

all_extractions = <list of extraction dicts from Step 3>
project = "<path_or_slug>"

total_nodes = 0
total_edges = 0

with driver.session() as session:
    for extraction in all_extractions:
        nodes = extraction.get("nodes", [])
        edges = extraction.get("edges", [])

        # DIKW classification
        classified_nodes = classify_nodes(nodes, edges, project)
        enriched_edges = build_dikw_edges(classified_nodes, edges)

        extraction["nodes"] = classified_nodes
        extraction["edges"] = enriched_edges

        stats = merge_extraction(
            session,
            extraction,
            source_uri=extraction.get("source_file", ""),
            project=project,
        )
        total_nodes += stats["nodes"]
        total_edges += stats["edges"]

# Cache for incremental updates
save_extractions(all_extractions)

print(f"Merged: {total_nodes} nodes, {total_edges} edges")
driver.close()
```

Print the merge summary to the user.

---

## Step 5 — Generate WISDOM_REPORT.md

Run in a subagent:
```python
import sys
sys.path.insert(0, '.')
from wisdom.connect import get_driver, ensure_schema
from wisdom.report import render_report
from pathlib import Path

driver = get_driver()
ensure_schema(driver)
out_dir = Path("wisdom-out")

with driver.session() as session:
    report = render_report(session, project="<project>", out_dir=out_dir)

driver.close()
print(report)
```

Show the user the WISDOM_REPORT.md content and tell them it's been saved to `wisdom-out/WISDOM_REPORT.md`.

---

## /wisdom add <url>

1. Run `python3 -m wisdom status` to verify connection
2. Fetch and save: run `from wisdom.ingest import ingest; path = ingest("<url>", corpus_dir=Path("./raw"), author="<author>")` in a subagent
3. Run the extraction pipeline (Step 3) on the saved file
4. MERGE (Step 4)
5. Regenerate WISDOM_REPORT.md (Step 5)

---

## /wisdom ask "<question>"

Run in a subagent:
```python
import sys
sys.path.insert(0, '.')
from wisdom.connect import get_driver, ensure_schema
from wisdom.traverse import answer_question

driver = get_driver()
ensure_schema(driver)
tier_filter = "<tier_arg_or_None>"

with driver.session() as session:
    result = answer_question(session, "<question>", tier_filter=tier_filter if tier_filter else None)

driver.close()
import json
print(json.dumps(result, indent=2))
```

Format the result for the user:
- Lead with Wisdom nodes (if any) — show the `principle` field prominently
- Follow with Insight nodes — show `content` and `pattern_strength`
- Show the DIKW provenance chain: Knowledge → Experience → Insight → Wisdom
- If no Wisdom found: show the best Knowledge/Experience matches and suggest `/wisdom reflect` to promote them

---

## /wisdom reflect

The promotion pass. Tell the user: "Running DIKW promotion — elevating Knowledge → Experience → Insight → Wisdom..."

### 3a. Run automated promotions

Run in a subagent:
```python
import sys
sys.path.insert(0, '.')
from wisdom.connect import get_driver, ensure_schema
from wisdom.reflect import run_reflect

driver = get_driver()
ensure_schema(driver)
project = "<project_arg_or_None>"

with driver.session() as session:
    stats = run_reflect(session, project=project)

driver.close()
import json
print(json.dumps(stats, indent=2))
```

### 3b. LLM Wisdom generation

From `stats["wisdom_candidates_data"]`, for each candidate Insight with `pattern_strength >= 0.5`:

Generate a Wisdom principle with this prompt:
```
You are distilling wisdom from accumulated experience.

Insight: "<insight.label>"
Pattern: "<insight.content>"
Source count: <insight.source_count>
Pattern strength: <insight.pattern_strength>

Generate a single, falsifiable, actionable Wisdom principle.
The principle should be:
- Specific enough to act on (not "write good code")
- Grounded in the pattern (no hallucination)
- Stated as something you would stake your professional reputation on

Return JSON:
{
  "id": "wis:<snake_case_label>",
  "label": "<concise label>",
  "principle": "<1-2 sentence actionable principle>",
  "confidence": <0.5-0.95>,
  "insight_id": "<source_insight_id>"
}
```

Then write the generated Wisdom nodes to Neo4j:
```python
from wisdom.reflect import write_wisdom
with driver.session() as session:
    count = write_wisdom(session, <list_of_generated_wisdom_dicts>)
print(f"Generated {count} new Wisdom nodes")
```

### 3c. Regenerate report

Run Step 5 again to update WISDOM_REPORT.md.

Show the user:
- How many nodes were promoted at each tier
- How many new Wisdom principles were generated
- The updated top Wisdom nodes

---

## /wisdom path "<A>" "<B>"

```python
from wisdom.traverse import shortest_path
with driver.session() as session:
    path = shortest_path(session, "<A>", "<B>")
```

Format as: `ConceptA [knowledge] → ConceptB [experience] → ConceptC [wisdom]`

---

## /wisdom explain "<concept>"

```python
from wisdom.traverse import explain_node
with driver.session() as session:
    result = explain_node(session, "<concept>")
```

Show:
1. The node and its tier
2. Full DIKW chain (which Knowledge grounds it, which Experience revealed it, which Wisdom it supports)
3. Source files/URLs

---

## Output files

```
wisdom-out/
├── WISDOM_REPORT.md     always-on context — Claude reads this before every file search
└── cache/               SHA256 extraction cache — incremental runs skip unchanged files
```

Add a `.wisdomignore` file (gitignore syntax) to exclude folders:
```
# .wisdomignore
vendor/
node_modules/
*.generated.py
dist/
```

---

## Error handling

**Neo4j connection refused**: Guide user through Aura signup or `wisdom docker up`

**Empty extraction**: Warn "No extractable content found in <file>. Skipping." Continue with other files.

**MERGE conflict**: MERGE semantics are idempotent — re-running is safe. Higher-confidence nodes win on conflict.

**reflect() produces no Wisdom**: Tell the user "Not enough accumulated experience yet. Absorb more projects and run `/wisdom reflect` again after 2-3 more runs."
