"""Parser for fileop (metadata I/O) benchmark output."""

from __future__ import annotations
from cbench.parsers.base import BenchmarkParser, ParseResult


class FileopParser(BenchmarkParser):
    names = ["fileop"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        status = "NOTSTARTED"

        for line in stdout.splitlines():
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())
            if "Fileop:" in line and "A=Avg, B=Best, W=Worst" in line:
                status = "STARTED"
            if "Worst delete" in line:
                status = "COMPLETED"

        if status == "COMPLETED":
            return ParseResult(status="PASSED")
        return ParseResult(status=f"ERROR({status})")
