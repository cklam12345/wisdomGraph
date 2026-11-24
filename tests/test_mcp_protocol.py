"""Exercise the installed SDK and real stdio transport, not just handlers."""
import asyncio
import sys

import pytest

pytest.importorskip('mcp')
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_stdio_storage_switch_and_persistent_memory(tmp_path):
    bootstrap = (
        'from pathlib import Path; from wisdom import connect; '
        f'connect._CONFIG_PATH = Path({str(tmp_path / "config.json")!r}); '
        f'connect._DEFAULT_CONFIG["graph_path"] = {str(tmp_path / "first.rl")!r}; '
        'from wisdom.mcp import run_mcp_server; run_mcp_server()'
    )

    async def exercise():
        server = StdioServerParameters(command=sys.executable, args=['-c', bootstrap])
        async with stdio_client(server) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert 'wisdom_storage' in {tool.name for tool in tools.tools}
                for name, args in [
                    ('wisdom_storage', {}),
                    ('wisdom_remember', {'label': 'Release smoke', 'content': 'Persistent MCP test'}),
                    ('wisdom_storage', {'action': 'switch', 'backend': 'relate', 'path': str(tmp_path / 'second.rl')}),
                    ('wisdom_storage', {'action': 'switch', 'backend': 'relate', 'path': str(tmp_path / 'first.rl')}),
                ]:
                    result = await session.call_tool(name, args)
                    assert not result.isError, result
                result = await session.call_tool('wisdom_query', {'cypher': 'MATCH (n:Knowledge) RETURN n.label AS label'})
                assert not result.isError
                assert 'Release smoke' in result.content[0].text

    asyncio.run(asyncio.wait_for(exercise(), timeout=30))
