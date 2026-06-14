"""Parser for IRS (Implicit Radiation Solver) benchmark output."""

from __future__ import annotations
import re
from cbench.parsers.base import BenchmarkParser, ParseResult


class IrsParser(BenchmarkParser):
    names = ["irs"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        status = "NOTSTARTED"
        metrics: dict[str, float] = {}

        for line in stdout.splitlines():
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())

            if "IRS Sequoia Benchmar" in line:
                status = "STARTED"

            if "BENCHMARK CORRECTNESS" in line:
                if "PASSED" in line:
                    status = "COMPLETED"
                elif "FAILED" in line:
                    status = "DIDNOTCONVERGE"

            m = re.search(r"BENCHMARK microseconds per zone-iteration =\s+(\S+)", line)
            if m:
                metrics["zonetime"] = float(m.group(1)) * 1000

            m = re.search(r"BENCHMARK FOM =\s+(\S+)", line)
            if m:
                metrics["fom"] = float(m.group(1))

        if status == "COMPLETED":
            return ParseResult(status="PASSED", metrics=metrics)
        return ParseResult(status=f"ERROR({status})")

    def metric_units(self) -> dict[str, str]:
        return {"zonetime": "ns", "fom": "zone-iters/s"}
