"""Parser for com (point-to-point MPI bandwidth/latency) benchmark output."""

from __future__ import annotations
import re
from cbench.parsers.base import BenchmarkParser, ParseResult


class ComParser(BenchmarkParser):
    names = ["com"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        status = "NOTSTARTED"
        com_version = "orig"
        current_table: str = ""
        metrics: dict[str, float] = {}

        for line in stdout.splitlines():
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())

            if "Unidirectional and Bidirectional Communication Test" in line:
                status = "STARTED"
            elif "com Point-to-Point MPI Bandwidth and Latency Benchmark" in line:
                com_version = "new"
                status = "STARTED"

            if com_version == "orig":
                if "Max Unidirectional" in line:
                    status = "COMPLETED"
                m = re.search(r"Max Unidirectional.*:\s+([\d.]+)", line)
                if m:
                    metrics["unidir_bw"] = float(m.group(1))
                m = re.search(r"Max\s+Bidirectional.*:\s+([\d.]+)", line)
                if m:
                    metrics["bidir_bw"] = float(m.group(1))
            else:
                m = re.search(r"(\S+) Test Results", line)
                if m:
                    current_table = m.group(1).lower()

                m = re.search(r"Summary\s*:\s+[\d.]+/[\d.]+/([\d.]+)", line)
                if m and current_table:
                    metrics[f"{current_table}_max_bw"] = float(m.group(1))
                    status = "COMPLETED"

        if status == "COMPLETED":
            return ParseResult(status="PASSED", metrics=metrics)
        return ParseResult(status=f"ERROR({status})")

    def metric_units(self) -> dict[str, str]:
        return {"unidir_bw": "MB/s", "bidir_bw": "MB/s"}
