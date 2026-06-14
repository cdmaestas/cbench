"""Parser for NAS Parallel Benchmarks (NPB) output."""

from __future__ import annotations

import re

from cbench.parsers.base import BenchmarkParser, ParseResult


class NpbParser(BenchmarkParser):
    """Parses NAS Parallel Benchmarks output.

    Mirrors perllib/output_parse/npb.pm.
    """

    names = ["npb"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        status = "NOTSTARTED"
        found_end = False
        mops: float | None = None
        verification: str | None = None

        for line in stdout.splitlines():
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())

            if "NAS Parallel Benchmarks" in line:
                status = "STARTED"

            if "Benchmark Completed" in line:
                found_end = True
                status = "COMPLETED"

            if not found_end:
                continue

            m = re.search(r"Mop/s total\s+=\s+([\d.]+)", line)
            if m:
                mops = float(m.group(1))

            m = re.search(r"Verification\s+=\s+(\S+)", line)
            if m:
                verification = m.group(1)

        if verification and verification.upper() == "SUCCESSFUL":
            return ParseResult(
                status="PASSED",
                metrics={"mops": mops} if mops is not None else {},
            )
        if verification and "UNSUCCESSFUL" in verification.upper():
            return ParseResult(status="ERROR(FAILED VERIFICATION)")

        return ParseResult(status=f"ERROR({status})")

    def metric_units(self) -> dict[str, str]:
        return {"mops": "Mop/s"}
