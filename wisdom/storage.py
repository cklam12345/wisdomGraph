"""Explicit, verified storage selection for MCP clients."""
from __future__ import annotations

import contextlib
import io
import re
from pathlib import Path
from urllib.parse import urlsplit

from . import connect


def describe(cfg: dict) -> str:
    backend = connect.backend_name(cfg)
    lines = [f"Storage: {backend}"]
    if backend == "relate":
        lines.append(f"Graph: {cfg.get('graph_path', connect._DEFAULT_CONFIG['graph_path'])}")
    elif backend == "docker":
        lines.append("Managed Docker: bolt://localhost:7687")
    else:
        # Do not expose credentials embedded in legacy URI configurations.
        uri = urlsplit(cfg.get('neo4j_uri', ''))
        lines.append(f"Remote host: {uri.hostname or 'not configured'}")
    lines.append("Switching selects a separate graph; existing data is not copied or deleted.")
    return "\n".join(lines)


def control(args: dict) -> str:
    allowed = {"action", "backend", "path", "uri", "user", "password_env", "engine"}
    if set(args) - allowed:
        raise ValueError("Unknown storage option. Supply credentials via password_env, not tool arguments.")
    action = args.get("action", "status")
    cfg = connect._load_config()
    if action == "status":
        if set(args) - {"action"}:
            raise ValueError("Use action='switch' to select storage.")
        return describe(cfg)
    if action != "switch":
        raise ValueError("action must be status or switch")
    backend = args.get("backend")
    if backend not in {"relate", "neo4j", "aura", "docker"}:
        raise ValueError("Choose backend relate, neo4j, aura, or docker")
    options = {"relate": {"path"}, "neo4j": {"uri", "user", "password_env"},
               "aura": {"uri", "user", "password_env"}, "docker": {"engine"}}
    if set(args) - {"action", "backend"} - options[backend]:
        raise ValueError("An option does not apply to the selected backend")
    candidate = dict(cfg)
    candidate["backend"] = "neo4j" if backend == "aura" else backend
    if backend == "relate":
        path = args.get("path", cfg.get("graph_path", connect._DEFAULT_CONFIG["graph_path"]))
        if not isinstance(path, str) or not path.strip() or path == ":memory:":
            raise ValueError("Provide a persistent graph path")
        candidate["graph_path"] = str(Path(path).expanduser().resolve())
    elif backend in {"neo4j", "aura"}:
        for key, field in [("uri", "neo4j_uri"), ("user", "neo4j_user"), ("password_env", "neo4j_password_env")]:
            if key in args:
                candidate[field] = args[key]
        uri = urlsplit(candidate.get("neo4j_uri", ""))
        if uri.scheme not in {"bolt", "bolt+s", "bolt+ssc", "neo4j", "neo4j+s", "neo4j+ssc"} or not uri.hostname or uri.username or uri.password:
            raise ValueError("Provide a Neo4j URI without embedded credentials")
        env = candidate.get("neo4j_password_env", connect._ENV_VAR)
        if not isinstance(env, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", env):
            raise ValueError("password_env must name an environment variable")
    else:
        from . import local
        engine = args.get("engine", "neo4j")
        if engine not in {"neo4j", "dozerdb"}:
            raise ValueError("engine must be neo4j or dozerdb")
        # Python progress can contain credentials; do not echo it into MCP.
        # Child-process progress is directed to stderr by local._run.
        with contextlib.redirect_stdout(io.StringIO()):
            local.up(connect=False, engine=engine)

    # A failed probe leaves the previous persisted selection intact.
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        driver = connect.get_driver(candidate)
        try:
            connect.ensure_schema(driver)
            connect.status(driver)
        finally:
            driver.close()
    connect._save_config(candidate)
    return "Storage switched. Subsequent tool calls use this selection.\n" + describe(candidate)
