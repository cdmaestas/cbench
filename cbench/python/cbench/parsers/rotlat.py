"""Parser for rotlat (ring-latency) MPI benchmark output."""

from __future__ import annotations
import re
from cbench.parsers.base import BenchmarkParser, ParseResult


class RotlatParser(BenchmarkParser):
    names = ["rotlat"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        status = "NOTSTARTED"
        found_end = False
        metrics: dict[str, float] = {}

        for line in stdout.splitlines():
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())

            if "rotate 0" in line:
                status = "STARTED"

            if "Must use at least 2 processes" in line:
                return ParseResult(status="NOTICE", status_detail="Needs at least two MPI processes")

            if "Min Link" in line:
                found_end = True
                status = "COMPLETED"

            if not found_end:
                continue

            m = re.search(r"Min Link.*:\s+([\d.]+)", line)
            if m:
                metrics["min_latency"] = float(m.group(1))

            m = re.search(r"Max Link.*:\s+([\d.]+)", line)
            if m:
                metrics["max_latency"] = float(m.group(1))

            m = re.search(r"Average Link.*:\s+([\d.]+)", line)
            if m:
                metrics["ave_latency"] = float(m.group(1))

        if status == "COMPLETED":
            return ParseResult(status="PASSED", metrics=metrics)
        return ParseResult(status=f"ERROR({status})")

    def metric_units(self) -> dict[str, str]:
        return {k: "us" for k in ("min_latency", "max_latency", "ave_latency")}
