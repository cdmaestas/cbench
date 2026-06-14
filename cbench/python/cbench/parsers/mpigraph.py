"""Parser for mpiGraph all-pairs MPI bandwidth benchmark output."""

from __future__ import annotations
import re
from cbench.parsers.base import BenchmarkParser, ParseResult


class MpigraphParser(BenchmarkParser):
    names = ["mpigraph"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        status = "NOTSTARTED"
        metrics: dict[str, float] = {}

        for line in stdout.splitlines():
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())

            if "START mpiGraph" in line:
                status = "STARTED"

            if "END mpiGraph" in line:
                status = "COMPLETED"

            m = re.search(r"Send MB/sec (\S+):\s+([\d.]+)", line)
            if m:
                metrics[f"send_{m.group(1)}"] = float(m.group(2))

            m = re.search(r"Recv MB/sec (\S+):\s+([\d.]+)", line)
            if m:
                metrics[f"recv_{m.group(1)}"] = float(m.group(2))

        if status == "COMPLETED":
            return ParseResult(status="PASSED", metrics=metrics)
        return ParseResult(status=f"ERROR({status})")

    def metric_units(self) -> dict[str, str]:
        return {}  # metric names include stat suffix (min/mean/max)
