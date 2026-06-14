"""Parser for HPL/Linpack (xhpl) benchmark output."""

from __future__ import annotations

import re

from cbench.parsers.base import BenchmarkParser, ParseResult


class XhplParser(BenchmarkParser):
    """Parses HP Linpack (xhpl / xhpl2) output.

    Extracts the maximum Gflops result across all test blocks that fully passed
    residual checks — matching the logic in perllib/output_parse/xhpl.pm.
    """

    names = ["xhpl", "xhpl2"]

    # Matches lines like:  WR11C2R4      16384  512    4    4   12.34   5.678e+02
    _RESULT_RE = re.compile(
        r"^\S+\s+\d+\s+\d+\s+\d+\s+\d+\s+([\d.]+)\s+([\d.]+)(?:e[+-]\d+)?",
    )
    _GFLOPS_RE = re.compile(
        r"^\S+\s+\d+\s+\d+\s+\d+\s+\d+\s+([\d.]+)\s+([\d.]+)(e[+-]\d+)?",
    )
    _FINISHED_RE = re.compile(r"Finished\s+(\d+)\s+tests")
    _PASSED_RE = re.compile(r"(\d+)\s+tests completed and passed")
    _FAILED_RE = re.compile(r"(\d+)\s+tests completed and failed")

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        lines = stdout.splitlines()

        status = "NOTSTARTED"
        max_gflops = 0.0
        total_time = 0.0
        total_tests = None
        passed_tests = None
        in_result_block = False
        pending_gflops: float | None = None
        pass_checks = 0

        i = 0
        while i < len(lines):
            line = lines[i]

            if "matrix A is randomly generated" in line:
                status = "STARTED"

            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())

            if "Memory allocation failed" in line:
                status = "ALLOCFAILURE"

            if "Illegal input in" in line:
                status = "INPUTFAILURE"

            # Start of a result block
            if re.search(r"T/V\s+N\s+NB", line):
                in_result_block = True
                pending_gflops = None
                pass_checks = 0
                i += 1
                continue

            if in_result_block and i + 1 < len(lines):
                # Result data line is 1 line after the header separator
                m = self._GFLOPS_RE.match(lines[i])
                if m:
                    time_val = float(m.group(1))
                    mantissa = float(m.group(2))
                    exp_str = m.group(3) or ""
                    if exp_str:
                        gflops = mantissa * float(f"1{exp_str}")
                    else:
                        gflops = mantissa
                    total_time += time_val
                    pending_gflops = gflops
                    in_result_block = False
                    i += 1
                    continue

            # PASSED/FAILED checks follow the result line
            if pending_gflops is not None and "PASSED" in line:
                pass_checks += 1
                if pass_checks == 3 and pending_gflops > max_gflops:
                    max_gflops = pending_gflops

            # End-of-run summary
            m = self._FINISHED_RE.search(line)
            if m:
                total_tests = int(m.group(1))
                status = "FINISHED"

            m = self._PASSED_RE.search(line)
            if m:
                passed_tests = int(m.group(1))

            i += 1

        # Determine final status
        if status == "FINISHED" and total_tests is not None and total_tests == passed_tests:
            return ParseResult(
                status="PASSED",
                metrics={"gflops": max_gflops, "runtime": total_time / 60},
            )
        if status == "FINISHED" and passed_tests is not None and passed_tests < (total_tests or 0):
            detail = f"{passed_tests} of {total_tests} PASSED"
            metrics = {"gflops": max_gflops, "runtime": total_time / 60} if max_gflops > 0 else {}
            return ParseResult(status="ERROR(FAILED RESIDUALS)", status_detail=detail, metrics=metrics)

        return ParseResult(status=f"ERROR({status})")

    def metric_units(self) -> dict[str, str]:
        return {"gflops": "GigaFlops", "runtime": "minutes"}
