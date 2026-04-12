"""wisdomGraph MCP server — expose DIKW tools to Claude Code over stdio.

Start with: wisdom mcp
Configure in .claude/settings.json:
{
  "mcpServers": {
    "wisdomGraph": {
      "command": "wisdom",
      "args": ["mcp"]
    }
  }
}

Tools exposed:
- wisdom_ingest      : ingest a file / directory / URL into Neo4j
- wisdom_remember    : store an explicit knowledge node
- wisdom_learn       : record an outcome (SUCCEEDED/FAILED/PARTIAL) + lesson learned
- wisdom_query       : run a Cypher traversal and return results
- wisdom_reflect     : run the DIKW promotion pipeline (surfaces failure anti-patterns)
- wisdom_report      : return tier counts + top Wisdom nodes + PREVENTS warnings as markdown
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

# ── MCP availability flag ─────────────────────────────────────────────────────
# We do NOT sys.exit at import time so tests can import handlers without mcp SDK.
_MCP_AVAILABLE = False
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent, CallToolResult, ListToolsResult
    _MCP_AVAILABLE = True
except ImportError:
    # Stub types so the rest of the module loads cleanly without the SDK.
    class _Stub:  # type: ignore[override]
        def __init__(self, *a, **kw): pass
    Tool = TextContent = CallToolResult = ListToolsResult = Server = stdio_server = _Stub  # type: ignore[misc,assignment]


# ── Lightweight result containers (no mcp dependency) ────────────────────────

class _Result:
    """Internal result — converted to CallToolResult only inside run_mcp_server."""
    __slots__ = ("text", "is_error")
    def __init__(self, text: str, is_error: bool = False):
        self.text = text
        self.is_error = is_error

    # Let tests inspect these directly without needing mcp types
    @property
    def content(self):
        class _C:
            def __init__(self, t): self.text = t
        return [_C(self.text)]

    @property
    def isError(self):
        return self.is_error


def _ok(text: str) -> _Result:
    return _Result(text)


def _err(text: str) -> _Result:
    return _Result(f"error: {text}", is_error=True)


# ── Tool definitions (plain dicts — no mcp.types.Tool needed at import) ──────

_TOOL_DEFS: list[dict] = [
    {
        "name": "wisdom_ingest",
        "description": (
            "Ingest a local file, directory, or URL into the wisdomGraph Neo4j store. "
            "Extracts Knowledge nodes and edges, merges them idempotently. "
            "Use this whenever you read a new file, learn a new concept, or visit a URL."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Absolute file path, directory path, or URL to ingest.",
                },
                "project": {
                    "type": "string",
                    "description": "Project name to tag these nodes (e.g. 'wisdomGraph'). Optional.",
                },
                "tier": {
                    "type": "string",
                    "enum": ["knowledge", "experience", "insight", "wisdom"],
                    "description": "DIKW tier to classify source as. Defaults to 'knowledge'.",
                },
            },
            "required": ["source"],
        },
    },
    {
        "name": "wisdom_remember",
        "description": (
            "Store an explicit knowledge node in wisdomGraph. "
            "Use this to remember facts, decisions, bugs fixed, patterns noticed, "
            "or any insight worth preserving across sessions."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "description": "Short label / title for this node.",
                },
                "content": {
                    "type": "string",
                    "description": "Full description / body of what to remember.",
                },
                "tier": {
                    "type": "string",
                    "enum": ["knowledge", "experience", "insight", "wisdom"],
                    "description": "DIKW tier. Use 'knowledge' for facts, 'experience' for patterns seen multiple times, 'insight' for derived understanding, 'wisdom' for universal principles.",
                },
                "project": {
                    "type": "string",
                    "description": "Project this belongs to. Optional.",
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence 0.0–1.0. Defaults to 1.0.",
                },
            },
            "required": ["label", "content"],
        },
    },
    {
        "name": "wisdom_learn",
        "description": (
            "Record what you tried, whether it SUCCEEDED or FAILED, and the lesson learned. "
            "This is the core of wisdomGraph's failure knowledge system — hard-won failures "
            "become anti-pattern Insights and PREVENTS edges that warn future sessions. "
            "Call this after any significant attempt: bug fix, architecture decision, deployment, experiment."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "description": "Short label for what was attempted (e.g. 'Deploy with sqlite on Heroku').",
                },
                "what_was_tried": {
                    "type": "string",
                    "description": "Description of the approach or action taken.",
                },
                "outcome": {
                    "type": "string",
                    "enum": ["SUCCEEDED", "FAILED", "PARTIAL", "UNKNOWN"],
                    "description": "The result. FAILED outcomes get elevated confidence in the wisdom graph — hard-won knowledge.",
                },
                "lesson": {
                    "type": "string",
                    "description": "What was learned. For failures: what to avoid and why. For successes: what made it work.",
                },
                "project": {
                    "type": "string",
                    "description": "Project context. Optional.",
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence in this lesson 0.0–1.0. Failures default to 0.9 (high — hard to acquire). Defaults to 0.8.",
                },
            },
            "required": ["label", "what_was_tried", "outcome", "lesson"],
        },
    },
    {
        "name": "wisdom_query",
        "description": (
            "Query the wisdomGraph Neo4j store with a Cypher statement. "
            "Use this to retrieve related knowledge, find patterns, trace DIKW chains, "
            "or answer questions from the accumulated wisdom graph."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "cypher": {
                    "type": "string",
                    "description": "Cypher query to run. Use MATCH/RETURN — no writes.",
                },
                "params": {
                    "type": "object",
                    "description": "Optional parameters for parameterized Cypher.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max rows to return. Defaults to 25.",
                },
            },
            "required": ["cypher"],
        },
    },
    {
        "name": "wisdom_reflect",
        "description": (
            "Run the DIKW promotion pipeline: Knowledge → Experience → Insight → Wisdom. "
            "Call this after a significant session to distil accumulated knowledge into higher-tier wisdom. "
            "Returns promotion statistics."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Scope reflection to a specific project. Optional.",
                },
            },
        },
    },
    {
        "name": "wisdom_report",
        "description": (
            "Return the current wisdomGraph status as markdown: tier counts, top Wisdom nodes, "
            "god nodes (highest connectivity), and any contradictions. "
            "Read this at the start of a session to get up to speed instantly."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Filter report to a specific project. Optional.",
                },
            },
        },
    },
]


# ── Handler helpers ───────────────────────────────────────────────────────────

def _get_driver():
    """Return a live Neo4j driver (or raise RuntimeError with a helpful message)."""
    try:
        from .connect import get_driver
        return get_driver()
    except SystemExit as e:
        raise RuntimeError(
            "Cannot connect to Neo4j. Make sure DozerDB is running (`wisdom docker up`) "
            "and credentials are configured (`wisdom connect`)."
        ) from e


# ── Tool handlers (pure Python — no mcp types needed) ────────────────────────

def _handle_ingest(args: dict[str, Any]) -> _Result:
    source = args.get("source", "").strip()
    project = args.get("project", "")
    tier = args.get("tier", "knowledge")

    if not source:
        return _err("'source' is required")

    # URL ingestion
    if source.startswith("http://") or source.startswith("https://"):
        try:
            from .ingest import ingest as fetch_ingest
            import tempfile
            corpus = Path(tempfile.mkdtemp(prefix="wisdom_corpus_"))
            saved = fetch_ingest(source, corpus)
            source = str(saved)
        except Exception as exc:
            return _err(f"URL fetch failed: {exc}")

    source_path = Path(source)
    if not source_path.exists():
        return _err(f"Path does not exist: {source}")

    # Collect files
    if source_path.is_dir():
        files = [
            f for f in source_path.rglob("*")
            if f.is_file() and f.suffix in {
                ".py", ".js", ".ts", ".go", ".rs", ".java",
                ".c", ".cpp", ".rb", ".cs", ".kt", ".scala",
                ".md", ".txt", ".toml", ".yaml", ".yml", ".json",
            }
        ]
    else:
        files = [source_path]

    if not files:
        return _ok(f"No ingestible files found in {source}")

    try:
        driver = _get_driver()
    except RuntimeError as exc:
        return _err(str(exc))

    from .merge import merge_extraction

    total_nodes = 0
    total_edges = 0

    with driver.session() as session:
        for fpath in files:
            try:
                # Build a minimal extraction from file metadata
                node_id = f"{tier}:{str(fpath).replace('/', '_')}"
                extraction = {
                    "nodes": [{
                        "id": node_id,
                        "label": fpath.name,
                        "content": fpath.read_text(encoding="utf-8", errors="replace")[:500],
                        "tier": tier,
                        "source_file": str(fpath),
                        "project": project,
                        "confidence": 1.0,
                        "confidence_tag": "INGESTED",
                    }],
                    "edges": [],
                }
                stats = merge_extraction(session, extraction, source_uri=str(fpath), project=project)
                total_nodes += stats.get("nodes", 0)
                total_edges += stats.get("edges", 0)
            except Exception:
                continue

    driver.close()
    return _ok(
        f"Ingested {len(files)} file(s) from `{source}`.\n"
        f"Merged {total_nodes} nodes · {total_edges} edges into Neo4j."
    )


def _handle_remember(args: dict[str, Any]) -> _Result:
    label = args.get("label", "").strip()
    content = args.get("content", "").strip()
    tier = args.get("tier", "knowledge")
    project = args.get("project", "")
    confidence = float(args.get("confidence", 1.0))

    if not label or not content:
        return _err("'label' and 'content' are required")

    node_id = f"{tier}:{hashlib.sha256(label.encode()).hexdigest()[:16]}"

    node = {
        "id": node_id,
        "label": label,
        "content": content,
        "tier": tier,
        "project": project,
        "confidence": confidence,
        "confidence_tag": "EXPLICIT",
    }

    try:
        driver = _get_driver()
    except RuntimeError as exc:
        return _err(str(exc))

    from .merge import merge_nodes
    with driver.session() as session:
        merge_nodes(session, [node])
    driver.close()

    return _ok(
        f"Remembered: [{tier.upper()}] {label}\n"
        f"ID: {node_id}\n"
        f"Confidence: {confidence}"
    )


def _handle_learn(args: dict[str, Any]) -> _Result:
    label = args.get("label", "").strip()
    what_was_tried = args.get("what_was_tried", "").strip()
    outcome = args.get("outcome", "UNKNOWN").upper()
    lesson = args.get("lesson", "").strip()
    project = args.get("project", "")
    # Failures default to 0.9 confidence — hard-won knowledge
    default_confidence = 0.9 if outcome == "FAILED" else 0.8
    confidence = float(args.get("confidence", default_confidence))

    if not label or not what_was_tried or not lesson:
        return _err("'label', 'what_was_tried', and 'lesson' are required")

    valid_outcomes = {"SUCCEEDED", "FAILED", "PARTIAL", "UNKNOWN"}
    if outcome not in valid_outcomes:
        return _err(f"'outcome' must be one of: {', '.join(sorted(valid_outcomes))}")

    exp_id = f"exp:{hashlib.sha256(label.encode()).hexdigest()[:16]}"
    content = f"{what_was_tried}\n\nLesson: {lesson}"

    exp_node = {
        "id": exp_id,
        "label": label,
        "content": content,
        "tier": "experience",
        "project": project,
        "confidence": confidence,
        "confidence_tag": "LEARNED",
        "outcome": outcome,
        "lesson": lesson,
    }

    try:
        driver = _get_driver()
    except RuntimeError as exc:
        return _err(str(exc))

    from .merge import merge_nodes
    with driver.session() as session:
        # Write the Experience node with outcome + lesson fields
        session.run(
            """
            MERGE (e:Experience {id: $id})
            ON CREATE SET
                e.label     = $label,
                e.content   = $content,
                e.outcome   = $outcome,
                e.lesson    = $lesson,
                e.project   = $project,
                e.confidence = $confidence,
                e.tier      = 'experience',
                e.timestamp = $ts
            ON MATCH SET
                e.outcome   = $outcome,
                e.lesson    = $lesson,
                e.confidence = CASE WHEN $confidence > e.confidence
                    THEN $confidence ELSE e.confidence END,
                e.content   = $content
            """,
            id=exp_id,
            label=label,
            content=content,
            outcome=outcome,
            lesson=lesson,
            project=project,
            confidence=confidence,
            ts=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        )
    driver.close()

    outcome_icon = {"SUCCEEDED": "✅", "FAILED": "❌", "PARTIAL": "⚠️", "UNKNOWN": "❓"}.get(outcome, "")
    lines = [
        f"## Learned {outcome_icon} {outcome}",
        "",
        f"**{label}**",
        f"ID: `{exp_id}`",
        "",
        f"*What was tried:* {what_was_tried}",
        "",
        f"*Lesson:* {lesson}",
        "",
        f"Confidence: {confidence}",
    ]
    if outcome == "FAILED":
        lines += [
            "",
            "> 💡 Run `wisdom_reflect` to promote this failure into an anti-pattern Insight",
            "> and generate PREVENTS edges that warn future sessions.",
        ]
    return _ok("\n".join(lines))


def _handle_query(args: dict[str, Any]) -> _Result:
    cypher = args.get("cypher", "").strip()
    params = args.get("params", {}) or {}
    limit = int(args.get("limit", 25))

    if not cypher:
        return _err("'cypher' is required")

    # Safety: block write operations
    cypher_upper = cypher.upper()
    for forbidden in ("CREATE ", "DELETE ", "DETACH ", "SET ", "REMOVE ", "MERGE "):
        if forbidden in cypher_upper:
            return _err(
                "wisdom_query is read-only. Use wisdom_remember or wisdom_ingest to write data."
            )

    # Inject LIMIT if not already present
    if "LIMIT" not in cypher_upper:
        cypher = cypher.rstrip(";") + f" LIMIT {limit}"

    try:
        driver = _get_driver()
    except RuntimeError as exc:
        return _err(str(exc))

    try:
        with driver.session() as session:
            result = session.run(cypher, **params)
            records = [dict(r) for r in result]
    except Exception as exc:
        driver.close()
        return _err(f"Cypher error: {exc}")

    driver.close()

    if not records:
        return _ok("No results.")

    # Format as markdown table
    keys = list(records[0].keys())
    header = "| " + " | ".join(keys) + " |"
    sep = "| " + " | ".join(["---"] * len(keys)) + " |"
    rows = ["| " + " | ".join(str(r.get(k, "")) for k in keys) + " |" for r in records]

    return _ok("\n".join([header, sep] + rows))


def _handle_reflect(args: dict[str, Any]) -> _Result:
    project = args.get("project", None)

    try:
        driver = _get_driver()
    except RuntimeError as exc:
        return _err(str(exc))

    from .reflect import run_reflect
    with driver.session() as session:
        stats = run_reflect(session, project=project)
    driver.close()

    candidates = stats.pop("wisdom_candidates_data", [])
    failure_promoted = stats.get("failure_insight_promoted", 0)
    prevents_edges = stats.get("prevents_edges", 0)

    lines = [
        "## DIKW Reflection complete",
        "",
        "### Promotion pipeline",
        f"- Experience nodes promoted:      {stats.get('experience_promoted', 0)}",
        f"- ❌ Failure anti-patterns found: {failure_promoted}",
        f"- ✅ Success insights promoted:   {stats.get('insight_promoted', 0)}",
        f"- Wisdom candidates crystallised: {stats.get('wisdom_candidates', 0)}",
        "",
        "### Feedback edges",
        f"- PREVENTS edges written: {prevents_edges}  ← anti-pattern Wisdom → Knowledge to avoid",
        f"- REINFORCES edges added: {stats.get('reinforcement_edges', 0)}  ← successful Wisdom → Knowledge to build on",
    ]

    # Surface anti-pattern wisdom candidates first
    antipatterns = [c for c in candidates if c.get("is_antipattern")]
    successes    = [c for c in candidates if not c.get("is_antipattern")]

    if antipatterns:
        lines += ["", "### ⚠️ Anti-pattern Wisdom (AVOID these paths)", ""]
        for c in antipatterns[:5]:
            lines.append(f"- **{c['label']}** (strength={c['strength']:.2f}, sources={c['count']})")
            if c.get("content"):
                lines.append(f"  _{c['content']}_")

    if successes:
        lines += ["", "### 💡 Wisdom candidates (ready to crystallise)", ""]
        for c in successes[:5]:
            lines.append(f"- **{c['label']}** (strength={c['strength']:.2f}, sources={c['count']})")
            if c.get("content"):
                lines.append(f"  _{c['content']}_")

    if failure_promoted > 0:
        lines += [
            "",
            "> Hard-won failure knowledge has been promoted with elevated confidence.",
            "> PREVENTS edges now warn future traversals before they repeat these mistakes.",
        ]

    return _ok("\n".join(lines))


def _handle_report(args: dict[str, Any]) -> _Result:
    project = args.get("project", "")

    try:
        driver = _get_driver()
    except RuntimeError as exc:
        return _err(str(exc))

    from .report import render_report
    with driver.session() as session:
        md = render_report(session, project=project)
    driver.close()

    return _ok(md)


_HANDLERS = {
    "wisdom_ingest":   _handle_ingest,
    "wisdom_remember": _handle_remember,
    "wisdom_learn":    _handle_learn,
    "wisdom_query":    _handle_query,
    "wisdom_reflect":  _handle_reflect,
    "wisdom_report":   _handle_report,
}


# ── Server entry point ────────────────────────────────────────────────────────

def run_mcp_server() -> None:
    """Start the wisdomGraph MCP server over stdio."""
    if not _MCP_AVAILABLE:
        print(
            "error: mcp package not installed. Run: pip install 'wisdomgraph[mcp]'",
            file=sys.stderr,
        )
        sys.exit(1)

    server = Server("wisdomGraph")

    # Build typed Tool list now that we know mcp is available
    tools = [Tool(name=t["name"], description=t["description"], inputSchema=t["inputSchema"]) for t in _TOOL_DEFS]

    @server.list_tools()
    async def list_tools() -> ListToolsResult:
        return ListToolsResult(tools=tools)

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
        handler = _HANDLERS.get(name)
        if handler is None:
            result = _err(f"Unknown tool: {name}")
        else:
            try:
                result = handler(arguments)
            except Exception as exc:
                result = _err(f"Unexpected error in {name}: {exc}")

        return CallToolResult(
            content=[TextContent(type="text", text=result.text)],
            isError=result.is_error,
        )

    import asyncio

    async def _main() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(_main())
