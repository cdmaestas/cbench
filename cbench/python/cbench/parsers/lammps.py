"""Parser for LAMMPS (Large-scale Atomic/Molecular Massively Parallel Simulator) output."""

from __future__ import annotations
import re
from cbench.parsers.base import BenchmarkParser, ParseResult


class LammpsParser(BenchmarkParser):
    names = ["lammps"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        status = "NOTSTARTED"
        restart_test = False
        baserun_done = False
        metrics: dict[str, float] = {}

        for line in stdout.splitlines():
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())

            if "= LAMMPS base run =" in line:
                restart_test = True

            if re.search(r"LAMMPS\s+\(", line) and not baserun_done:
                status = "STARTED"

            if baserun_done and "Reading restart" in line:
                status = "RESTARTED"

            if "Failed to reallocate" in line:
                status = "REALLOC FAILED"

            if "Found no restart file" in line:
                status = "NO RESTART FILE"

            if "Dangerous builds" in line:
                if not restart_test:
                    status = "SUCCESSFUL"
                elif not baserun_done:
                    status = "PRERESTART"
                    baserun_done = True
                else:
                    status = "SUCCESSFUL"

            m = re.search(r"Memory usage per processor = ([\d.]+)", line)
            if m:
                metrics["memory"] = float(m.group(1))

            # Performance line: Loop time of X secs on Y procs for Z steps with W atoms
            m = re.search(r"Performance: ([\d.]+) ns/day", line)
            if m:
                metrics["ns_per_day"] = float(m.group(1))

        if status == "SUCCESSFUL":
            return ParseResult(status="PASSED", metrics=metrics)
        return ParseResult(status=f"ERROR({status})")

    def metric_units(self) -> dict[str, str]:
        return {"memory": "MB", "ns_per_day": "ns/day"}
