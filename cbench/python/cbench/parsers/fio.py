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

# clat average line following a read/write block. fio 3.x orders the fields
# min/max/avg/stdev; older fio printed min/avg/stdev/max:
# "     clat (usec): min=51, max=210385, avg=19706.47, stdev=21431.33"
# "   clat (msec): min=1, avg=5.23, stdev=1.00, max=50"
_CLAT_RE = re.compile(
    r"^\s*clat\s+\((\w+)\):.*?\bavg=\s*([\d.]+)"
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


# Job block header: "rand_rw: (groupid=0, jobs=4): err= 0: pid=1234: ..."
_JOB_HEADER_RE = re.compile(r"^(\S+): \(groupid=\d+, jobs=\d+\)")

# cbench's own fio job names (cbench.fioprofile) -> metric role
_ROLES = {
    "seq_rw": "seq", "rand_rw": "rand",
    "md_create": "create", "md_stat": "stat", "md_delete": "delete",
}


def _direction_metrics(lines: list[str]) -> dict[str, float]:
    """Per-direction IOPS / MiB/s / clat avg / clat p99 from fio normal output.

    Takes the first job block's values (with --group_reporting there is one
    block per invocation) and the Run status group bandwidth.
    """
    metrics: dict[str, float] = {}
    current_dir = ""
    in_percentile_block = False

    for line in lines:
        m = _JOB_LINE_RE.match(line)
        if m:
            direction = m.group(1).lower()
            current_dir = direction
            in_percentile_block = False
            metrics.setdefault(f"{direction}_iops", _iops_to_float(m.group(2), m.group(3)))
            metrics.setdefault(f"{direction}_bw_MiB_s", _bw_to_mib_s(m.group(4), m.group(5)))
            continue

        m = _CLAT_RE.match(line)
        if m and current_dir:
            metrics.setdefault(f"{current_dir}_lat_avg_us", _clat_to_us(m.group(2), m.group(1)))
            continue

        if "clat percentiles" in line and current_dir:
            in_percentile_block = True
            continue

        if in_percentile_block and current_dir:
            m99 = _P99_RE.search(line)
            if m99:
                metrics.setdefault(f"{current_dir}_lat_p99_us", float(m99.group(1)))
            # Percentile block ends when we hit a non-pipe line
            if line.strip() and not line.strip().startswith("|"):
                in_percentile_block = False
            continue

        # Run status group — aggregate bandwidth (overrides per-job values)
        m = _RUN_STATUS_RE.match(line)
        if m:
            metrics[f"{m.group(1).lower()}_bw_MiB_s"] = _bw_to_mib_s(m.group(2), m.group(3))

    return metrics


def _role_metrics(role: str, dm: dict[str, float]) -> dict[str, float]:
    if role == "seq":
        return {f"seq_{k}": v for k, v in dm.items() if k.endswith("_bw_MiB_s")}
    if role == "rand":
        return {f"rand_{k}": v for k, v in dm.items() if not k.startswith("trim")}
    # metadata engines report each operation as one I/O, in whichever direction
    ops = sum(v for k, v in dm.items() if k.endswith("_iops"))
    return {f"{role}_ops": ops} if ops else {}


class FioParser(BenchmarkParser):
    """Parses fio Flexible I/O Tester output.

    For cbench's own job set (cbench.fioprofile: ``seq_rw``, ``rand_rw``,
    ``md_create``/``md_stat``/``md_delete``, each run with --group_reporting)
    every job's block is parsed separately:

      seq_rw    -> seq_read_bw_MiB_s, seq_write_bw_MiB_s
      rand_rw   -> rand_{read,write}_{iops,bw_MiB_s,lat_avg_us,lat_p99_us}
      md_*      -> create_ops, stat_ops, delete_ops

    Output without those job names (any other fio job) falls back to generic
    per-direction metrics from the first job block. PASSED if anything parsed;
    NOTSTARTED if no fio output is detected.
    """

    names = ["fio"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        if "CBENCH NOTICE" in stdout:
            for line in stdout.splitlines():
                if "CBENCH NOTICE" in line:
                    return ParseResult(status="NOTICE", status_detail=line.strip())

        lines = stdout.splitlines()
        sections: list[tuple[str, list[str]]] = []
        for line in lines:
            m = _JOB_HEADER_RE.match(line)
            if m:
                sections.append((m.group(1), []))
            elif sections:
                sections[-1][1].append(line)

        metrics: dict[str, float] = {}
        role_sections = [(_ROLES[name], body) for name, body in sections if name in _ROLES]
        if role_sections:
            for role, body in role_sections:
                metrics.update(_role_metrics(role, _direction_metrics(body)))
        else:
            metrics = _direction_metrics(lines)

        if not metrics:
            return ParseResult(status="NOTSTARTED")
        return ParseResult(status="PASSED", metrics=metrics)

    def metric_units(self) -> dict[str, str]:
        units = {}
        for prefix in ("", "rand_"):
            for d in ("read", "write"):
                units[f"{prefix}{d}_iops"] = "IOPS"
                units[f"{prefix}{d}_bw_MiB_s"] = "MiB/s"
                units[f"{prefix}{d}_lat_avg_us"] = "us"
                units[f"{prefix}{d}_lat_p99_us"] = "us"
        units.update({"trim_iops": "IOPS", "trim_bw_MiB_s": "MiB/s",
                      "seq_read_bw_MiB_s": "MiB/s", "seq_write_bw_MiB_s": "MiB/s",
                      "create_ops": "ops/s", "stat_ops": "ops/s", "delete_ops": "ops/s"})
        return units
