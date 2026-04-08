"""DozerDB Docker lifecycle — start, stop, status."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_CONTAINER_NAME = "wisdomgraph-dozerdb"
_IMAGE = "graphstack/dozerdb:5.26.3.0"
_DATA_DIR = Path.home() / "neo4j"


def _run(cmd: list[str], capture: bool = False) -> subprocess.CompletedProcess:
    if capture:
        return subprocess.run(cmd, capture_output=True, text=True)
    return subprocess.run(cmd)


def up(password: str = "password") -> None:
    """Start DozerDB container (idempotent — safe to call if already running)."""
    # Check if already running
    result = _run(["docker", "ps", "-q", "-f", f"name={_CONTAINER_NAME}"], capture=True)
    if result.stdout.strip():
        print(f"  DozerDB already running ({_CONTAINER_NAME})")
        return

    # Check if stopped container exists
    result = _run(["docker", "ps", "-aq", "-f", f"name={_CONTAINER_NAME}"], capture=True)
    if result.stdout.strip():
        print(f"  Starting existing DozerDB container...")
        _run(["docker", "start", _CONTAINER_NAME])
        _print_ready()
        return

    # Create data dirs
    for subdir in ("data", "logs", "import", "plugins"):
        (_DATA_DIR / subdir).mkdir(parents=True, exist_ok=True)

    print(f"  Pulling {_IMAGE}...")
    _run(["docker", "pull", _IMAGE])

    print(f"  Starting DozerDB ({_CONTAINER_NAME})...")
    _run([
        "docker", "run", "-d",
        "--name", _CONTAINER_NAME,
        "-p", "7474:7474",
        "-p", "7687:7687",
        "-v", f"{_DATA_DIR}/data:/data",
        "-v", f"{_DATA_DIR}/logs:/logs",
        "-v", f"{_DATA_DIR}/import:/var/lib/neo4j/import",
        "-v", f"{_DATA_DIR}/plugins:/plugins",
        "--env", f"NEO4J_AUTH=neo4j/{password}",
        "--env", "NEO4J_PLUGINS=[\"apoc\"]",
        "--env", "NEO4J_apoc_export_file_enabled=true",
        "--env", "NEO4J_apoc_import_file_enabled=true",
        "--env", "NEO4J_dbms_security_procedures_unrestricted=*",
        _IMAGE,
    ])
    _print_ready()


def _print_ready() -> None:
    print()
    print("  DozerDB started. Waiting for bolt port...")
    print()
    print("  Browser:   http://localhost:7474")
    print("  Bolt URI:  bolt://localhost:7687")
    print()
    print("  Run: wisdom connect bolt://localhost:7687 --user neo4j --password password")
    print()


def down() -> None:
    """Stop DozerDB container (data persists in ~/neo4j/data)."""
    result = _run(["docker", "ps", "-q", "-f", f"name={_CONTAINER_NAME}"], capture=True)
    if not result.stdout.strip():
        print(f"  DozerDB not running ({_CONTAINER_NAME})")
        return
    _run(["docker", "stop", _CONTAINER_NAME])
    print(f"  DozerDB stopped. Data preserved in {_DATA_DIR}/data")


def status() -> None:
    """Print DozerDB container status."""
    result = _run(["docker", "ps", "-f", f"name={_CONTAINER_NAME}", "--format", "table {{.Names}}\t{{.Status}}\t{{.Ports}}"], capture=True)
    if _CONTAINER_NAME in result.stdout:
        print(result.stdout)
    else:
        result2 = _run(["docker", "ps", "-a", "-f", f"name={_CONTAINER_NAME}", "--format", "table {{.Names}}\t{{.Status}}"], capture=True)
        if _CONTAINER_NAME in result2.stdout:
            print(result2.stdout)
            print("  (container exists but is not running — use: wisdom docker up)")
        else:
            print(f"  No DozerDB container found. Run: wisdom docker up")
