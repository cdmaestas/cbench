"""Parser for Trilinos Epetra benchmark output."""

from __future__ import annotations
import re
from cbench.parsers.base import BenchmarkParser, ParseResult

_METRICS = ["SpMV", "SpMM2", "SpMM4", "SpMM8", "NORM", "DOT", "AXPY"]


class TrilinosParser(BenchmarkParser):
    names = ["trilinos"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        status = "NOTSTARTED"
        metrics: dict[str, float] = {}

        for line in stdout.splitlines():
            line = line.strip()

            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line)

            if line.startswith("Epetra Benchmark Test Version"):
                status = "STARTED"

            if line.startswith("MFLOP/s"):
                parts = line.split()
                # Format: MFLOP/s  <procs>  SpMV  SpMM2  SpMM4  SpMM8  NORM  DOT  AXPY
                if len(parts) >= 9:
                    for i, key in enumerate(_METRICS):
                        try:
                            metrics[key] = float(parts[i + 2])
                        except (IndexError, ValueError):
                            pass
                    if "AXPY" in metrics:
                        status = "SUCCESSFUL"
                    else:
                        status = "UNSUCCESSFUL"

        if status == "SUCCESSFUL":
            return ParseResult(status="PASSED", metrics=metrics)
        if status == "UNSUCCESSFUL":
            return ParseResult(status="ERROR(FAILED VERIFICATION)")
        return ParseResult(status=f"ERROR({status})")

    def metric_units(self) -> dict[str, str]:
        return {k: "MFlops" for k in _METRICS}
