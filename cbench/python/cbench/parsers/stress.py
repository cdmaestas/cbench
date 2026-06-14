"""Parser for stress (all-to-all MPI bandwidth stress) benchmark output."""

from __future__ import annotations
import re
from cbench.parsers.base import BenchmarkParser, ParseResult


class StressParser(BenchmarkParser):
    names = ["stress", "longstress"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        status = "NOTSTARTED"
        found_end = False
        metrics: dict[str, float] = {}

        for line in stdout.splitlines():
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())

            if "All to All non-blocking" in line:
                status = "STARTED"

            if "Stress completed" in line:
                found_end = True

            if "Message" in line and "should be from" in line:
                status = "BADMESSAGES"
            elif "wrong size" in line:
                status = "BADMSGSIZE"
            elif "is corrupt" in line:
                status = "BADDATA"

            m = re.search(r"stress runs.*\[([\d.]+)\s+MB/s\s+aggregate\]", line)
            if m:
                metrics["ave_alltoall"] = float(m.group(1))

        if found_end and not any(s in status for s in ("BAD",)):
            return ParseResult(status="PASSED", metrics=metrics)
        return ParseResult(status=f"ERROR({status})")

    def metric_units(self) -> dict[str, str]:
        return {"ave_alltoall": "MB/s"}
