"""Parser for gpfsperf IBM GPFS/Spectrum Scale benchmark output.

gpfsperf tests one operation per invocation.  The result line uses 4-space
indent and one of three formats depending on GPFS version:

  Spectrum Scale 4.x/5.x (newer):
    Data rate was 5089216.97 Kbytes/sec, Op Rate was 606.68 Ops/sec,
    Avg Latency was 19.350 milliseconds, thread utilization 0.978,
    bytesTransferred 214748364800

  GPFS 3.x / early 4.x (iops was):
    Data rate was 2330376.56 Kbytes/sec, iops was 284.47,
    thread utilization 1.000

  Minimal (no IOPS/latency computed):
    Data rate was 83583.30 Kbytes/sec, thread utilization 1.000

Throughput is always reported in Kbytes/sec; the parser stores MB/s
(dividing by 1024) for consistency with other parsers.
"""

from __future__ import annotations

import re

from cbench.parsers.base import BenchmarkParser, ParseResult

# Invocation echo line: "/path/to/gpfsperf[-mpi] <op> <pattern> <file>"
_CMD_RE = re.compile(
    r"^(?:\S+/)?gpfsperf(?:-mpi)?\s+(\w+)\s+(\w+)\s+(\S+)", re.MULTILINE
)

# Config line: "  nProcesses N nThreadsPerProcess N"
_PROCS_RE = re.compile(r"^\s{2}nProcesses\s+(\d+)\s+nThreadsPerProcess\s+(\d+)")

# Config line: "  recSize X nBytes Y fileSize Z"
_REC_RE = re.compile(r"^\s{2}recSize\s+(\S+)\s+nBytes\s+(\S+)\s+fileSize\s+(\S+)")

# Result — newer format with Op Rate and Avg Latency (Spectrum Scale 4.x/5.x)
_RESULT_FULL_RE = re.compile(
    r"^\s{4}Data rate was ([\d.]+) Kbytes/sec,"
    r"\s+Op Rate was ([\d.]+) Ops/sec,"
    r"\s+Avg Latency was ([\d.]+) milliseconds,"
    r"\s+thread utilization ([\d.]+)"
    r"(?:,\s+bytesTransferred (\d+))?"
)

# Result — older format with "iops was"
_RESULT_IOPS_RE = re.compile(
    r"^\s{4}Data rate was ([\d.]+) Kbytes/sec,"
    r"\s+iops was ([\d.]+),"
    r"\s+thread utilization ([\d.]+)"
)

# Result — minimal format (no IOPS or latency)
_RESULT_MIN_RE = re.compile(
    r"^\s{4}Data rate was ([\d.]+) Kbytes/sec,"
    r"\s+thread utilization ([\d.]+)"
)

# Optional CPU utilization line
_CPU_RE = re.compile(
    r"^\s{4}CPU utilization:\s+user ([\d.]+)%,\s+sys ([\d.]+)%,"
    r"\s+idle ([\d.]+)%,\s+wait ([\d.]+)%"
)


class GpfsperfParser(BenchmarkParser):
    """Parses gpfsperf IBM GPFS/Spectrum Scale benchmark output.

    Handles single-node and MPI (gpfsperf-mpi) output.  Throughput is
    stored as MB/s (converted from the native Kbytes/sec).  IOPS and
    average latency (ms) are captured when present.
    """

    names = ["gpfsperf"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        if "CBENCH NOTICE" in stdout:
            for line in stdout.splitlines():
                if "CBENCH NOTICE" in line:
                    return ParseResult(status="NOTICE", status_detail=line.strip())

        metrics: dict[str, float] = {}
        operation = ""
        access_pattern = ""

        for line in stdout.splitlines():
            # Command echo — extract operation and access pattern
            if not operation:
                m = _CMD_RE.match(line)
                if m:
                    operation = m.group(1).lower()
                    access_pattern = m.group(2).lower()
                    continue

            # Config: process/thread counts
            m = _PROCS_RE.match(line)
            if m:
                metrics["nprocesses"] = float(m.group(1))
                metrics["nthreads_per_process"] = float(m.group(2))
                continue

            # Result lines — try most specific format first
            m = _RESULT_FULL_RE.match(line)
            if m:
                metrics["throughput_MB_s"] = float(m.group(1)) / 1024.0
                metrics["iops"] = float(m.group(2))
                metrics["latency_avg_ms"] = float(m.group(3))
                metrics["thread_utilization"] = float(m.group(4))
                if m.group(5):
                    metrics["bytes_transferred"] = float(m.group(5))
                continue

            m = _RESULT_IOPS_RE.match(line)
            if m:
                metrics["throughput_MB_s"] = float(m.group(1)) / 1024.0
                metrics["iops"] = float(m.group(2))
                metrics["thread_utilization"] = float(m.group(3))
                continue

            m = _RESULT_MIN_RE.match(line)
            if m:
                metrics["throughput_MB_s"] = float(m.group(1)) / 1024.0
                metrics["thread_utilization"] = float(m.group(2))
                continue

            # Optional CPU utilization
            m = _CPU_RE.match(line)
            if m:
                metrics["cpu_user_pct"] = float(m.group(1))
                metrics["cpu_sys_pct"] = float(m.group(2))
                metrics["cpu_idle_pct"] = float(m.group(3))
                metrics["cpu_wait_pct"] = float(m.group(4))
                continue

        if "throughput_MB_s" not in metrics:
            return ParseResult(status="NOTSTARTED")

        detail = f"operation={operation} pattern={access_pattern}" if operation else ""
        return ParseResult(status="PASSED", metrics=metrics, status_detail=detail)

    def metric_units(self) -> dict[str, str]:
        return {
            "throughput_MB_s": "MB/s",
            "iops": "ops/s",
            "latency_avg_ms": "ms",
            "thread_utilization": "fraction",
            "bytes_transferred": "bytes",
            "nprocesses": "count",
            "nthreads_per_process": "count",
            "cpu_user_pct": "%",
            "cpu_sys_pct": "%",
            "cpu_idle_pct": "%",
            "cpu_wait_pct": "%",
        }
