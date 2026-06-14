"""Parser for AMG (Algebraic Multi-Grid) benchmark output."""

from __future__ import annotations
import re
from cbench.parsers.base import BenchmarkParser, ParseResult


class AmgParser(BenchmarkParser):
    names = ["amg"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        status = "NOTSTARTED"
        solver: str = "foo"
        solver_ok: dict[str, int] = {"solver3": 0, "solver4": 0}
        metrics: dict[str, float] = {}

        for line in stdout.splitlines():
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())

            m = re.search(r"===== solver (\d) ===", line)
            if m:
                solver = m.group(1)

            if "SStruct Interface" in line:
                solver_ok[f"solver{solver}"] = 1

            m = re.search(r"System Size \* Iterations / Solve Phase Time:\s+(\S+)", line)
            if m:
                metrics[f"solver{solver}_fom"] = float(m.group(1))
                solver_ok[f"solver{solver}"] = 2

        if solver_ok["solver3"] == 2 and solver_ok["solver4"] == 2:
            return ParseResult(status="PASSED", metrics=metrics)

        if solver_ok["solver3"] == 2 or solver_ok["solver4"] == 1:
            status = "SOLVER4STARTED"
        elif solver_ok["solver3"] == 1:
            status = "SOLVER3STARTED"
        else:
            status = "PARTIALFAILURE"

        return ParseResult(status=f"ERROR({status})", metrics=metrics)

    def metric_units(self) -> dict[str, str]:
        return {"solver3_fom": "sz*iters/s", "solver4_fom": "sz*iters/s"}
