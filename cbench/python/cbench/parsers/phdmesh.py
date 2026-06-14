"""Parser for phdMesh benchmark output."""

from __future__ import annotations
import re
from cbench.parsers.base import BenchmarkParser, ParseResult


class PhdmeshParser(BenchmarkParser):
    names = ["phdmesh"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        status = "NOTSTARTED"
        metrics: dict[str, float] = {}

        for line in stdout.splitlines():
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())

            if "GEARS meshing" in line:
                status = "STARTED"

            if "N_GEARS Performance results" in line:
                status = "COMPLETED"

            m = re.search(r"Search/step\s+=\s+([\d.]+)\s+sec", line)
            if m:
                metrics["search"] = float(m.group(1))

            m = re.search(r"Rebalance\s+=\s+([\d.]+)\s+sec", line)
            if m:
                metrics["rebalance"] = float(m.group(1))

        if status == "COMPLETED":
            return ParseResult(status="PASSED", metrics=metrics)
        return ParseResult(status=f"ERROR({status})")

    def metric_units(self) -> dict[str, str]:
        return {"search": "s", "rebalance": "s"}
