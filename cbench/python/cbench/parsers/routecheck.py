"""Parser for routecheck (MPI routing validation) benchmark output."""

from __future__ import annotations
import re
from cbench.parsers.base import BenchmarkParser, ParseResult


class RoutecheckParser(BenchmarkParser):
    names = ["routecheck", "mpisanity"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        status = "NOTSTARTED"
        dealers = 0
        metrics: dict[str, float] = {}

        for line in stdout.splitlines():
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())

            if "Timing resolution" in line:
                status = "STARTED"

            if "This program requires more than 1 process" in line:
                return ParseResult(status="NOTICE", status_detail="Needs at least two MPI processes")

            if re.search(r"dealer node is now rank\s+\d+", line):
                dealers += 1

            m = re.search(r"Total time =\s+([\d.]+)", line)
            if m:
                metrics["totaltime"] = float(m.group(1))
                status = "COMPLETED"

            m = re.search(r"Avg loop time =\s+([\d.]+)", line)
            if m:
                metrics["ave_looptime"] = float(m.group(1))
                status = "COMPLETED"

        if status == "COMPLETED":
            return ParseResult(status="PASSED", metrics=metrics)
        return ParseResult(status=f"ERROR({status})")

    def metric_units(self) -> dict[str, str]:
        return {"totaltime": "s", "ave_looptime": "s"}
