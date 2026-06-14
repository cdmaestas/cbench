"""Parser for Bonnie++ I/O benchmark output."""

from __future__ import annotations
import re
from cbench.parsers.base import BenchmarkParser, ParseResult


class BonnieParser(BenchmarkParser):
    names = ["bonnie"]

    # Bonnie++ CSV output columns (0-indexed after split):
    # hostname, size, seq_write_char_ks, %cp, seq_write_block_ks, %cp,
    # seq_write_rewrite_ks, %cp, seq_read_char_ks, %cp, seq_read_block_ks, %cp,
    # random_seeks_s, %cp, num_files, seq_create_s, %cp, seq_create_read_s, %cp,
    # seq_delete_s, %cp, rand_create_s, %cp, rand_create_read_s, %cp, rand_delete_s, %cp
    _CSV_RE = re.compile(r"^\S+,\S+,\S+,\S+,\S+,.*$")

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        status = "NOTSTARTED"
        metrics: dict[str, float] = {k: 0.0 for k in (
            "sequential_write_char", "sequential_write_block", "sequential_write_rewrite",
            "sequential_read_char", "sequential_read_block", "random_seeks",
            "sequential_create", "sequential_create_read", "sequential_delete",
            "random_create", "random_create_read", "random_delete",
        )}

        for line in stdout.splitlines():
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())

            if "Writing with putc" in line:
                status = "STARTED"

            if re.search(r"Version\s+\S+\s+.*Sequential Output.*Sequential Input", line):
                status = "COMPLETED"

            if self._CSV_RE.match(line):
                a = line.split(",")
                try:
                    metrics["sequential_write_char"] += float(a[2])
                    metrics["sequential_write_block"] += float(a[4])
                    metrics["sequential_write_rewrite"] += float(a[6])
                    metrics["sequential_read_char"] += float(a[8])
                    metrics["sequential_read_block"] += float(a[10])
                    metrics["random_seeks"] += float(a[12])
                    metrics["sequential_create"] += float(a[15])
                    metrics["sequential_create_read"] += float(a[17])
                    metrics["sequential_delete"] += float(a[19])
                    metrics["random_create"] += float(a[21])
                    metrics["random_create_read"] += float(a[23])
                    metrics["random_delete"] += float(a[25])
                except (IndexError, ValueError):
                    pass

        if status == "COMPLETED":
            return ParseResult(status="PASSED", metrics={k: v for k, v in metrics.items() if v > 0})
        return ParseResult(status=f"ERROR({status})")

    def metric_units(self) -> dict[str, str]:
        return {k: "K/s" for k in (
            "sequential_write_char", "sequential_write_block", "sequential_write_rewrite",
            "sequential_read_char", "sequential_read_block",
            "sequential_create", "sequential_create_read", "sequential_delete",
            "random_create", "random_create_read", "random_delete",
        )} | {"random_seeks": "/s"}
