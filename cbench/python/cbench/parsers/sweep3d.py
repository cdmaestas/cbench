"""Parser for SWEEP3D (3-D SN particle transport) benchmark output."""

from __future__ import annotations
import re
from cbench.parsers.base import BenchmarkParser, ParseResult


class Sweep3dParser(BenchmarkParser):
    names = ["sweep3d"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        status = "NOTSTARTED"
        metrics: dict[str, float] = {}

        for line in stdout.splitlines():
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())

            if "SWEEP3D - Method 5" in line:
                status = "STARTED"

            if "Elapsed time" in line:
                status = "SUCCESSFUL"

            m = re.search(r"CPU\s+time was:\s+([\d.]+)", line)
            if m:
                metrics["cpu_time"] = float(m.group(1))

            m = re.search(r"CPU grind time:\s+([\d.]+)", line)
            if m:
                metrics["cpu_grind_time"] = float(m.group(1))

        if status == "SUCCESSFUL":
            return ParseResult(status="PASSED", metrics=metrics)
        return ParseResult(status=f"ERROR({status})")

    def metric_units(self) -> dict[str, str]:
        return {"cpu_time": "s", "cpu_grind_time": "s"}
