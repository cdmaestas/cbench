"""`cbench mcp`: an MCP server (stdio) that lets an MCP client such as Claude
drive cbench. The operations live in cbench.mcp_tools; this module only
registers them. Needs the ``mcp`` extra (``pip install 'cbench[mcp]'``,
Python 3.10+).
"""

from __future__ import annotations

import functools

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from cbench import mcp_tools as t
from cbench.config import ConfigError
from cbench.nodecheck import NodecheckError
from cbench.profiles import ProfileError

INSTRUCTIONS = """\
cbench is an HPC benchmarking framework. Typical flow: status -> check_deps
(-> build_benchmark) -> run_nodecheck on the node pool -> gen_jobs (with
nodefacts) -> start_jobs -> watch_jobs until all_done -> parse_results ->
query_results.

Tools that change anything (set_config, run_nodecheck, gen_jobs, start_jobs,
build_benchmark) do nothing without confirm=true: they return the exact command
or config diff instead. Show that plan to the user and only call again with
confirm=true once the user has agreed to that specific action. Never confirm
on your own initiative. start_jobs submits to the batch queue or loads the
machine; build_benchmark downloads and compiles source code.

cbench never installs system packages: report check_deps' suggestions to the
user (installing them is an admin's job).

Long operations (start_jobs mode=interactive, build_benchmark) return a
task_id; poll task_status. Jobs report progress through watch_jobs.
"""

_READ = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
_READ_NET = ToolAnnotations(readOnlyHint=True, openWorldHint=True)
_LOCAL_WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False,
                               idempotentHint=True, openWorldHint=False)
_ACTION = ToolAnnotations(readOnlyHint=False, destructiveHint=False,
                          idempotentHint=False, openWorldHint=True)
_OVERWRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=True,
                             idempotentHint=True, openWorldHint=False)

#: (function, annotations); the tool name is the function name
TOOLS = [
    (t.status, _READ),
    (t.get_config, _READ),
    (t.list_testsets, _READ),
    (t.node_facts, _READ),
    (t.watch_jobs, _READ),
    (t.query_results, _READ),
    (t.task_status, _READ),
    (t.check_deps, _READ),
    (t.check_updates, _READ_NET),
    (t.set_config, _OVERWRITE),
    (t.parse_results, _LOCAL_WRITE),
    (t.run_nodecheck, _ACTION),
    (t.gen_jobs, _OVERWRITE),
    (t.start_jobs, _ACTION),
    (t.build_benchmark, _ACTION),
]


#: errors whose message is the answer (bad input, missing file, invalid
#: config); the SDK hides any other exception's text from the client
_EXPECTED = (t.ToolError, ConfigError, NodecheckError, ProfileError, OSError)


def _tool(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except _EXPECTED as exc:
            raise ToolError(str(exc)) from exc
    return wrapper


def build_server() -> MCPServer:
    server = MCPServer("cbench", instructions=INSTRUCTIONS)
    for fn, ann in TOOLS:
        server.tool(name=fn.__name__, annotations=ann)(_tool(fn))
    return server


def main() -> None:
    build_server().run("stdio")
