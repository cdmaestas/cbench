"""Parser for OSU MPI benchmark output."""

from __future__ import annotations

import re

from cbench.parsers.base import BenchmarkParser, ParseResult


class OsuParser(BenchmarkParser):
    """Parses OSU MPI micro-benchmark output (bandwidth, latency, message rate).

    Extracts peak bandwidth / minimum latency across all measured message sizes.
    Mirrors perllib/output_parse/osu.pm.
    """

    names = ["osu", "mpioverhead"]

    _TEST_RE = re.compile(r"OSU MPI\s+(.*?)\s+Test", re.IGNORECASE)
    _DATA_RE = re.compile(r"^\s*(\d+)\s+([\d.]+)\s*$")
    _MSGRATE_RE = re.compile(r"^\s*(\d+)\s+\S+\s+[-]?([\d.]+)")

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        status = "NOTSTARTED"
        metric = "unidir_bw"
        max_val = 0.0
        zero_lat: float | None = None

        for line in stdout.splitlines():
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())

            m = self._TEST_RE.search(line)
            if m:
                test = m.group(1)
                if "Bidirectional" in test:
                    metric = "bidir_bw"
                elif "Latency" in test:
                    metric = "latency"
                elif "Message Rate" in test:
                    metric = "message_rate"
                else:
                    metric = "unidir_bw"
                status = "STARTED"
                continue

            m = self._DATA_RE.match(line)
            if m:
                msg_size = int(m.group(1))
                val = float(m.group(2))
                if metric == "latency" and msg_size == 0:
                    zero_lat = val
                max_val = max(max_val, val)
                status = "COMPLETED"
                continue

            m = self._MSGRATE_RE.match(line)
            if m:
                val = float(m.group(2))
                max_val = max(max_val, val)
                status = "COMPLETED"

        if status == "COMPLETED":
            reported = zero_lat if (metric == "latency" and zero_lat is not None) else max_val
            return ParseResult(status="PASSED", metrics={metric: reported})

        return ParseResult(status=f"ERROR({status})")

    def metric_units(self) -> dict[str, str]:
        return {
            "unidir_bw": "MB/s",
            "bidir_bw": "MB/s",
            "latency": "us",
            "message_rate": "messages/s",
        }
