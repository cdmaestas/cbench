"""Parser for SQMR (MPI message rate) benchmark output."""

from __future__ import annotations
import re
from cbench.parsers.base import BenchmarkParser, ParseResult

_DATA_RE = re.compile(
    r"(\S+)\s+(\S+)\s+([\d.]+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)"
)


class SqmrParser(BenchmarkParser):
    names = ["sqmr"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        status = "NOTSTARTED"
        max_rate = 0.0

        for line in stdout.splitlines():
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())

            if "SQMR v1" in line:
                status = "STARTED"

            if "Cbench end timestamp" in line and "SQMR ERROR" not in status:
                status = "COMPLETED"

            if re.match(r"^ERROR ", line):
                status = "SQMR ERROR"

            m = _DATA_RE.match(line)
            if m:
                try:
                    max_rate = max(max_rate, float(m.group(6)))
                except ValueError:
                    pass

        if status == "COMPLETED":
            return ParseResult(status="PASSED", metrics={"message_rate": max_rate})
        return ParseResult(status=f"ERROR({status})")

    def metric_units(self) -> dict[str, str]:
        return {"message_rate": "msgs/s"}
