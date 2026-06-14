"""Parser for elbencho distributed storage benchmark output.

elbencho prints a fixed-width results table with two value columns
(FIRST DONE and LAST DONE).  We capture the LAST DONE column as the
canonical result for each metric.

Table format::

    OPERATION RESULT TYPE        FIRST DONE  LAST DONE
    =========== ================    ==========  =========
    WRITE     Elapsed time     :    2m3.241s    2m5.755s
              IOPS             :       33395       33352
              Throughput MiB/s :       33395       33352
              Total MiB        :     4115703     4194304
    ---
    READ      Elapsed time     :    1m58.012s   1m59.001s
              IOPS             :       31000       30500
              Throughput MiB/s :       31000       30500
              Total MiB        :     3900000     3950000
    ---
"""

from __future__ import annotations

import re

from cbench.parsers.base import BenchmarkParser, ParseResult

# Table header that marks the start of results
_HEADER_RE = re.compile(r"OPERATION\s+RESULT TYPE\s+FIRST DONE\s+LAST DONE")

# Phase row: "WRITE     Elapsed time     :     2m3.241s    2m5.755s"
# or continuation rows without the phase name (operation column is blank)
_PHASE_ROW_RE = re.compile(
    r"^([A-Z][A-Z/ ]*\S)?\s{2,}([A-Za-z0-9/ ]+?)\s*:\s+(\S+)\s+(\S+)\s*$"
)

# Error line
_ERROR_RE = re.compile(r"^ERROR:", re.MULTILINE)

# Latency line: "          FILE latency     : [ min=123us avg=456us max=1.23ms ]"
# Matched separately because the trailing content prevents _PHASE_ROW_RE from anchoring at EOL.
_LAT_LINE_RE = re.compile(
    r"^\s+\S.*latency\s*:\s*\[([^\]]*)\]", re.IGNORECASE
)
_LAT_KV_RE = re.compile(r"(min|avg|max)=(\S+)")


def _parse_latency_us(s: str) -> float:
    """Convert a human-readable latency string (e.g. '1.23ms', '456us', '1.5s') to microseconds."""
    s = s.strip()
    if s.endswith("us"):
        return float(s[:-2])
    if s.endswith("ms"):
        return float(s[:-2]) * 1000.0
    if s.endswith("s"):
        return float(s[:-1]) * 1_000_000.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _parse_numeric(s: str) -> float | None:
    """Parse a plain integer or float result value."""
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def _parse_elapsed_s(s: str) -> float | None:
    """Convert elapsed time string (e.g. '2m3.241s', '30.500s', '500ms') to seconds."""
    s = s.strip()
    # hours: 3h25m45s
    m = re.match(r"^(\d+)h(\d+)m(\d+(?:\.\d+)?)s$", s)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    # minutes: 2m3.241s
    m = re.match(r"^(\d+)m(\d+(?:\.\d+)?)s$", s)
    if m:
        return int(m.group(1)) * 60 + float(m.group(2))
    # seconds: 30.500s
    m = re.match(r"^(\d+(?:\.\d+)?)s$", s)
    if m:
        return float(m.group(1))
    # milliseconds: 500ms
    m = re.match(r"^(\d+(?:\.\d+)?)ms$", s)
    if m:
        return float(m.group(1)) / 1000.0
    return None


class ElbenchoParser(BenchmarkParser):
    """Parses elbencho distributed storage benchmark output.

    Captures per-phase throughput (MiB/s), IOPS, elapsed time, and
    latency (avg, min, max in µs) for WRITE, READ, and any other
    phases present.  The composite status is PASSED if the results
    table was found and no ERROR lines appear.
    """

    names = ["elbencho"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        if "CBENCH NOTICE" in stdout:
            for line in stdout.splitlines():
                if "CBENCH NOTICE" in line:
                    return ParseResult(status="NOTICE", status_detail=line.strip())

        if _ERROR_RE.search(stdout):
            # Extract first error line for detail
            for line in stdout.splitlines():
                if line.startswith("ERROR:"):
                    return ParseResult(status="ERROR(RUNTIME)",
                                       status_detail=line.strip())
            return ParseResult(status="ERROR(RUNTIME)")

        if not _HEADER_RE.search(stdout):
            return ParseResult(status="NOTSTARTED")

        metrics: dict[str, float] = {}
        current_phase = ""

        for line in stdout.splitlines():
            # Phase separator — reset current phase to force re-read from next row
            if line.strip() == "---":
                current_phase = ""
                continue

            # Latency lines contain a [ min=... avg=... max=... ] block that
            # extends past the two-value column format; handle before the main RE.
            lat_m = _LAT_LINE_RE.match(line)
            if lat_m and current_phase:
                for kv in _LAT_KV_RE.finditer(lat_m.group(1)):
                    stat, val_str = kv.group(1), kv.group(2)
                    metrics[f"{current_phase}_lat_{stat}_us"] = _parse_latency_us(val_str)
                continue

            m = _PHASE_ROW_RE.match(line)
            if not m:
                continue

            phase_field = (m.group(1) or "").strip()
            result_type = m.group(2).strip().lower()
            # last_done is group(4); first_done is group(3)
            last_val_str = m.group(4).strip()

            if phase_field:
                # Normalise phase name: take first token (e.g. "WRITE" from "WRITE ")
                current_phase = phase_field.split()[0].lower()

            if not current_phase:
                continue

            prefix = current_phase

            # Elapsed time
            if result_type == "elapsed time":
                v = _parse_elapsed_s(last_val_str)
                if v is not None:
                    metrics[f"{prefix}_elapsed_s"] = v
                continue

            # Throughput — "throughput mib/s", "mib/s", "mib/s write", etc.
            if "mib/s" in result_type or "mb/s" in result_type:
                v = _parse_numeric(last_val_str)
                if v is not None:
                    key = f"{prefix}_throughput_MiB_s"
                    # prefer "total" sub-type if present
                    if "total" in result_type:
                        key = f"{prefix}_throughput_total_MiB_s"
                    metrics[key] = v
                continue

            # IOPS
            if result_type.startswith("iops"):
                v = _parse_numeric(last_val_str)
                if v is not None:
                    key = f"{prefix}_iops"
                    if "total" in result_type:
                        key = f"{prefix}_iops_total"
                    metrics[key] = v
                continue

            # FILES/s (metadata ops per second)
            if "files/s" in result_type or "dirs/s" in result_type:
                v = _parse_numeric(last_val_str)
                if v is not None:
                    key = f"{prefix}_ops_per_s"
                    if "total" in result_type:
                        key = f"{prefix}_ops_per_s_total"
                    metrics[key] = v
                continue

            # Total MiB transferred
            if result_type in ("total mib", "mib write", "mib read"):
                v = _parse_numeric(last_val_str)
                if v is not None:
                    metrics[f"{prefix}_total_MiB"] = v
                continue


        if not metrics:
            return ParseResult(status="ERROR(NO_RESULTS)",
                               status_detail="Results table found but no metrics extracted")

        return ParseResult(status="PASSED", metrics=metrics)

    def metric_units(self) -> dict[str, str]:
        return {
            "write_throughput_MiB_s": "MiB/s",
            "write_throughput_total_MiB_s": "MiB/s",
            "read_throughput_MiB_s": "MiB/s",
            "read_throughput_total_MiB_s": "MiB/s",
            "write_iops": "IOPS",
            "write_iops_total": "IOPS",
            "read_iops": "IOPS",
            "read_iops_total": "IOPS",
            "write_elapsed_s": "seconds",
            "read_elapsed_s": "seconds",
            "write_total_MiB": "MiB",
            "read_total_MiB": "MiB",
            "write_lat_min_us": "us",
            "write_lat_avg_us": "us",
            "write_lat_max_us": "us",
            "read_lat_min_us": "us",
            "read_lat_avg_us": "us",
            "read_lat_max_us": "us",
            "write_ops_per_s": "ops/s",
            "read_ops_per_s": "ops/s",
        }
