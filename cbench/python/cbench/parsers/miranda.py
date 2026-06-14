"""Parser for Miranda benchmark output."""

from __future__ import annotations
import re
from cbench.parsers.base import BenchmarkParser, ParseResult


class MirandaParser(BenchmarkParser):
    names = ["miranda"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        status = "NOTSTARTED"
        metrics: dict[str, float] = {}

        for line in stdout.splitlines():
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())

            if "test emulating Bill Cabots code and bz4410" in line:
                status = "STARTED"

            if "all done" in line:
                status = "COMPLETED"

            m = re.search(r"Overall Transfer Rate =\s+([\d.]+)\s+MiB/s", line)
            if m:
                metrics["rate"] = float(m.group(1))

        if status == "COMPLETED":
            return ParseResult(status="PASSED", metrics=metrics)
        return ParseResult(status=f"ERROR({status})")

    def metric_units(self) -> dict[str, str]:
        return {"rate": "MiB/s"}
