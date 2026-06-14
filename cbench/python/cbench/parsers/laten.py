"""Parser for laten (MPI bidirectional latency) benchmark output."""

from __future__ import annotations
import re
from cbench.parsers.base import BenchmarkParser, ParseResult


class LatenParser(BenchmarkParser):
    names = ["laten"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        status = "NOTSTARTED"
        parse_state = 0
        min_latency: float | None = None

        for line in stdout.splitlines():
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())

            if "MPI" in line and "Bidir" in line and "latency" in line.lower():
                status = "STARTED"

            if "Processes" in line:
                parse_state = 1

            if parse_state > 0 and "Test Parameters" in line:
                parse_state = 2
                status = "COMPLETED"

            if "--------" in line:
                continue

            if parse_state == 1:
                m = re.search(r"\s+(\d+)\s+([\d.]+)", line)
                if m:
                    lat = float(m.group(2))
                    if min_latency is None or lat < min_latency:
                        min_latency = lat

        metrics = {"latency": min_latency} if min_latency is not None else {}
        if status == "COMPLETED":
            return ParseResult(status="PASSED", metrics=metrics)
        return ParseResult(status=f"ERROR({status})")

    def metric_units(self) -> dict[str, str]:
        return {"latency": "us"}
