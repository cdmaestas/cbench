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


# Any line naming a gpfsperf invocation — its own echo, or cbench's
# "Cbench joblaunch cmd line: /path/gpfsperf read rand ./f ..." — starts the
# section for that operation.
_OP_RE = re.compile(r"gpfsperf(?:-mpi)?\s+(create|read|write|uncache)\s+(\w+)\s+\S+")

# iogpfs_gpfsperf.in brackets its run with these lines
_JOB_START = "Cbench gpfsperf: profile="
_JOB_END = "Cbench gpfsperf: finished"

_PER_OP = ("throughput_MB_s", "iops", "latency_avg_ms", "thread_utilization",
           "bytes_transferred", "cpu_user_pct", "cpu_sys_pct", "cpu_idle_pct", "cpu_wait_pct")


def _section_metrics(lines: list[str]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for line in lines:
        m = _PROCS_RE.match(line)
        if m:
            metrics["nprocesses"] = float(m.group(1))
            metrics["nthreads_per_process"] = float(m.group(2))
            continue
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
        m = _CPU_RE.match(line)
        if m:
            metrics["cpu_user_pct"] = float(m.group(1))
            metrics["cpu_sys_pct"] = float(m.group(2))
            metrics["cpu_idle_pct"] = float(m.group(3))
            metrics["cpu_wait_pct"] = float(m.group(4))
    return metrics


class GpfsperfParser(BenchmarkParser):
    """Parses gpfsperf IBM GPFS/Spectrum Scale benchmark output.

    Handles single-node and MPI (gpfsperf-mpi) output.  Throughput is
    stored as MB/s (converted from the native Kbytes/sec).  IOPS and
    average latency (ms) are captured when present.

    Output covering several operations (the gen-jobs iogpfs_gpfsperf job runs
    create seq, read seq, read rand, write rand) is split per operation and
    the per-operation metrics are prefixed ``<op>_<pattern>_`` (e.g.
    ``read_rand_iops``); a single operation keeps the unprefixed names. A
    gen-jobs job without its end line is ERROR(STARTED).
    """

    names = ["gpfsperf"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        if "CBENCH NOTICE" in stdout:
            for line in stdout.splitlines():
                if "CBENCH NOTICE" in line:
                    return ParseResult(status="NOTICE", status_detail=line.strip())
        if _JOB_START in stdout and _JOB_END not in stdout:
            return ParseResult(status="ERROR(STARTED)",
                               status_detail="gpfsperf job did not finish (still running or killed)")

        sections: list[tuple[str, str, list[str]]] = []
        for line in stdout.splitlines():
            m = _OP_RE.search(line)
            if m:
                op, pattern = m.group(1).lower(), m.group(2).lower()
                # the cbench cmd-line echo and gpfsperf's own echo name the same op
                if not sections or sections[-1][:2] != (op, pattern):
                    sections.append((op, pattern, []))
                continue
            if sections:
                sections[-1][2].append(line)
        if not sections:  # no invocation line at all: parse the whole output
            sections = [("", "", stdout.splitlines())]

        parsed = [(op, pat, _section_metrics(body)) for op, pat, body in sections]
        parsed = [(op, pat, m) for op, pat, m in parsed if "throughput_MB_s" in m]
        if not parsed:
            return ParseResult(status="NOTSTARTED")

        if len(parsed) == 1:
            op, pat, metrics = parsed[0]
            detail = f"operation={op} pattern={pat}" if op else ""
            return ParseResult(status="PASSED", metrics=metrics, status_detail=detail)

        combined: dict[str, float] = {}
        for op, pat, op_metrics in parsed:
            for k, v in op_metrics.items():
                combined[f"{op}_{pat}_{k}" if k in _PER_OP else k] = v
        detail = "operations=" + ",".join(f"{op}_{pat}" for op, pat, _ in parsed)
        return ParseResult(status="PASSED", metrics=combined, status_detail=detail)

    def metric_units(self) -> dict[str, str]:
        base = {
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
        units = dict(base)
        for op in ("create", "read", "write", "uncache"):
            for pat in ("seq", "rand", "randhint", "strided", "backwards"):
                units.update({f"{op}_{pat}_{k}": base[k] for k in _PER_OP})
        return units
