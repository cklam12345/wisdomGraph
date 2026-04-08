"""Export wisdom graph to external formats."""
from __future__ import annotations

import json
from pathlib import Path


def export_cypher(session, out_dir: Path) -> Path:
    """Export all nodes and edges as Cypher CREATE statements."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "wisdom_export.cypher"

    lines = ["// wisdomGraph Cypher export\n// Import with: cypher-shell -f wisdom_export.cypher\n"]

    # Export nodes by tier
    for label in ("Knowledge", "Experience", "Insight", "Wisdom", "Source"):
        result = session.run(f"MATCH (n:{label}) RETURN n")
        for record in result:
            n = dict(record["n"])
            props = ", ".join(f"{k}: {json.dumps(v)}" for k, v in n.items() if v is not None)
            lines.append(f"MERGE (n:{label} {{id: {json.dumps(n.get('id', ''))}}}) SET n += {{{props}}};")

    # Export relationships
    result = session.run(
        """
        MATCH (a)-[r]->(b)
        WHERE (a:Knowledge OR a:Experience OR a:Insight OR a:Wisdom OR a:Source)
          AND (b:Knowledge OR b:Experience OR b:Insight OR b:Wisdom OR b:Source)
        RETURN a.id AS src, b.id AS tgt, type(r) AS rel, properties(r) AS props
        """
    )
    for record in result:
        rel_props = ", ".join(f"{k}: {json.dumps(v)}" for k, v in (record["props"] or {}).items())
        props_str = f" {{{rel_props}}}" if rel_props else ""
        lines.append(
            f"MATCH (a {{id: {json.dumps(record['src'])}}}), (b {{id: {json.dumps(record['tgt'])}}})"
            f" MERGE (a)-[:{record['rel']}{props_str}]->(b);"
        )

    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def export_json(session, out_dir: Path) -> Path:
    """Export as graph.json — graphify-compatible format."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "graph.json"

    nodes = []
    for label in ("Knowledge", "Experience", "Insight", "Wisdom"):
        result = session.run(
            f"""
            MATCH (n:{label})
            RETURN n.id AS id, n.label AS label, n.tier AS tier,
                   n.confidence AS confidence, n.source_file AS source_file,
                   n.project AS project
            """
        )
        for r in result:
            d = dict(r)
            d["type"] = label.lower()
            nodes.append(d)

    edges = []
    result = session.run(
        """
        MATCH (a)-[r]->(b)
        WHERE (a:Knowledge OR a:Experience OR a:Insight OR a:Wisdom)
          AND (b:Knowledge OR b:Experience OR b:Insight OR b:Wisdom)
        RETURN a.id AS source, b.id AS target, type(r) AS relation,
               r.confidence AS confidence, r.confidence_tag AS confidence_tag
        """
    )
    for r in result:
        edges.append(dict(r))

    graph = {"nodes": nodes, "edges": edges, "format": "wisdomgraph-v1"}
    out_path.write_text(json.dumps(graph, indent=2), encoding="utf-8")
    return out_path


def export_obsidian(session, out_dir: Path, vault_dir: Path | None = None) -> Path:
    """Export as Obsidian vault — one note per Wisdom node, index.md entry point."""
    vault = Path(vault_dir) if vault_dir else Path(out_dir) / "obsidian"
    vault.mkdir(parents=True, exist_ok=True)

    # Index
    index_lines = ["# Wisdom Graph — Obsidian Vault\n"]

    for label in ("Wisdom", "Insight", "Experience", "Knowledge"):
        result = session.run(
            f"""
            MATCH (n:{label})
            RETURN n.id AS id, n.label AS label,
                   n.principle AS principle, n.content AS content,
                   n.confidence AS confidence
            ORDER BY n.confidence DESC
            LIMIT 50
            """
        )
        rows = [dict(r) for r in result]
        if rows:
            index_lines.append(f"\n## {label} tier\n")
            for n in rows:
                fname = _safe_filename(n["label"]) + ".md"
                index_lines.append(f"- [[{fname}|{n['label']}]]")
                # Write note
                note = [f"# {n['label']}\n", f"**Tier:** {label}\n"]
                if n.get("principle"):
                    note.append(f"\n**Principle:** {n['principle']}\n")
                if n.get("content"):
                    note.append(f"\n{n['content']}\n")
                if n.get("confidence"):
                    note.append(f"\n**Confidence:** {n['confidence']:.2f}\n")
                (vault / fname).write_text("\n".join(note), encoding="utf-8")

    (vault / "index.md").write_text("\n".join(index_lines), encoding="utf-8")
    return vault


def _safe_filename(label: str) -> str:
    import re
    return re.sub(r"[^\w\s-]", "", label).strip().replace(" ", "_")[:80]
