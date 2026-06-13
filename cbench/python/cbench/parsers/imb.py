"""Parser for Intel MPI Benchmarks (IMB) output."""

from __future__ import annotations

import re

from cbench.parsers.base import BenchmarkParser, ParseResult

# IMB benchmark name → our canonical metric name + units
_BENCHMARK_MAP = {
    "PingPong": ("latency_us", "unidir_bw_mbs"),
    "PingPing": ("latency_us", "unidir_bw_mbs"),
    "SendRecv": ("sendrecv_bw_mbs",),
    "Allreduce": ("allreduce_lat_us",),
    "Alltoall": ("alltoall_lat_us",),
    "Bcast": ("bcast_lat_us",),
    "Barrier": ("barrier_lat_us",),
    "Allgather": ("allgather_lat_us",),
    "Reduce": ("reduce_lat_us",),
}

_BENCH_START_RE = re.compile(r"#\s+Benchmarking\s+(\w+)")
_DATA_RE = re.compile(r"^\s*(\d+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)")


class ImbParser(BenchmarkParser):
    """Parses Intel MPI Benchmarks (IMB / Pallas) output.

    Captures the peak bandwidth or minimum latency at 4MB message size
    (or largest measured size) for each benchmark section found.

    Mirrors perllib/output_parse/imb.pm state machine logic.
    """

    names = ["imb", "bandwidth", "latency", "collective", "shakedown"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        status = "NOTSTARTED"
        current_bench: str | None = None
        metrics: dict[str, float] = {}

        # Track peak values per benchmark section
        peak_bw: dict[str, float] = {}
        min_lat: dict[str, float] = {}

        for line in stdout.splitlines():
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())

            m = _BENCH_START_RE.search(line)
            if m:
                current_bench = m.group(1)
                status = "STARTED"
                continue

            if current_bench is None:
                continue

            m = _DATA_RE.match(line)
            if not m:
                continue

            # IMB table columns: bytes  repetitions  t_min[usec]  t_max[usec]  t_avg[usec]  ... Mbytes/sec
            # Exact layout varies by benchmark; capture bandwidth (last column if present)
            parts = line.split()
            try:
                msg_size = int(parts[0])
                lat_us = float(parts[2])          # t_min
                bw_col = float(parts[-1]) if len(parts) >= 6 else 0.0
            except (IndexError, ValueError):
                continue

            key_lat = f"{current_bench}_lat_us"
            key_bw = f"{current_bench}_bw_mbs"

            if key_lat not in min_lat or lat_us < min_lat[key_lat]:
                min_lat[key_lat] = lat_us
            if bw_col > peak_bw.get(key_bw, 0.0):
                peak_bw[key_bw] = bw_col

            status = "COMPLETED"

        metrics.update(min_lat)
        metrics.update({k: v for k, v in peak_bw.items() if v > 0})

        if status == "COMPLETED":
            return ParseResult(status="PASSED", metrics=metrics)
        if status == "STARTED":
            return ParseResult(status="ERROR(INCOMPLETE)")
        return ParseResult(status=f"ERROR({status})")

    def metric_units(self) -> dict[str, str]:
        return {}   # Units are embedded in metric names (_us / _mbs)
