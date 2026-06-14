"""Parser for sPPM (structured Piecewise Parabolic Method) benchmark output."""

from __future__ import annotations
import re
from cbench.parsers.base import BenchmarkParser, ParseResult


class SppmParser(BenchmarkParser):
    names = ["sppm"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        status = "NOTSTARTED"
        metrics: dict[str, float] = {}

        for line in stdout.splitlines():
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())

            if "sPPM Benchmark" in line:
                status = "STARTED"

            if "Finished Calculation" in line:
                status = "SUCCESSFUL"

            m = re.search(
                r"TOTAL-HYD cpu, wall, ratio:\s+([\d.]+).*?([\d.]+)\s+[\d.]+\s+Finished Calculation",
                line,
            )
            if m:
                metrics["hyd_cpu_time"] = float(m.group(1))
                metrics["hyd_wall_time"] = float(m.group(2))

            m = re.search(r"TOTAL-I/O cpu, wall, ratio:\s+([\d.]+)\s+([\d.]+)", line)
            if m:
                metrics["io_cpu_time"] = float(m.group(1))
                metrics["io_wall_time"] = float(m.group(2))

        if status == "SUCCESSFUL":
            return ParseResult(status="PASSED", metrics=metrics)
        return ParseResult(status=f"ERROR({status})")

    def metric_units(self) -> dict[str, str]:
        return {k: "s" for k in ("hyd_cpu_time", "hyd_wall_time", "io_cpu_time", "io_wall_time")}
