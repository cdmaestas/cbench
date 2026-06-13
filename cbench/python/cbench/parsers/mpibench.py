"""Parser for mpiBench collective MPI benchmark output."""

from __future__ import annotations
import re
from cbench.parsers.base import BenchmarkParser, ParseResult

_LINE_RE = re.compile(
    r"^(\S+)\s+Bytes:\s+(\S+)\s+Iters:\s+\d+\s+Avg:\s+([\d.]+)\s+Min:\s+[\d.]+\s+Max:\s+[\d.]+"
)


class MpibenchParser(BenchmarkParser):
    names = ["mpibench", "collective", "mpisanity"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        status = "NOTSTARTED"
        metrics: dict[str, float] = {}

        for line in stdout.splitlines():
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())

            if "START mpiBench" in line:
                status = "STARTED"

            if "END mpiBench" in line:
                status = "COMPLETED"

            if "buffer corruption detected" in line:
                status = "BUFFER CORRUPTION"

            m = _LINE_RE.match(line)
            if m:
                test, bytes_str, avg = m.group(1), m.group(2), float(m.group(3))
                if test == "Barrier":
                    # Barrier has no message size; record first (smallest) value
                    if test not in metrics:
                        metrics[test] = avg
                elif bytes_str == "8192":
                    metrics[test] = avg

        if status == "COMPLETED":
            return ParseResult(status="PASSED", metrics=metrics)
        return ParseResult(status=f"ERROR({status})")

    def metric_units(self) -> dict[str, str]:
        return {}  # units depend on collective; Barrier=us, others=us at 8K
