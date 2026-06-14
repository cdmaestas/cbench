"""Parser for fio (Flexible I/O Tester) benchmark output.

fio emits one summary block per job followed by a "Run status group" section.
We parse the per-direction (read/write) summary lines and the clat latency
block (average and p99).

Typical output structure::

    read: IOPS=316k, BW=1234MiB/s (1294MB/s)(72.3GiB/30001msec)
       clat (usec): min=2, avg=12.34, stdev=5.67, max=1234
      clat percentiles (usec):
       |  1.00th=[    4], ..., 99.00th=[   50], 99.90th=[  100], ...
    write: IOPS=100k, BW=400MiB/s (419MB/s)(24.0GiB/60001msec)
       clat (usec): min=3, avg=20.00, stdev=8.00, max=2000
      clat percentiles (usec):
       | ..., 99.00th=[   80], ...

    Run status group 0 (all jobs):
       READ: bw=1234MiB/s (1294MB/s), ..., run=60001-60001msec
      WRITE: bw=400MiB/s  (419MB/s),  ..., run=60001-60001msec
"""

from __future__ import annotations

import re

from cbench.parsers.base import BenchmarkParser, ParseResult

# Per-direction summary line inside a job block
# "  read: IOPS=316k, BW=1234MiB/s ..."
# "  write: IOPS=12.3k, BW=49.3MiB/s ..."
_JOB_LINE_RE = re.compile(
    r"^\s*(read|write|trim):\s+IOPS=([\d.]+)([kKmMgG]?),\s+BW=([\d.]+)(\w+)/s",
    re.IGNORECASE,
)

# clat average line following a read/write block
# "   clat (usec): min=2, avg=12.34, stdev=5.67, max=1234"
# "   clat (msec): min=1, avg=5.23, stdev=1.00, max=50"
_CLAT_RE = re.compile(
    r"^\s*clat\s+\((\w+)\):\s+min=[\d.]+,\s+avg=([\d.]+)"
)

# Percentile line — we grab the 99.00th value
# "   |  ..., 99.00th=[   50], ..."
_P99_RE = re.compile(r"99\.00th=\[\s*([\d]+)\s*\]")

# Run status group — final per-direction totals
# "   READ: bw=1234MiB/s (1294MB/s), ..."
# "  WRITE: bw=400MiB/s ..."
_RUN_STATUS_RE = re.compile(
    r"^\s+(READ|WRITE|TRIM):\s+bw=([\d.]+)(\w+)/s",
    re.IGNORECASE,
)

_MULTIPLIERS = {"k": 1e3, "m": 1e6, "g": 1e9, "K": 1e3, "M": 1e6, "G": 1e9}


def _iops_to_float(value: str, suffix: str) -> float:
    mul = _MULTIPLIERS.get(suffix, 1.0)
    return float(value) * mul


def _bw_to_mib_s(value: str, unit: str) -> float:
    """Convert bandwidth to MiB/s regardless of reported unit."""
    v = float(value)
    u = unit.upper()
    if u.startswith("GIB"):
        return v * 1024.0
    if u.startswith("KIB"):
        return v / 1024.0
    if u.startswith("MIB"):
        return v
    # MB/s (decimal) — close enough
    if u.startswith("MB"):
        return v / 1.048576
    if u.startswith("GB"):
        return v * 1000.0 / 1.048576
    if u.startswith("KB"):
        return v / 1048.576
    return v


def _clat_to_us(avg: str, unit: str) -> float:
    v = float(avg)
    u = unit.lower()
    if u == "msec" or u == "ms":
        return v * 1000.0
    if u == "nsec" or u == "ns":
        return v / 1000.0
    return v  # usec


class FioParser(BenchmarkParser):
    """Parses fio Flexible I/O Tester output.

    Captures per-direction IOPS, bandwidth (MiB/s), average completion
    latency (µs), and 99th-percentile latency (µs) for read, write, and
    trim operations.  A run is PASSED if at least one direction produced
    metrics; NOTSTARTED if no fio output is detected.
    """

    names = ["fio"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        if "CBENCH NOTICE" in stdout:
            for line in stdout.splitlines():
                if "CBENCH NOTICE" in line:
                    return ParseResult(status="NOTICE", status_detail=line.strip())

        metrics: dict[str, float] = {}
        run_status_seen = False

        # Track current direction context for clat/percentile lines
        current_dir: str = ""
        in_percentile_block = False

        for line in stdout.splitlines():
            # Per-job direction summary
            m = _JOB_LINE_RE.match(line)
            if m:
                direction = m.group(1).lower()
                current_dir = direction
                in_percentile_block = False
                iops = _iops_to_float(m.group(2), m.group(3))
                bw = _bw_to_mib_s(m.group(4), m.group(5))
                # Only record the first occurrence (first job); Run status
                # group gives the aggregate which we also capture below.
                if f"{direction}_iops" not in metrics:
                    metrics[f"{direction}_iops"] = iops
                if f"{direction}_bw_MiB_s" not in metrics:
                    metrics[f"{direction}_bw_MiB_s"] = bw
                continue

            # clat average
            m = _CLAT_RE.match(line)
            if m and current_dir:
                key = f"{current_dir}_lat_avg_us"
                if key not in metrics:
                    metrics[key] = _clat_to_us(m.group(2), m.group(1))
                continue

            # Start of percentile block
            if "clat percentiles" in line and current_dir:
                in_percentile_block = True
                continue

            # p99 inside percentile block
            if in_percentile_block and current_dir:
                m99 = _P99_RE.search(line)
                if m99:
                    key = f"{current_dir}_lat_p99_us"
                    if key not in metrics:
                        metrics[key] = float(m99.group(1))
                # Percentile block ends when we hit a non-pipe line
                if line.strip() and not line.strip().startswith("|"):
                    in_percentile_block = False
                continue

            # Run status group — aggregate bandwidth (overrides per-job values)
            m = _RUN_STATUS_RE.match(line)
            if m:
                run_status_seen = True
                direction = m.group(1).lower()
                bw = _bw_to_mib_s(m.group(2), m.group(3))
                metrics[f"{direction}_bw_MiB_s"] = bw
                continue

        if not metrics:
            return ParseResult(status="NOTSTARTED")

        return ParseResult(status="PASSED", metrics=metrics)

    def metric_units(self) -> dict[str, str]:
        return {
            "read_iops": "IOPS",
            "write_iops": "IOPS",
            "trim_iops": "IOPS",
            "read_bw_MiB_s": "MiB/s",
            "write_bw_MiB_s": "MiB/s",
            "trim_bw_MiB_s": "MiB/s",
            "read_lat_avg_us": "us",
            "write_lat_avg_us": "us",
            "read_lat_p99_us": "us",
            "write_lat_p99_us": "us",
        }
