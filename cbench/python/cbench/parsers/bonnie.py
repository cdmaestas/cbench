"""Parser for Bonnie++ I/O benchmark output."""

from __future__ import annotations

import re

from cbench.parsers.base import BenchmarkParser, ParseResult

_THROUGHPUT = (
    "sequential_write_char", "sequential_write_block", "sequential_write_rewrite",
    "sequential_read_char", "sequential_read_block",
)
_RATES = (
    "random_seeks",
    "sequential_create", "sequential_create_read", "sequential_delete",
    "random_create", "random_create_read", "random_delete",
)

# CSV field index of each metric. bonnie++ 1.9x/2.x rows start with the CSV
# format version, e.g.
#   1.98,2.00,host,concurrency,seed,size,chunk,seeks,seek_procs,
#   putc,%cpu,blk_write,%cpu,rewrite,%cpu,getc,%cpu,blk_read,%cpu,seeks,%cpu,
#   num_files,max,min,dirs,file_chunk,
#   seq_create,%cpu,seq_stat,%cpu,seq_del,%cpu,ran_create,%cpu,ran_stat,%cpu,ran_del,%cpu,
#   latencies...
_FIELDS_198 = {
    "sequential_write_char": 9, "sequential_write_block": 11,
    "sequential_write_rewrite": 13, "sequential_read_char": 15,
    "sequential_read_block": 17, "random_seeks": 19,
    "sequential_create": 26, "sequential_create_read": 28, "sequential_delete": 30,
    "random_create": 32, "random_create_read": 34, "random_delete": 36,
}
# bonnie++ 1.03 rows start with the hostname:
#   host,size,putc,%cpu,blk_write,%cpu,rewrite,%cpu,getc,%cpu,blk_read,%cpu,
#   seeks,%cpu,num_files,seq_create,%cpu,seq_stat,%cpu,seq_del,%cpu,
#   ran_create,%cpu,ran_stat,%cpu,ran_del,%cpu
_FIELDS_103 = {
    "sequential_write_char": 2, "sequential_write_block": 4,
    "sequential_write_rewrite": 6, "sequential_read_char": 8,
    "sequential_read_block": 10, "random_seeks": 12,
    "sequential_create": 15, "sequential_create_read": 17, "sequential_delete": 19,
    "random_create": 21, "random_create_read": 23, "random_delete": 25,
}

_FORMAT_198_RE = re.compile(r"1\.9\d")
# bonnie++ prints "+++++" (or "++++") when an operation finished too fast to time.
_TOO_FAST_RE = re.compile(r"\++")


class BonnieParser(BenchmarkParser):
    """Parses bonnie++ CSV result rows (1.03 and 1.9x/2.x formats).

    The iometadata template runs several concurrent instances; throughput and
    rates are summed across rows to give the node aggregate. An operation that
    any instance reported as ``+++++`` (too fast to measure) is left out rather
    than summed short, and is named in ``status_detail``.
    """

    names = ["bonnie"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        status = "NOTSTARTED"
        totals: dict[str, float] = {}
        too_fast: set[str] = set()
        rows = 0

        for line in stdout.splitlines():
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())

            if "Writing" in line or line.startswith("Using uid"):
                status = "STARTED"

            fields = self._row_fields(line.strip().split(","))
            if fields is None:
                continue
            a, layout = fields
            rows += 1
            for key, idx in layout.items():
                val = a[idx].strip()
                if _TOO_FAST_RE.fullmatch(val):
                    too_fast.add(key)
                    continue
                try:
                    totals[key] = totals.get(key, 0.0) + float(val)
                except ValueError:
                    continue  # blank: that test was skipped (e.g. -f, -n 0)

        if rows == 0:
            return ParseResult(status=f"ERROR({status})")

        metrics = {k: v for k, v in totals.items() if k not in too_fast}
        metrics["instances"] = float(rows)
        detail = ""
        if too_fast:
            detail = "too fast to measure (+++++): " + ", ".join(sorted(too_fast))
        return ParseResult(status="PASSED", status_detail=detail, metrics=metrics)

    @staticmethod
    def _row_fields(a: list[str]) -> tuple[list[str], dict[str, int]] | None:
        if len(a) >= 38 and _FORMAT_198_RE.fullmatch(a[0]):
            return a, _FIELDS_198
        if 27 <= len(a) < 38 and re.fullmatch(r"\d+[KMGT]?", a[1]):
            return a, _FIELDS_103
        return None

    def metric_units(self) -> dict[str, str]:
        return (
            dict.fromkeys(_THROUGHPUT, "K/s")
            | dict.fromkeys(_RATES, "/s")
            | {"instances": "count"}
        )
