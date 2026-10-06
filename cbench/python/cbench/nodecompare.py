"""Compare per-node results and flag outlier nodes.

Per-node jobs (gen-jobs group gpfs-node, ``iogpfs_gpfsperfnode``) run the same
single-node test on every node of a pool and print ``node=<name>`` on their
``Cbench gpfsperf:`` start line. `cbench parse` collects the PASSED ones, groups
them by benchmark (the job's benchmark name without the trailing node), and for
each metric compares every node with the group median: a node more than
``pct`` percent worse is an outlier. Throughput and IOPS are better when
higher, latency when lower; bookkeeping values (bytes transferred, process
and thread counts, thread utilization) are not compared.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass

_NODE_RE = re.compile(r"^Cbench gpfsperf: .*\bnode=(\S+)", re.MULTILINE)
_SKIP = ("bytes_transferred", "thread_utilization", "nprocesses", "nthreads_per_process")


def node_from_output(stdout: str) -> str | None:
    """The node a per-node job ran on, from its start line; None otherwise."""
    m = _NODE_RE.search(stdout)
    return m.group(1) if m else None


def lower_is_better(metric: str) -> bool:
    return "latency" in metric


def compared(metric: str) -> bool:
    return not any(s in metric for s in _SKIP)


@dataclass
class Outlier:
    group: str
    node: str
    metric: str
    value: float
    median: float
    pct_worse: float


def group_key(benchmark: str, node: str) -> str:
    """'gpfsperfnode-gpfsnode-zimabg1' on node zimabg1 -> 'gpfsperfnode-gpfsnode'."""
    suffix = f"-{node}"
    return benchmark[: -len(suffix)] if benchmark.endswith(suffix) else benchmark


def compare(rows: list[dict], pct: float) -> tuple[dict[str, dict[str, dict[str, float]]], list[Outlier]]:
    """rows: parse results with ``node`` set. Returns ({group: {node: metrics}},
    outliers). Groups with fewer than two PASSED nodes are not compared."""
    groups: dict[str, dict[str, dict[str, float]]] = {}
    for r in rows:
        if r.get("node") and r.get("status") == "PASSED":
            groups.setdefault(group_key(r["benchmark"], r["node"]), {})[r["node"]] = r["metrics"]
    outliers: list[Outlier] = []
    for group, by_node in sorted(groups.items()):
        if len(by_node) < 2:
            continue
        metrics = sorted({m for ms in by_node.values() for m in ms if compared(m)})
        for metric in metrics:
            values = {n: ms[metric] for n, ms in by_node.items() if metric in ms}
            if len(values) < 2:
                continue
            median = statistics.median(values.values())
            if median <= 0:
                continue
            for node, v in sorted(values.items()):
                worse = (v - median) / median if lower_is_better(metric) else (median - v) / median
                if worse * 100 > pct:
                    outliers.append(Outlier(group, node, metric, v, median, worse * 100))
    return groups, outliers
