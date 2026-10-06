"""`cbench mcp` over the MCP protocol (in-memory client). Needs the mcp extra
(Python 3.10+); skipped without it."""
from __future__ import annotations

import asyncio
import json

import pytest

pytest.importorskip("mcp")

from mcp.client import Client  # noqa: E402

from cbench import mcp_server  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


async def _session(fn):
    async with Client(mcp_server.build_server()) as c:
        return await fn(c)


def test_tools_and_annotations():
    async def go(c):
        return (await c.list_tools()).tools
    tools = {tl.name: tl for tl in _run(_session(go))}
    assert set(tools) == {fn.__name__ for fn, _ann in mcp_server.TOOLS}
    for name in ("status", "watch_jobs", "query_results", "check_deps"):
        assert tools[name].annotations.read_only_hint is True, name
    for name in ("set_config", "gen_jobs", "start_jobs", "build_benchmark", "run_nodecheck"):
        assert tools[name].annotations.read_only_hint is False, name
        assert "confirm" in tools[name].input_schema["properties"], name
    assert "confirm" not in tools["parse_results"].input_schema["properties"]


def test_errors_reach_the_client_with_their_reason(tmp_path, monkeypatch):
    monkeypatch.setenv("CBENCHTEST", str(tmp_path))

    async def go(c):
        return await c.call_tool("watch_jobs", {"testset": "t", "ident": "nope"})
    r = _run(_session(go))
    assert r.is_error and "run gen_jobs first" in r.content[0].text


def test_call_returns_json(tmp_path, monkeypatch):
    monkeypatch.setenv("CBENCHTEST", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    async def go(c):
        return await c.call_tool("set_config", {"updates": {"max_nodes": 3}})
    r = _run(_session(go))
    assert not r.is_error
    out = json.loads(r.content[0].text)
    assert out["confirmed"] is False and out["diff"]["set"]["max_nodes"]["new"] == 3
    assert not (tmp_path / "cluster.yaml").exists()


def test_instructions_require_user_consent():
    assert "confirm=true" in mcp_server.INSTRUCTIONS
    assert "Never confirm" in mcp_server.INSTRUCTIONS
