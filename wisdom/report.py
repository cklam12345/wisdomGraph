"""Generate WISDOM_REPORT.md — the always-on context document for Claude."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def render_report(session, project: str = "", out_dir: Path | None = None) -> str:
    """Query Neo4j and render WISDOM_REPORT.md. Returns the markdown string."""
    from .traverse import god_nodes

    # Count nodes per tier inline (avoids needing the driver object)
    stats: dict = {}
    for label in ("Knowledge", "Experience", "Insight", "Wisdom", "Source"):
        r = session.run(f"MATCH (n:{label}) RETURN count(n) AS c")
        stats[label] = r.single()["c"]
    edge_r = session.run("MATCH ()-[r]->() RETURN count(r) AS c")
    stats["edges"] = edge_r.single()["c"]

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    lines = [
        f"# Wisdom Report — {project or 'all projects'} ({date_str})",
        "",
        "## Graph status",
        f"- {stats.get('Knowledge', 0)} Knowledge"
        f" · {stats.get('Experience', 0)} Experience"
        f" · {stats.get('Insight', 0)} Insight"
        f" · {stats.get('Wisdom', 0)} Wisdom nodes",
        f"- {stats.get('edges', 0)} total edges",
        f"- {stats.get('Source', 0)} source files/URLs indexed",
        "",
    ]

    # Top Wisdom nodes
    wisdom_result = session.run(
        """
        MATCH (w:Wisdom)
        RETURN w.label AS label, w.principle AS principle,
               w.confidence AS confidence,
               w.reinforcement_count AS reinforcement_count
        ORDER BY w.confidence * (1 + coalesce(w.reinforcement_count, 0)) DESC
        LIMIT 10
        """
    )
    wisdom_rows = [dict(r) for r in wisdom_result]

    if wisdom_rows:
        lines.append("## Top Wisdom (by confidence × reinforcement)")
        for i, w in enumerate(wisdom_rows, 1):
            conf = w.get("confidence") or 0.0
            reinf = w.get("reinforcement_count") or 0
            principle = w.get("principle") or w.get("label", "")
            lines.append(f"{i}. \"{principle}\"")
            lines.append(f"   [confidence: {conf:.2f}, reinforced: {reinf}x]")
        lines.append("")

    # Fragile principles
    fragile_result = session.run(
        """
        MATCH (w:Wisdom)
        WHERE w.confidence < 0.4
        RETURN w.label AS label, w.confidence AS confidence
        ORDER BY w.confidence ASC
        LIMIT 5
        """
    )
    fragile_rows = [dict(r) for r in fragile_result]
    if fragile_rows:
        lines.append("## Fragile principles (need more experience to strengthen)")
        for w in fragile_rows:
            lines.append(f"- \"{w['label']}\" [confidence: {w.get('confidence', 0):.2f}]")
        lines.append("")

    # Cross-project god nodes
    god_node_list = god_nodes(session, limit=10)
    if god_node_list:
        lines.append("## God nodes (most connected across all projects)")
        for i, n in enumerate(god_node_list, 1):
            lines.append(f"{i}. `{n['label']}` [{n.get('tier', 'knowledge')}] — {n.get('degree', 0)} edges")
        lines.append("")

    # Contradictions
    contra_result = session.run(
        """
        MATCH (a)-[:CONTRADICTS]->(b)
        RETURN a.label AS a_label, b.label AS b_label, a.tier AS tier
        LIMIT 5
        """
    )
    contra_rows = [dict(r) for r in contra_result]
    if contra_rows:
        lines.append("## Contradictions to resolve")
        for c in contra_rows:
            lines.append(f"- `{c['a_label']}` ↔ `{c['b_label']}` [{c.get('tier', 'knowledge')}]")
            lines.append("  Run `/wisdom reflect` to reconcile.")
        lines.append("")

    # Suggested questions
    lines.extend([
        "## Suggested questions",
        "_Questions this graph is uniquely positioned to answer:_",
        "",
    ])
    # Find high-betweenness nodes (approximate: nodes with most incoming + outgoing edges)
    bridge_result = session.run(
        """
        MATCH (n)
        WHERE (n:Knowledge OR n:Experience OR n:Insight OR n:Wisdom)
        WITH n, count{(n)--()}  AS degree
        WHERE degree >= 3
        RETURN n.label AS label, n.tier AS tier, degree
        ORDER BY degree DESC
        LIMIT 4
        """
    )
    for r in bridge_result:
        lines.append(f"- What makes `{r['label']}` a central concept in your work?")
    lines.append("- What patterns connect your most-used abstractions across projects?")
    lines.append("")

    report = "\n".join(lines)

    if out_dir:
        out_path = Path(out_dir) / "WISDOM_REPORT.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")

    return report


