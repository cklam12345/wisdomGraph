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
- wisdom_query       : run a Cypher traversal and return results
- wisdom_reflect     : run the DIKW promotion pipeline
- wisdom_report      : return tier counts + top Wisdom nodes as markdown
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
    lines = [
        "## DIKW Reflection complete",
        "",
        f"- Experience nodes promoted: {stats.get('experience_promoted', 0)}",
        f"- Insight nodes promoted:    {stats.get('insight_promoted', 0)}",
        f"- Wisdom candidates found:   {stats.get('wisdom_candidates', 0)}",
        f"- Reinforcement edges added: {stats.get('reinforcement_edges', 0)}",
    ]

    if candidates:
        lines += ["", "### Wisdom candidates (ready to crystallise)", ""]
        for c in candidates[:5]:
            lines.append(f"- **{c['label']}** (strength={c['strength']:.2f}, sources={c['count']})")
            lines.append(f"  {c.get('content', '')}")

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
