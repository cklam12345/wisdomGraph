"""Managed local Neo4j backend for first-time wisdomGraph setup."""
from __future__ import annotations

import os
import shutil
import socket
import stat
import subprocess
import sys
import time
from pathlib import Path

from .connect import save_connection

CONTAINER_NAME = "wisdomgraph-neo4j"
DEFAULT_ENGINE = "neo4j"
IMAGE_BY_ENGINE = {
    "neo4j": "neo4j:latest",
    "dozerdb": "graphstack/dozerdb:5.26.3.0",
}
DEFAULT_PASSWORD = "password"
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


def _select_image(engine: str | None = None, image: str | None = None) -> str:
    explicit_image = image or os.environ.get("WISDOM_NEO4J_IMAGE")
    if explicit_image:
        return explicit_image

    selected_engine = (engine or os.environ.get("WISDOM_NEO4J_ENGINE") or DEFAULT_ENGINE).lower()
    if selected_engine not in IMAGE_BY_ENGINE:
        choices = ", ".join(sorted(IMAGE_BY_ENGINE))
        print(f"error: unknown local backend engine '{selected_engine}'. Choose: {choices}", file=sys.stderr)
        sys.exit(1)
    return IMAGE_BY_ENGINE[selected_engine]


def _read_or_create_password(default: str = DEFAULT_PASSWORD) -> str:
    if PASSWORD_PATH.exists():
        return PASSWORD_PATH.read_text(encoding="utf-8").strip()
    PASSWORD_PATH.parent.mkdir(parents=True, exist_ok=True)
    PASSWORD_PATH.write_text(default + "\n", encoding="utf-8")
    PASSWORD_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return default


def _resolve_password(password: str | None = None) -> str:
    selected = password or os.environ.get("WISDOM_NEO4J_PASSWORD")
    if selected:
        PASSWORD_PATH.parent.mkdir(parents=True, exist_ok=True)
        PASSWORD_PATH.write_text(selected + "\n", encoding="utf-8")
        PASSWORD_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)
        return selected
    return _read_or_create_password()


def _docker_run_args(image: str, password: str) -> list[str]:
    return [
        "docker", "run", "-d",
        "--name", CONTAINER_NAME,
        "-p", f"{HTTP_PORT}:7474",
        "-p", f"{BOLT_PORT}:7687",
        "-v", f"{BASE_DIR}/data:/data",
        "-v", f"{BASE_DIR}/logs:/logs",
        "-v", f"{BASE_DIR}/import:/var/lib/neo4j/import",
        "-v", f"{BASE_DIR}/plugins:/plugins",
        "--env", f"NEO4J_AUTH=neo4j/{password}",
        image,
    ]


def _wait_for_port(timeout_s: int = 45) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", BOLT_PORT), timeout=1):
                return True
        except OSError:
            time.sleep(1)
    return False


def _probe_cypher(password: str) -> bool:
    """One-shot: can we run an authenticated `RETURN 1` yet?

    Neo4j opens the Bolt port several seconds before it accepts
    authenticated queries, so a TCP connect is not proof of readiness.
    """
    try:
        from neo4j import GraphDatabase
    except ImportError:
        # Driver not installed here; the TCP probe is the best we can do.
        return True
    driver = None
    try:
        driver = GraphDatabase.driver(URI, auth=(USER, password))
        driver.verify_connectivity()
        with driver.session() as session:
            session.run("RETURN 1").consume()
        return True
    except Exception:
        return False
    finally:
        if driver is not None:
            driver.close()


def _wait_until_ready(password: str, timeout_s: int = 90) -> bool:
    """Wait until Neo4j accepts an authenticated query, not just a TCP socket."""
    if not _wait_for_port(timeout_s=min(timeout_s, 45)):
        return False
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _probe_cypher(password):
            return True
        time.sleep(1)
    return False


def up(
    password: str | None = None,
    connect: bool = True,
    image: str | None = None,
    engine: str | None = None,
) -> None:
    """Start the managed local backend and optionally save wisdomGraph connection."""
    selected_image = _select_image(engine=engine, image=image)

    if not docker_available():
        print("error: Docker is not installed or not on PATH.", file=sys.stderr)
        print("Install Docker Desktop/Engine, or use Neo4j Aura with:", file=sys.stderr)
        print("  wisdom quickstart --storage aura --uri <bolt+s://...> --password <password>", file=sys.stderr)
        sys.exit(1)
    if not docker_daemon_available():
        print("error: Docker is installed but the daemon is not reachable.", file=sys.stderr)
        print("Start Docker Desktop/Engine, then run: wisdom local up", file=sys.stderr)
        sys.exit(1)

    running = _container_id(all_containers=False)
    exists = bool(running) or bool(_container_id(all_containers=True))

    if exists:
        # A container's NEO4J_AUTH is fixed at creation time; a new --password
        # cannot change it, so reuse the saved one and warn on a mismatch.
        saved = _read_or_create_password()
        if password and password != saved:
            print("  note: a local backend already exists — keeping its existing password.", file=sys.stderr)
            print(f"        To reset it: wisdom local down && docker rm {CONTAINER_NAME}, then rerun.", file=sys.stderr)
        password = saved
    else:
        password = _resolve_password(password)

    if running:
        print(f"  Local wisdomGraph backend already running ({CONTAINER_NAME})")
        if connect:
            save_connection(URI, USER, password)
        _print_ready(password, selected_image)
        return

    if exists:
        print(f"  Starting existing local backend ({CONTAINER_NAME})...")
        result = _run(["docker", "start", CONTAINER_NAME], capture=True)
        if result.returncode != 0:
            print(result.stderr.strip() or "error: failed to start local backend", file=sys.stderr)
            sys.exit(result.returncode)
        _report_if_not_ready(password)
        if connect:
            save_connection(URI, USER, password)
        _print_ready(password, selected_image)
        return

    _ensure_dirs()

    print(f"  Pulling {selected_image} (first run may take a minute)...")
    result = _run(["docker", "pull", selected_image])  # stream progress to the user
    if result.returncode != 0:
        print(f"error: failed to pull {selected_image}", file=sys.stderr)
        print("Check Docker Hub access/proxy settings, then retry: wisdom local up", file=sys.stderr)
        sys.exit(result.returncode)

    print(f"  Starting managed local backend ({CONTAINER_NAME})...")
    result = _run(_docker_run_args(selected_image, password), capture=True)
    if result.returncode != 0:
        print(result.stderr.strip() or "error: failed to start local backend", file=sys.stderr)
        sys.exit(result.returncode)

    print("  Waiting for Neo4j to accept connections...")
    _report_if_not_ready(password)

    if connect:
        save_connection(URI, USER, password)
    _print_ready(password, selected_image)


def _report_if_not_ready(password: str) -> None:
    if not _wait_until_ready(password):
        print("warning: local backend started, but Neo4j was not ready before timeout.", file=sys.stderr)
        print("Run `wisdom local logs` or `wisdom doctor` if connection fails.", file=sys.stderr)


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


def _print_ready(password: str, image: str) -> None:
    print()
    print("  wisdomGraph local backend is ready")
    print()
    print(f"  Container: {CONTAINER_NAME}")
    print(f"  Image:     {image}")
    print(f"  Browser:   http://localhost:{HTTP_PORT}")
    print(f"  Bolt URI:  {URI}")
    print(f"  User:      {USER}")
    if password == DEFAULT_PASSWORD:
        print(f"  Password:  {password}")
    else:
        print(f"  Password:  stored in {PASSWORD_PATH}")
    print()
