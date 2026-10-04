"""Parser for mdtest (metadata I/O) benchmark output."""

from __future__ import annotations

import re

from cbench.parsers.base import BenchmarkParser, ParseResult

_OPS = [
    ("Directory creation", "directory_create"),
    ("Directory stat", "directory_stat"),
    ("Directory rename", "directory_rename"),
    ("Directory removal", "directory_remove"),
    ("File creation", "file_create"),
    ("File stat", "file_stat"),
    ("File read", "file_read"),
    ("File removal", "file_remove"),
    ("Tree creation", "tree_create"),
    ("Tree removal", "tree_remove"),
]

_NUM = r"([-+\d.eE]+)"
# Old mdtest:     "   Directory creation:   9273.825   6788.107   8343.664    668.352"
# hpc/ior mdtest: "   Directory creation        1430.887    250.357    648.277    337.088"
_ROW_RE = re.compile(
    r"^\s*(" + "|".join(label for label, _ in _OPS) + r")\s*:?"
    + rf"\s+{_NUM}\s+{_NUM}\s+{_NUM}\s+{_NUM}\s*$"
)
_KEY = dict(_OPS)


class MdtestParser(BenchmarkParser):
    """Parses the mdtest rate summary (old ``SUMMARY:`` and hpc/ior ``SUMMARY rate``).

    Reports the Mean column in ops/s. Rows from any other summary table (the
    hpc/ior ``SUMMARY time`` table uses the same row labels) are ignored.
    """

    names = ["mdtest"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        status = "NOTSTARTED"
        metrics: dict[str, float] = {}
        in_rate_table = False

        for line in stdout.splitlines():
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())

            if "mdtest" in line and "was launched" in line:
                status = "STARTED"

            if line.startswith("SUMMARY"):
                in_rate_table = line.startswith("SUMMARY:") or line.startswith("SUMMARY rate")
                if in_rate_table:
                    status = "COMPLETED"
                continue

            if in_rate_table:
                m = _ROW_RE.match(line)
                if m:
                    metrics[_KEY[m.group(1)]] = float(m.group(4))  # Mean column

        if status == "COMPLETED" and metrics:
            return ParseResult(status="PASSED", metrics=metrics)
        return ParseResult(status=f"ERROR({status})")

    def metric_units(self) -> dict[str, str]:
        return {key: "ops/s" for _, key in _OPS}
