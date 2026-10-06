"""Parser for OSU MPI benchmark output."""

from __future__ import annotations

import re

from cbench.parsers.base import BenchmarkParser, ParseResult


class OsuParser(BenchmarkParser):
    """Parses OSU MPI micro-benchmark output (bandwidth, latency, message rate).

    Extracts peak bandwidth across all measured message sizes, and latency at
    the smallest message size. Mirrors perllib/output_parse/osu.pm, which
    reported the 0-byte latency; OSU 7.x starts its latency table at 1 byte,
    so the smallest size measured is used (0 bytes on older OSU).
    """

    names = ["osu"]
    alias_spec = r"osubw|osubibw|osumsgrate"

    _TEST_RE = re.compile(r"OSU MPI\s+(.*?)\s+Test", re.IGNORECASE)
    _DATA_RE = re.compile(r"^\s*(\d+)\s+([\d.]+)\s*$")
    _MSGRATE_RE = re.compile(r"^\s*(\d+)\s+\S+\s+[-]?([\d.]+)")

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        status = "NOTSTARTED"
        metric = "unidir_bw"
        max_val = 0.0
        small_lat: tuple[int, float] | None = None   # (smallest message size, latency)

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
                if metric == "latency" and (small_lat is None or msg_size < small_lat[0]):
                    small_lat = (msg_size, val)
                max_val = max(max_val, val)
                status = "COMPLETED"
                continue

            m = self._MSGRATE_RE.match(line)
            if m:
                val = float(m.group(2))
                max_val = max(max_val, val)
                status = "COMPLETED"

        if status == "COMPLETED":
            reported = small_lat[1] if (metric == "latency" and small_lat) else max_val
            return ParseResult(status="PASSED", metrics={metric: reported})

        return ParseResult(status=f"ERROR({status})")

    def metric_units(self) -> dict[str, str]:
        return {
            "unidir_bw": "MB/s",
            "bidir_bw": "MB/s",
            "latency": "us",
            "message_rate": "messages/s",
        }
