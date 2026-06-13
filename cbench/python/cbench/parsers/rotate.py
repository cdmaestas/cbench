"""Parser for rotate (ring-bandwidth) MPI benchmark output."""

from __future__ import annotations
import re
from cbench.parsers.base import BenchmarkParser, ParseResult


class RotateParser(BenchmarkParser):
    names = ["rotate"]

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

            if "Min Unidirectional" in line:
                found_end = True
                status = "COMPLETED"

            if not found_end:
                continue

            m = re.search(r"Min Unidirectional.*:\s+([\d.]+)", line)
            if m:
                metrics["min_link_bw"] = float(m.group(1))

            m = re.search(r"Max Unidirectional.*:\s+([\d.]+)", line)
            if m:
                metrics["max_link_bw"] = float(m.group(1))

            m = re.search(r"Average Link Unidirectional.*:\s+([\d.]+)", line)
            if m:
                metrics["ave_link_bw"] = float(m.group(1))

            m = re.search(r"Average Aggregate Unidirectional.*:\s+([\d.]+)", line)
            if m:
                metrics["aggregate_bw"] = float(m.group(1))

        if status == "COMPLETED":
            return ParseResult(status="PASSED", metrics=metrics)
        return ParseResult(status=f"ERROR({status})")

    def metric_units(self) -> dict[str, str]:
        return {k: "MB/s" for k in ("min_link_bw", "max_link_bw", "ave_link_bw", "aggregate_bw")}
