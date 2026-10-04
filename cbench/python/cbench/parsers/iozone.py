"""Parser for IOzone throughput-mode output (gen-jobs iolocal_iozone job).

Throughput mode (``-t N``) prints one aggregate block per test, e.g.::

    Children see throughput for  4 initial writers  =  123456.78 kB/sec
    Parent sees throughput for  4 initial writers   =  120000.12 kB/sec
    ...
    Children see throughput for 4 random writers    =   23456.78 kB/sec

"Children see" is the sum of the per-thread rates and is what we record, in
MiB/s (iozone's kB is 1024 bytes). The nodehwtest iozone hw_test parser is
separate (hw_tests/iozone.py). iozone ends with ``iozone test complete.``;
output with results but without it is a run that died or is still going.
"""

from __future__ import annotations

import re

from cbench.parsers.base import BenchmarkParser, ParseResult

# iozone test label -> metric prefix
_TESTS = {
    "initial writers": "write",
    "rewriters": "rewrite",
    "readers": "read",
    "re-readers": "reread",
    "reverse readers": "reverse_read",
    "stride readers": "stride_read",
    "random readers": "random_read",
    "mixed workload": "mixed",
    "random writers": "random_write",
    "pwrite writers": "pwrite",
    "pread readers": "pread",
    "fwriters": "fwrite",
    "freaders": "fread",
}

_CHILDREN_RE = re.compile(
    r"Children see throughput for\s+(\d+)\s+(.+?)\s*=\s*([\d.]+)\s*kB/sec"
)
_DONE = "iozone test complete"
# iolocal_iozone.in brackets its two iozone runs with these lines
_JOB_START = "Cbench iozone: profile="
_JOB_END = "Cbench iozone: finished"


class IozoneParser(BenchmarkParser):
    """Aggregate per-test throughput from iozone ``-t`` (throughput) mode."""

    names = ["iozone"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        metrics: dict[str, float] = {}
        threads = None
        for line in stdout.splitlines():
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())
            m = _CHILDREN_RE.search(line)
            if not m:
                continue
            key = _TESTS.get(m.group(2).strip().lower())
            if key:
                threads = int(m.group(1))
                # the cbench job runs iozone twice (throughput at the profile
                # record, then -i 0 -i 2 at 4k); the second run's -i 0 only
                # lays the files out, so the first value of each test wins
                metrics.setdefault(f"{key}_MiB_s", float(m.group(3)) / 1024.0)

        if not metrics:
            return ParseResult(status="NOTSTARTED")
        if _DONE not in stdout or (_JOB_START in stdout and _JOB_END not in stdout):
            return ParseResult(status="ERROR(STARTED)",
                               status_detail="iozone did not finish (still running or killed)")
        if threads:
            metrics["threads"] = float(threads)
        return ParseResult(status="PASSED", metrics=metrics)

    def metric_units(self) -> dict[str, str]:
        return {f"{k}_MiB_s": "MiB/s" for k in _TESTS.values()} | {"threads": "count"}
