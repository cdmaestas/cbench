"""Parser for IOR I/O benchmark output."""

from __future__ import annotations

import re

from cbench.parsers.base import BenchmarkParser, ParseResult


class IorParser(BenchmarkParser):
    """Parses IOR parallel I/O benchmark output.

    Captures peak write and read bandwidth in MB/s.
    Mirrors perllib/output_parse/ior.pm.
    """

    names = ["ior", "iosanity", "io"]
    alias_spec = r"(ior|ios).*"

    _WRITE_RE = re.compile(r"Max Write:\s+[\d.]+\s+MiB/sec\s+\(([\d.]+)\s+MB/sec\)")
    _READ_RE = re.compile(r"Max Read:\s+[\d.]+\s+MiB/sec\s+\(([\d.]+)\s+MB/sec\)")
    # Older IOR output format
    _WRITE_OLD_RE = re.compile(r"^write\s+([\d.]+)\s+[\d.]+\s+[\d.]+")
    _READ_OLD_RE = re.compile(r"^read\s+([\d.]+)\s+[\d.]+\s+[\d.]+")
    _BEGAN_RE = re.compile(r"^(Run began|Began)\s*:")
    _FINISHED_RE = re.compile(r"^(Run finished|Finished)\s*:")

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        status = "NOTSTARTED"
        write_bw: float | None = None
        read_bw: float | None = None
        # Pre-2.10 IOR has no "Max Write:" line, only bare "write <MiB/s> ..."
        # rows. Modern IOR prints such rows too (per-iteration results and the
        # "Summary of all tests" table, in MiB/s), so they are a fallback only.
        old_write: float | None = None
        old_read: float | None = None

        for line in stdout.splitlines():
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())

            # "Run began:" (IOR 2.x/3.0) or "Began               :" (3.1+)
            if self._BEGAN_RE.match(line):
                status = "STARTED"

            if self._FINISHED_RE.match(line):
                status = "COMPLETED"

            if "cannot open file" in line.lower():
                status = "FILE OPEN ERRORS"

            m = self._WRITE_RE.search(line)
            if m:
                write_bw = float(m.group(1))

            m = self._READ_RE.search(line)
            if m:
                read_bw = float(m.group(1))

            m = self._WRITE_OLD_RE.match(line)
            if m:
                old_write = float(m.group(1))

            m = self._READ_OLD_RE.match(line)
            if m:
                old_read = float(m.group(1))

        if write_bw is None and read_bw is None:
            write_bw, read_bw = old_write, old_read

        if status == "COMPLETED" and (write_bw is not None or read_bw is not None):
            metrics: dict[str, float] = {}
            if write_bw is not None:
                metrics["write"] = write_bw
            if read_bw is not None:
                metrics["read"] = read_bw
            return ParseResult(status="PASSED", metrics=metrics)

        if "FILE OPEN" in status:
            return ParseResult(status="ERROR(FILE OPEN ERRORS)")

        return ParseResult(status=f"ERROR({status})")

    def metric_units(self) -> dict[str, str]:
        return {"write": "MB/s", "read": "MB/s"}
