"""Parser for mdtest (metadata I/O) benchmark output."""

from __future__ import annotations
import re
from cbench.parsers.base import BenchmarkParser, ParseResult

_OPS = [
    ("Directory creation", "directory_create"),
    ("Directory stat", "directory_stat"),
    ("Directory removal", "directory_remove"),
    ("File creation", "file_create"),
    ("File stat", "file_stat"),
    ("File removal", "file_remove"),
]

_ROW_RE = re.compile(r":\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)")


class MdtestParser(BenchmarkParser):
    names = ["mdtest"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        status = "NOTSTARTED"
        metrics: dict[str, float] = {}

        for line in stdout.splitlines():
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())

            if "mdtest" in line and "was launched" in line:
                status = "STARTED"

            if "SUMMARY:" in line:
                status = "COMPLETED"

            for label, key in _OPS:
                if label in line:
                    m = _ROW_RE.search(line)
                    if m:
                        metrics[key] = float(m.group(3))  # Mean column

        if status == "COMPLETED":
            return ParseResult(status="PASSED", metrics=metrics)
        return ParseResult(status=f"ERROR({status})")

    def metric_units(self) -> dict[str, str]:
        return {key: "ops/s" for _, key in _OPS}
