"""wisdomGraph CLI — `wisdom install` sets up the Claude Code skill."""
from __future__ import annotations

import json
import platform as _platform_mod
import re
import shutil
import sys
from pathlib import Path

try:
    from importlib.metadata import version as _pkg_version
    __version__ = _pkg_version("wisdomgraph")
except Exception:
    __version__ = "unknown"


# ── Hook / registration strings ──────────────────────────────────────────────

_SETTINGS_HOOK = {
    "matcher": "Glob|Grep",
    "hooks": [{
        "type": "command",
        "command": (
            "[ -f wisdom-out/WISDOM_REPORT.md ] && "
            "echo 'wisdomGraph: Wisdom graph exists. Read wisdom-out/WISDOM_REPORT.md "
            "for principles, god nodes, and contradictions before searching raw files.' || true"
        ),
    }],
}

_SKILL_REGISTRATION = (
    "\n# wisdomGraph\n"
    "- **wisdom** (`~/.claude/skills/wisdom/SKILL.md`) "
    "- accumulative Neo4j wisdom memory. Trigger: `/wisdom`\n"
    "When the user types `/wisdom`, invoke the Skill tool "
    "with `skill: \"wisdom\"` before doing anything else.\n"
)

_CLAUDE_MD_SECTION = """\
## wisdomGraph

This project uses wisdomGraph — accumulative Neo4j-native wisdom memory.

Rules:
- Before answering architecture or codebase questions, read wisdom-out/WISDOM_REPORT.md
  for top Wisdom principles, god nodes, and contradictions
- Use `/wisdom ask` to query the live graph when deeper traversal is needed
- After `/wisdom reflect`, new Wisdom nodes may be available — re-read the report
"""

_AGENTS_MD_SECTION = """\
## wisdomGraph

This project uses wisdomGraph — accumulative Neo4j-native wisdom memory.

Rules:
- Before answering architecture or codebase questions, read wisdom-out/WISDOM_REPORT.md
- Use the wisdom CLI to query the graph: wisdom ask "your question"
"""

_MCP_SETTINGS_BLOCK = {
    "wisdomGraph": {
        "command": "wisdom",
        "args": ["mcp"],
    }
}

_PLATFORM_CONFIG: dict[str, dict] = {
    "claude": {
        "skill_file": "skill.md",
        "skill_dst": Path(".claude") / "skills" / "wisdom" / "SKILL.md",
        "claude_md": True,
    },
    "windows": {
        "skill_file": "skill-windows.md",
        "skill_dst": Path(".claude") / "skills" / "wisdom" / "SKILL.md",
        "claude_md": True,
    },
    "claw": {
        "skill_file": "skill-claw.md",
        "skill_dst": Path(".claw") / "skills" / "wisdom" / "SKILL.md",
        "claude_md": False,
    },
}


# ── Install helpers ───────────────────────────────────────────────────────────

def install(platform: str = "claude") -> None:
    if platform not in _PLATFORM_CONFIG:
        print(f"error: unknown platform '{platform}'. Choose: {', '.join(_PLATFORM_CONFIG)}", file=sys.stderr)
        sys.exit(1)

    cfg = _PLATFORM_CONFIG[platform]
    skill_src = Path(__file__).parent / cfg["skill_file"]

    # Fallback: use skill.md for windows/claw if platform-specific not found yet
    if not skill_src.exists():
        skill_src = Path(__file__).parent / "skill.md"
    if not skill_src.exists():
        print(f"error: skill.md not found in package", file=sys.stderr)
        sys.exit(1)

    skill_dst = Path.home() / cfg["skill_dst"]
    skill_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(skill_src, skill_dst)
    (skill_dst.parent / ".wisdom_version").write_text(__version__, encoding="utf-8")
    print(f"  skill installed  ->  {skill_dst}")

    if cfg["claude_md"]:
        _register_claude_md()
        _install_claude_hook(Path("."))

    print()
    print("Done. Open your AI coding assistant and type:")
    print()
    print("  /wisdom .")
    print()


def _register_claude_md() -> None:
    claude_md = Path.home() / ".claude" / "CLAUDE.md"
    if claude_md.exists():
        content = claude_md.read_text(encoding="utf-8")
        if "wisdomGraph" in content or "wisdom" in content:
            print("  CLAUDE.md        ->  already registered (no change)")
            return
        claude_md.write_text(content.rstrip() + _SKILL_REGISTRATION, encoding="utf-8")
    else:
        claude_md.parent.mkdir(parents=True, exist_ok=True)
        claude_md.write_text(_SKILL_REGISTRATION.lstrip(), encoding="utf-8")
    print(f"  CLAUDE.md        ->  skill registered")


def _install_claude_hook(project_dir: Path) -> None:
    settings_path = project_dir / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            settings = {}
    else:
        settings = {}

    hooks = settings.setdefault("hooks", {})
    pre_tool = hooks.setdefault("PreToolUse", [])
    if any("wisdomGraph" in str(h) or "wisdom-out" in str(h) for h in pre_tool):
        print("  .claude/settings.json  ->  hook already registered (no change)")
        return
    pre_tool.append(_SETTINGS_HOOK)
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    print("  .claude/settings.json  ->  PreToolUse hook registered")


def _install_mcp(project_dir: Path | None = None, host: str = "claude") -> None:
    """Register wisdomGraph as an MCP server for a supported host."""
    host = host.lower()
    if host == "claude":
        _install_claude_mcp(project_dir)
    elif host == "codex":
        _install_codex_mcp()
    else:
        print("error: unknown MCP host. Choose: claude, codex", file=sys.stderr)
        sys.exit(1)


def _install_claude_mcp(project_dir: Path | None = None) -> None:
    """Register wisdomGraph as an MCP server in .claude/settings.json."""
    target_dir = project_dir or Path(".")
    settings_path = target_dir / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            settings = {}
    else:
        settings = {}

    mcp_servers = settings.setdefault("mcpServers", {})
    if "wisdomGraph" in mcp_servers:
        print("  .claude/settings.json  ->  wisdomGraph MCP already registered (no change)")
        return

    mcp_servers["wisdomGraph"] = _MCP_SETTINGS_BLOCK["wisdomGraph"]
    settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    print(f"  .claude/settings.json  ->  wisdomGraph MCP server registered")
    print()
    print("Claude Code will now call wisdomGraph tools directly:")
    print("  wisdom_ingest, wisdom_remember, wisdom_learn, wisdom_status, wisdom_list,")
    print("  wisdom_trace, wisdom_explain, wisdom_query, wisdom_reflect, wisdom_report")


def _install_codex_mcp() -> None:
    """Register wisdomGraph as a global Codex MCP server."""
    import subprocess

    if not shutil.which("codex"):
        print("error: codex CLI not found on PATH.", file=sys.stderr)
        print("Install Codex or run manually: codex mcp add wisdomGraph -- wisdom mcp", file=sys.stderr)
        sys.exit(1)

    existing = subprocess.run(
        ["codex", "mcp", "get", "wisdomGraph"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if existing.returncode == 0:
        print("  Codex MCP       ->  wisdomGraph already registered (no change)")
        return

    result = subprocess.run(
        ["codex", "mcp", "add", "wisdomGraph", "--", "wisdom", "mcp"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        print("error: failed to register wisdomGraph with Codex.", file=sys.stderr)
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        print("Run manually: codex mcp add wisdomGraph -- wisdom mcp", file=sys.stderr)
        sys.exit(result.returncode)

    print("  Codex MCP       ->  wisdomGraph registered globally")
    print()
    print("Codex will launch wisdomGraph with:")
    print("  wisdom mcp")


def _detect_hosts() -> list[str]:
    hosts: list[str] = []
    if Path.home().joinpath(".claude").exists() or shutil.which("claude"):
        hosts.append("claude")
    if shutil.which("codex"):
        hosts.append("codex")
    return hosts


def _expand_hosts(host: str) -> list[str]:
    host = host.lower()
    if host == "none":
        return []
    if host == "all":
        hosts = _detect_hosts()
        return hosts or ["claude"]
    if host in {"claude", "codex"}:
        return [host]
    print("error: unknown host. Choose: claude, codex, all, none", file=sys.stderr)
    sys.exit(1)


def _run_quickstart() -> None:
    """First-time setup: storage plus optional MCP registration."""
    storage = _get_arg("--storage", "local").lower()
    host_arg = _get_arg("--host", "all")
    hosts = _expand_hosts(host_arg)

    print("wisdomGraph quickstart")
    print()

    if storage == "local":
        from wisdom.local import up as local_up
        local_up()
    elif storage in {"aura", "existing"}:
        uri = _get_arg("--uri", "")
        user = _get_arg("--user", "neo4j")
        password = _get_arg("--password", "")
        if not uri:
            print(f"error: --uri is required for --storage {storage}", file=sys.stderr)
            sys.exit(1)
        if not password:
            import getpass
            password = getpass.getpass("Neo4j password: ")
        from wisdom.connect import save_connection
        save_connection(uri, user, password)
    else:
        print("error: unknown storage. Choose: local, aura, existing", file=sys.stderr)
        sys.exit(1)

    _doctor(connect_only=True)

    for host in hosts:
        _install_mcp(host=host)

    print()
    print("wisdomGraph is ready.")
    if hosts:
        print(f"MCP hosts: {', '.join(hosts)}")
        print("Start a new agent session so it can discover the MCP tools.")
    else:
        print("MCP registration skipped. Run `wisdom mcp-install --host <host>` later.")


def _doctor(connect_only: bool = False) -> None:
    """Check local setup without mutating Docker or graph state."""
    print("wisdomGraph doctor")
    print()

    from wisdom.connect import _load_config
    cfg = _load_config()
    print(f"Config: {Path.home() / '.wisdom' / 'config.json'}")
    print(f"Neo4j URI: {cfg.get('neo4j_uri', 'not configured')}")
    print(f"Neo4j user: {cfg.get('neo4j_user', 'not configured')}")
    print(f"Password env: {cfg.get('neo4j_password_env', 'WISDOM_NEO4J_PASSWORD')}")

    try:
        from wisdom.connect import ensure_schema, get_driver, status as graph_status
        driver = get_driver()
        ensure_schema(driver)
        stats = graph_status(driver)
        driver.close()
        print("Connection: ok")
        print(
            "Graph: "
            f"{stats.get('Knowledge', 0)} Knowledge, "
            f"{stats.get('Experience', 0)} Experience, "
            f"{stats.get('Insight', 0)} Insight, "
            f"{stats.get('Wisdom', 0)} Wisdom, "
            f"{stats.get('edges', 0)} edges"
        )
    except SystemExit:
        print("Connection: failed")
        if connect_only:
            raise
    if connect_only:
        return

    print()
    from wisdom.local import docker_available, docker_daemon_available
    print(f"Docker installed: {'yes' if docker_available() else 'no'}")
    print(f"Docker daemon:    {'yes' if docker_daemon_available() else 'no'}")

    hosts = _detect_hosts()
    print(f"MCP hosts found:  {', '.join(hosts) if hosts else 'none detected'}")


def claude_install(project_dir: Path | None = None) -> None:
    target = (project_dir or Path(".")) / "CLAUDE.md"
    if target.exists():
        content = target.read_text(encoding="utf-8")
        if "wisdomGraph" in content:
            print("wisdomGraph already configured in CLAUDE.md")
            return
        target.write_text(content.rstrip() + "\n\n" + _CLAUDE_MD_SECTION, encoding="utf-8")
    else:
        target.write_text(_CLAUDE_MD_SECTION, encoding="utf-8")
    print(f"wisdomGraph section written to {target.resolve()}")
    _install_claude_hook(project_dir or Path("."))


def claude_uninstall(project_dir: Path | None = None) -> None:
    target = (project_dir or Path(".")) / "CLAUDE.md"
    if not target.exists():
        print("No CLAUDE.md found - nothing to do")
        return
    content = target.read_text(encoding="utf-8")
    if "wisdomGraph" not in content:
        print("wisdomGraph not found in CLAUDE.md - nothing to do")
        return
    cleaned = re.sub(r"\n*## wisdomGraph\n.*?(?=\n## |\Z)", "", content, flags=re.DOTALL).rstrip()
    target.write_text((cleaned + "\n") if cleaned else "", encoding="utf-8")
    print(f"wisdomGraph section removed from {target.resolve()}")


# ── Main CLI ──────────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        _print_help()
        return

    cmd = sys.argv[1]

    if cmd == "install":
        default_p = "windows" if _platform_mod.system() == "Windows" else "claude"
        chosen = default_p
        args = sys.argv[2:]
        i = 0
        while i < len(args):
            if args[i] in ("--platform", "-p") and i + 1 < len(args):
                chosen = args[i + 1]; i += 2
            elif args[i].startswith("--platform="):
                chosen = args[i].split("=", 1)[1]; i += 1
            else:
                i += 1
        install(platform=chosen)

    elif cmd == "mcp":
        # Start the MCP server over stdio
        from wisdom.mcp import run_mcp_server
        run_mcp_server()

    elif cmd == "mcp-install":
        # Register MCP server with a supported host.
        project = _get_arg("--project", None)
        host = _get_arg("--host", "claude")
        _install_mcp(Path(project) if project else None, host=host)

    elif cmd == "quickstart":
        _run_quickstart()

    elif cmd == "doctor":
        _doctor()

    elif cmd == "local":
        from wisdom.local import down as local_down, logs as local_logs, status as local_status, up as local_up
        subcmd = sys.argv[2] if len(sys.argv) > 2 else ""
        password = _get_arg("--password", None)
        if subcmd == "up":
            local_up(password=password)
        elif subcmd == "down":
            local_down()
        elif subcmd == "status":
            local_status()
        elif subcmd == "logs":
            tail = int(_get_arg("--tail", "80"))
            local_logs(tail=tail)
        else:
            print("Usage: wisdom local [up|down|status|logs]", file=sys.stderr)
            sys.exit(1)

    elif cmd == "connect":
        if len(sys.argv) < 3:
            print("Usage: wisdom connect <bolt-uri> --user <user> --password <pass>", file=sys.stderr)
            sys.exit(1)
        uri = sys.argv[2]
        user = _get_arg("--user", "neo4j")
        password = _get_arg("--password", "")
        if not password:
            import getpass
            password = getpass.getpass("Neo4j password: ")
        from wisdom.connect import save_connection
        save_connection(uri, user, password)

    elif cmd == "docker":
        from wisdom.docker import up, down, status as docker_status
        subcmd = sys.argv[2] if len(sys.argv) > 2 else ""
        password = _get_arg("--password", "password")
        if subcmd == "up":
            up(password=password)
        elif subcmd == "down":
            down()
        elif subcmd == "status":
            docker_status()
        else:
            print("Usage: wisdom docker [up|down|status]", file=sys.stderr)
            sys.exit(1)

    elif cmd == "status":
        from wisdom.connect import get_driver, status as conn_status, ensure_schema
        driver = get_driver()
        ensure_schema(driver)
        stats = conn_status(driver)
        print(f"Knowledge: {stats.get('Knowledge', 0)}")
        print(f"Experience: {stats.get('Experience', 0)}")
        print(f"Insight:    {stats.get('Insight', 0)}")
        print(f"Wisdom:     {stats.get('Wisdom', 0)}")
        print(f"Sources:    {stats.get('Source', 0)}")
        print(f"Edges:      {stats.get('edges', 0)}")
        driver.close()

    elif cmd == "ask":
        if len(sys.argv) < 3:
            print("Usage: wisdom ask \"<question>\" [--tier wisdom]", file=sys.stderr)
            sys.exit(1)
        question = sys.argv[2]
        tier = _get_arg("--tier", None)
        from wisdom.connect import get_driver, ensure_schema
        from wisdom.traverse import answer_question
        driver = get_driver()
        ensure_schema(driver)
        with driver.session() as session:
            result = answer_question(session, question, tier_filter=tier)
        driver.close()
        _print_answer(result)

    elif cmd == "path":
        if len(sys.argv) < 4:
            print("Usage: wisdom path \"<concept A>\" \"<concept B>\"", file=sys.stderr)
            sys.exit(1)
        from wisdom.connect import get_driver, ensure_schema
        from wisdom.traverse import shortest_path
        driver = get_driver()
        ensure_schema(driver)
        with driver.session() as session:
            path = shortest_path(session, sys.argv[2], sys.argv[3])
        driver.close()
        if path:
            print(" → ".join(f"{n['label']} [{n.get('tier','?')}]" for n in path))
        else:
            print("No path found between these concepts.")

    elif cmd == "explain":
        if len(sys.argv) < 3:
            print("Usage: wisdom explain \"<concept>\"", file=sys.stderr)
            sys.exit(1)
        from wisdom.connect import get_driver, ensure_schema
        from wisdom.traverse import explain_node
        driver = get_driver()
        ensure_schema(driver)
        with driver.session() as session:
            result = explain_node(session, sys.argv[2])
        driver.close()
        _print_explain(result)

    elif cmd == "god-nodes":
        from wisdom.connect import get_driver, ensure_schema
        from wisdom.traverse import god_nodes
        driver = get_driver()
        ensure_schema(driver)
        with driver.session() as session:
            nodes = god_nodes(session, limit=15)
        driver.close()
        for i, n in enumerate(nodes, 1):
            print(f"{i:2}. {n['label']} [{n.get('tier','?')}] — {n.get('degree',0)} edges")

    elif cmd == "export":
        fmt = _get_arg("--cypher", None, is_flag=True)
        json_fmt = _get_arg("--json", None, is_flag=True)
        obsidian = _get_arg("--obsidian", None, is_flag=True)
        out_dir = Path(_get_arg("--out", "wisdom-out"))
        from wisdom.connect import get_driver, ensure_schema
        from wisdom.export import export_cypher, export_json, export_obsidian
        driver = get_driver()
        ensure_schema(driver)
        with driver.session() as session:
            if fmt:
                p = export_cypher(session, out_dir)
                print(f"Cypher export  ->  {p}")
            if json_fmt:
                p = export_json(session, out_dir)
                print(f"JSON export    ->  {p}")
            if obsidian:
                vault_dir = _get_arg("--obsidian-dir", None)
                p = export_obsidian(session, out_dir, Path(vault_dir) if vault_dir else None)
                print(f"Obsidian vault ->  {p}")
            if not any([fmt, json_fmt, obsidian]):
                print("Specify --cypher, --json, or --obsidian", file=sys.stderr)
        driver.close()

    elif cmd in ("claude",):
        subcmd = sys.argv[2] if len(sys.argv) > 2 else ""
        if subcmd == "install":
            claude_install()
        elif subcmd == "uninstall":
            claude_uninstall()
        else:
            print(f"Usage: wisdom {cmd} [install|uninstall]", file=sys.stderr)
            sys.exit(1)

    elif cmd == "purge":
        project = _get_arg("--project", "")
        if not project:
            print("Usage: wisdom purge --project <project-slug>", file=sys.stderr)
            sys.exit(1)
        from wisdom.connect import get_driver, ensure_schema
        driver = get_driver()
        ensure_schema(driver)
        with driver.session() as session:
            result = session.run(
                "MATCH (n {project: $p}) DETACH DELETE n RETURN count(n) AS deleted",
                p=project,
            )
            deleted = result.single()["deleted"]
        driver.close()
        print(f"Purged {deleted} nodes for project '{project}'")

    else:
        print(f"error: unknown command '{cmd}'", file=sys.stderr)
        print("Run 'wisdom --help' for usage.", file=sys.stderr)
        sys.exit(1)


def _get_arg(name: str, default, is_flag: bool = False):
    """Parse a named arg from sys.argv."""
    args = sys.argv
    if is_flag:
        return name in args
    for i, a in enumerate(args):
        if a == name and i + 1 < len(args):
            return args[i + 1]
        if a.startswith(f"{name}="):
            return a.split("=", 1)[1]
    return default


def _print_answer(result: dict) -> None:
    wisdom_nodes = result.get("wisdom_nodes", [])
    all_nodes = result.get("nodes", [])
    if wisdom_nodes:
        print("\n=== Wisdom ===")
        for w in wisdom_nodes:
            print(f"\n  {w.get('principle') or w.get('label', '')}")
            print(f"  [confidence: {w.get('confidence', 0):.2f}]")
    elif all_nodes:
        print("\n=== Best match ===")
        n = all_nodes[0]
        print(f"  [{n.get('tier','?')}] {n.get('label', '')}")
        if n.get("content"):
            print(f"  {n['content'][:200]}")
    else:
        print(result.get("answer", "No results found."))


def _print_explain(result: dict) -> None:
    if result.get("error"):
        print(result["error"])
        return
    print(f"\n{result['label']} [{result.get('tier','?')}]")
    if result.get("content"):
        print(f"\n{result['content']}")
    chain = result.get("dikw_chain", [])
    if chain:
        print("\nDIKW chain:")
        for n in chain:
            print(f"  {n.get('tier','?'):12} {n.get('label','')}")
    sources = result.get("sources", [])
    if sources:
        print("\nSources:")
        for s in sources:
            print(f"  {s.get('uri','')}")


def _print_help() -> None:
    print("Usage: wisdom <command>")
    print()
    print("Setup:")
    print("  quickstart [--storage local|aura|existing] [--host claude|codex|all|none]")
    print("  doctor                          check Neo4j, local backend, and MCP host readiness")
    print("  install [--platform P]          copy skill (claude|windows|claw)")
    print("  connect <uri> --user U --pass P  save Neo4j connection")
    print("  local up|down|status|logs       manage first-time local Neo4j/DozerDB backend")
    print("  docker up|down|status           manage DozerDB local container")
    print("  claude install|uninstall        write CLAUDE.md + PreToolUse hook")
    print()
    print("MCP:")
    print("  mcp                             start MCP server over stdio")
    print("  mcp-install [--project <dir>]   register MCP for Claude Code")
    print("  mcp-install --host codex        register MCP for Codex")
    print()
    print("Absorb:")
    print("  (use /wisdom in Claude Code — the skill handles absorption)")
    print()
    print("Query:")
    print("  ask \"<question>\" [--tier wisdom]")
    print("  path \"<A>\" \"<B>\"")
    print("  explain \"<concept>\"")
    print("  god-nodes")
    print()
    print("Maintain:")
    print("  status")
    print("  purge --project <slug>")
    print("  export --cypher|--json|--obsidian")
    print()


if __name__ == "__main__":
    main()
