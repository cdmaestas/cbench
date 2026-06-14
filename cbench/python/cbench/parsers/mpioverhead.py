"""Parser for mpioverhead benchmark output."""

from __future__ import annotations

import re

from cbench.parsers.base import BenchmarkParser, ParseResult


class MpioverheadParser(BenchmarkParser):
    names = ["mpioverhead", "ohead"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        lines = stdout.splitlines()
        status = "NOTSTARTED"
        start_time: int | None = None
        end_time: int | None = None
        launch_time: int | None = None
        total_mpi_mem = 0
        num_ranks_found = 0

        for line in lines:
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())

            m = re.search(r"Timestamp before MPI launch = (\d+)", line)
            if m:
                start_time = int(m.group(1))

            m = re.search(r"Rank 0: MPI launch timestamp = (\d+)", line)
            if m:
                end_time = int(m.group(1))
                status = "STARTED"
                if start_time is not None:
                    launch_time = end_time - start_time

            m = re.search(r"Rank \d+ \(\S+\): mem used.*= (\d+).*= \d+ kB", line)
            if m:
                num_ranks_found += 1
                total_mpi_mem += int(m.group(1))

        if status == "STARTED" and launch_time is not None and num_ranks_found > 0:
            ave_mpi_mem = (total_mpi_mem / num_ranks_found) / 1024
            return ParseResult(
                status="PASSED",
                metrics={"launch_time": launch_time, "ave_mpi_mem": ave_mpi_mem},
            )
        return ParseResult(status=f"ERROR({status})")

    def metric_units(self) -> dict[str, str]:
        return {"launch_time": "seconds", "ave_mpi_mem": "MegaBytes"}
