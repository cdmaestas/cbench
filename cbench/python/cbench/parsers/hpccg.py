"""Parser for HPCCG (High Performance Conjugate Gradients) benchmark output."""

from __future__ import annotations
import re
from cbench.parsers.base import BenchmarkParser, ParseResult


class HpccgParser(BenchmarkParser):
    names = ["hpccg"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        status = "NOTSTARTED"
        metrics: dict[str, float] = {}

        for line in stdout.splitlines():
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())

            if re.search(r"Process 0 of \d+ is alive", line):
                status = "STARTED"

            m = re.search(r"^Total\s+Time/FLOPS/MFLOPS\s+=\s+(\S+)/(\S+)/(\S+)\.", line)
            if m:
                metrics["time"] = float(m.group(1))
                metrics["mflops"] = float(m.group(3))

            if re.search(r"^Difference between computed and exact\s+=\s+\S+\.", line):
                status = "SUCCESSFUL"

        if status == "SUCCESSFUL":
            return ParseResult(status="PASSED", metrics=metrics)
        if "UNSUCCESSFUL" in status:
            return ParseResult(status="ERROR(FAILED VERIFICATION)")
        return ParseResult(status=f"ERROR({status})")

    def metric_units(self) -> dict[str, str]:
        return {"mflops": "MFlops", "time": "s"}
