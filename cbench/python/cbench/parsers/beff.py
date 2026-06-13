"""Parser for b_eff (effective MPI bandwidth) benchmark output."""

from __future__ import annotations
import re
from cbench.parsers.base import BenchmarkParser, ParseResult


class BeffParser(BenchmarkParser):
    names = ["beff"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        status = "NOTSTARTED"
        metrics: dict[str, float] = {}

        for line in stdout.splitlines():
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())

            if "[00] initialization" in line:
                status = "STARTED"

            if "b_eff" in line:
                status = "COMPLETED"

            if "needs at least two parallel mpi processes" in line.lower():
                return ParseResult(status="NOTICE", status_detail="Needs at least two MPI processes")

            m = re.search(r"b_eff\S*\s+=\s+([\d.]+)\s+MB/s", line)
            if m:
                metrics["bidir_bw"] = float(m.group(1))

        if status == "COMPLETED":
            return ParseResult(status="PASSED", metrics=metrics)
        return ParseResult(status=f"ERROR({status})")

    def metric_units(self) -> dict[str, str]:
        return {"bidir_bw": "MB/s"}
