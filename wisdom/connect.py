"""Neo4j connection management — credentials, driver lifecycle, schema setup."""
from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from typing import Any

_CONFIG_PATH = Path.home() / ".wisdom" / "config.json"
_ENV_VAR = "WISDOM_NEO4J_PASSWORD"

# Default DozerDB local config
_DEFAULT_CONFIG: dict[str, Any] = {
    "neo4j_uri": "bolt://localhost:7687",
    "neo4j_user": "neo4j",
    "neo4j_password_env": _ENV_VAR,
    "default_mode": "standard",
    "cache_dir": str(Path.home() / ".wisdom" / "cache"),
}


def _load_config() -> dict[str, Any]:
    if _CONFIG_PATH.exists():
        try:
            return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return dict(_DEFAULT_CONFIG)


def _save_config(cfg: dict[str, Any]) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _CONFIG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    tmp.replace(_CONFIG_PATH)
    # Restrict permissions — config may have env var names
    _CONFIG_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)


def save_connection(uri: str, user: str, password: str) -> None:
    """Save connection details. Password written to shell env file, not config."""
    cfg = _load_config()
    cfg["neo4j_uri"] = uri
    cfg["neo4j_user"] = user
    cfg["neo4j_password_env"] = _ENV_VAR
    _save_config(cfg)

    # Write password to environment
    _write_env_password(password)
    print(f"  config saved  ->  {_CONFIG_PATH}")
    print(f"  password set  ->  {_ENV_VAR} in shell profile")


def _write_env_password(password: str) -> None:
    """Append export to shell profile if not already present."""
    for profile in [Path.home() / ".zshrc", Path.home() / ".bashrc", Path.home() / ".bash_profile"]:
        if profile.exists():
            content = profile.read_text(encoding="utf-8")
            marker = f"export {_ENV_VAR}="
            if marker in content:
                # Replace existing line
                lines = content.splitlines()
                new_lines = [f"{marker}\"{password}\"" if l.startswith(marker) else l for l in lines]
                profile.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
            else:
                with profile.open("a", encoding="utf-8") as f:
                    f.write(f"\n# wisdomGraph Neo4j password\nexport {_ENV_VAR}=\"{password}\"\n")
            os.environ[_ENV_VAR] = password
            return
    # No profile found — just set in current process
    os.environ[_ENV_VAR] = password


def get_driver():
    """Return a connected Neo4j driver using saved config."""
    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("error: neo4j driver not installed. Run: pip install wisdomgraph[neo4j]", file=sys.stderr)
        sys.exit(1)

    cfg = _load_config()
    uri = cfg.get("neo4j_uri", _DEFAULT_CONFIG["neo4j_uri"])
    user = cfg.get("neo4j_user", _DEFAULT_CONFIG["neo4j_user"])
    env_var = cfg.get("neo4j_password_env", _ENV_VAR)
    password = os.environ.get(env_var, "")

    if not password:
        print(f"error: {env_var} environment variable not set.", file=sys.stderr)
        print("Run: wisdom connect <uri> --user <user> --password <password>", file=sys.stderr)
        sys.exit(1)

    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        driver.verify_connectivity()
    except Exception as e:
        print(f"error: cannot connect to Neo4j at {uri}: {e}", file=sys.stderr)
        sys.exit(1)
    return driver


def ensure_schema(driver) -> None:
    """Create indexes and constraints if they don't exist."""
    with driver.session() as session:
        session.run("""
            CREATE INDEX wisdom_id IF NOT EXISTS
            FOR (n:Knowledge) ON (n.id)
        """)
        session.run("""
            CREATE INDEX experience_id IF NOT EXISTS
            FOR (n:Experience) ON (n.id)
        """)
        session.run("""
            CREATE INDEX insight_id IF NOT EXISTS
            FOR (n:Insight) ON (n.id)
        """)
        session.run("""
            CREATE INDEX wisdom_node_id IF NOT EXISTS
            FOR (n:Wisdom) ON (n.id)
        """)
        session.run("""
            CREATE INDEX source_uri IF NOT EXISTS
            FOR (n:Source) ON (n.uri)
        """)
        # Full-text search across all DIKW tiers
        try:
            session.run("""
                CREATE FULLTEXT INDEX wisdom_content IF NOT EXISTS
                FOR (n:Knowledge|Experience|Insight|Wisdom)
                ON EACH [n.label, n.content, n.principle]
            """)
        except Exception:
            pass  # Some Neo4j versions need different syntax — skip gracefully


def status(driver) -> dict:
    """Return graph stats by tier."""
    with driver.session() as session:
        counts = {}
        for label in ("Knowledge", "Experience", "Insight", "Wisdom", "Source"):
            result = session.run(f"MATCH (n:{label}) RETURN count(n) AS c")
            counts[label] = result.single()["c"]
        edge_result = session.run("MATCH ()-[r]->() RETURN count(r) AS c")
        counts["edges"] = edge_result.single()["c"]
    return counts
