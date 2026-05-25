"""Managed local Neo4j/DozerDB backend for first-time wisdomGraph setup."""
from __future__ import annotations

import secrets
import shutil
import socket
import stat
import subprocess
import sys
import time
from pathlib import Path

from .connect import save_connection

CONTAINER_NAME = "wisdomgraph-neo4j"
IMAGE = "graphstack/dozerdb:5.26.3.0"
BASE_DIR = Path.home() / ".wisdom" / "neo4j"
PASSWORD_PATH = Path.home() / ".wisdom" / "local-password"
HTTP_PORT = 7474
BOLT_PORT = 7687
URI = f"bolt://localhost:{BOLT_PORT}"
USER = "neo4j"


def _run(cmd: list[str], capture: bool = False) -> subprocess.CompletedProcess:
    if capture:
        return subprocess.run(cmd, capture_output=True, text=True, check=False)
    return subprocess.run(cmd, check=False)


def docker_available() -> bool:
    return shutil.which("docker") is not None


def docker_daemon_available() -> bool:
    if not docker_available():
        return False
    result = _run(["docker", "info"], capture=True)
    return result.returncode == 0


def _container_id(all_containers: bool = False) -> str:
    args = ["docker", "ps", "-q"]
    if all_containers:
        args = ["docker", "ps", "-aq"]
    result = _run(args + ["-f", f"name=^{CONTAINER_NAME}$"], capture=True)
    return result.stdout.strip()


def _ensure_dirs() -> None:
    for subdir in ("data", "logs", "import", "plugins"):
        (BASE_DIR / subdir).mkdir(parents=True, exist_ok=True)


def _read_or_create_password() -> str:
    if PASSWORD_PATH.exists():
        return PASSWORD_PATH.read_text(encoding="utf-8").strip()
    PASSWORD_PATH.parent.mkdir(parents=True, exist_ok=True)
    password = "wg-" + secrets.token_urlsafe(24)
    PASSWORD_PATH.write_text(password + "\n", encoding="utf-8")
    PASSWORD_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return password


def _wait_for_port(timeout_s: int = 45) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", BOLT_PORT), timeout=1):
                return True
        except OSError:
            time.sleep(1)
    return False


def up(password: str | None = None, connect: bool = True) -> None:
    """Start the managed local backend and optionally save wisdomGraph connection."""
    if not docker_available():
        print("error: Docker is not installed or not on PATH.", file=sys.stderr)
        print("Install Docker Desktop/Engine, or use Neo4j Aura with:", file=sys.stderr)
        print("  wisdom quickstart --storage aura --uri <bolt+s://...> --password <password>", file=sys.stderr)
        sys.exit(1)
    if not docker_daemon_available():
        print("error: Docker is installed but the daemon is not reachable.", file=sys.stderr)
        print("Start Docker, then run: wisdom local up", file=sys.stderr)
        sys.exit(1)

    password = password or _read_or_create_password()

    if _container_id(all_containers=False):
        print(f"  Local wisdomGraph backend already running ({CONTAINER_NAME})")
        if connect:
            save_connection(URI, USER, password)
        _print_ready(password)
        return

    if _container_id(all_containers=True):
        print(f"  Starting existing local backend ({CONTAINER_NAME})...")
        result = _run(["docker", "start", CONTAINER_NAME], capture=True)
        if result.returncode != 0:
            print(result.stderr.strip() or "error: failed to start local backend", file=sys.stderr)
            sys.exit(result.returncode)
        if connect:
            save_connection(URI, USER, password)
        _print_ready(password)
        return

    _ensure_dirs()

    print(f"  Pulling {IMAGE}...")
    result = _run(["docker", "pull", IMAGE], capture=True)
    if result.returncode != 0:
        print(result.stderr.strip() or "error: failed to pull DozerDB image", file=sys.stderr)
        sys.exit(result.returncode)

    print(f"  Starting managed local backend ({CONTAINER_NAME})...")
    result = _run([
        "docker", "run", "-d",
        "--name", CONTAINER_NAME,
        "-p", f"{HTTP_PORT}:7474",
        "-p", f"{BOLT_PORT}:7687",
        "-v", f"{BASE_DIR}/data:/data",
        "-v", f"{BASE_DIR}/logs:/logs",
        "-v", f"{BASE_DIR}/import:/var/lib/neo4j/import",
        "-v", f"{BASE_DIR}/plugins:/plugins",
        "--env", f"NEO4J_AUTH=neo4j/{password}",
        "--env", "NEO4J_PLUGINS=[\"apoc\"]",
        "--env", "NEO4J_apoc_export_file_enabled=true",
        "--env", "NEO4J_apoc_import_file_enabled=true",
        "--env", "NEO4J_dbms_security_procedures_unrestricted=*",
        IMAGE,
    ], capture=True)
    if result.returncode != 0:
        print(result.stderr.strip() or "error: failed to start local backend", file=sys.stderr)
        sys.exit(result.returncode)

    if not _wait_for_port():
        print("warning: local backend started, but Bolt was not reachable before timeout.", file=sys.stderr)
        print("Run `wisdom local logs` or `wisdom doctor` if connection fails.", file=sys.stderr)

    if connect:
        save_connection(URI, USER, password)
    _print_ready(password)


def down() -> None:
    if not docker_available():
        print("error: Docker is not installed or not on PATH.", file=sys.stderr)
        sys.exit(1)
    if not _container_id(all_containers=False):
        print(f"  Local backend not running ({CONTAINER_NAME})")
        return
    result = _run(["docker", "stop", CONTAINER_NAME], capture=True)
    if result.returncode != 0:
        print(result.stderr.strip() or "error: failed to stop local backend", file=sys.stderr)
        sys.exit(result.returncode)
    print(f"  Local backend stopped. Data preserved in {BASE_DIR}/data")


def status() -> None:
    if not docker_available():
        print("Docker: not installed")
        return
    result = _run(
        ["docker", "ps", "-a", "-f", f"name=^{CONTAINER_NAME}$", "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}"],
        capture=True,
    )
    if result.stdout.strip():
        print(result.stdout.strip())
    else:
        print(f"No managed local backend found. Run: wisdom local up")


def logs(tail: int = 80) -> None:
    if not docker_available():
        print("error: Docker is not installed or not on PATH.", file=sys.stderr)
        sys.exit(1)
    if not _container_id(all_containers=True):
        print(f"No managed local backend found. Run: wisdom local up")
        return
    result = _run(["docker", "logs", "--tail", str(tail), CONTAINER_NAME], capture=True)
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip(), file=sys.stderr)


def _print_ready(password: str) -> None:
    print()
    print("  wisdomGraph local backend is ready")
    print()
    print(f"  Container: {CONTAINER_NAME}")
    print(f"  Browser:   http://localhost:{HTTP_PORT}")
    print(f"  Bolt URI:  {URI}")
    print(f"  User:      {USER}")
    print(f"  Password:  stored in {PASSWORD_PATH}")
    print()
