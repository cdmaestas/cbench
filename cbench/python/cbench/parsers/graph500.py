"""Parser for Graph500 benchmark output."""

from __future__ import annotations
import re
from cbench.parsers.base import BenchmarkParser, ParseResult


class Graph500Parser(BenchmarkParser):
    names = ["graph500"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        status = "NOTSTARTED"
        metrics: dict[str, float] = {}

        for line in stdout.splitlines():
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())

            if "Running BFS 0" in line:
                status = "STARTED"

            if "stddev_validate:" in line:
                status = "SUCCESSFUL"

            m = re.search(r"^harmonic_mean_TEPS:\s+(\S+) TEPS", line)
            if m:
                metrics["harmonic_mean_teps"] = float(m.group(1))

            m = re.search(r"^median_TEPS:\s+(\S+) TEPS", line)
            if m:
                metrics["median_teps"] = float(m.group(1))

            m = re.search(r"^construction_time:\s+(\S+) s", line)
            if m:
                metrics["construction_time"] = float(m.group(1))

        if status == "SUCCESSFUL":
            return ParseResult(status="PASSED", metrics=metrics)
        return ParseResult(status=f"ERROR({status})")

    def metric_units(self) -> dict[str, str]:
        return {"harmonic_mean_teps": "TEPS", "median_teps": "TEPS", "construction_time": "s"}
