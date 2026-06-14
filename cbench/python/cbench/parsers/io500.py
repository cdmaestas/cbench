"""Parser for IO500 storage benchmark output."""

from __future__ import annotations

import re

from cbench.parsers.base import BenchmarkParser, ParseResult

# IO500 result lines: [RESULT]   ior-easy-write   1.234 GiB/s : time 60.01 seconds
_RESULT_RE = re.compile(
    r"\[RESULT\]\s+([\w-]+)\s+([\d.]+)\s+(GiB/s|kIOPS)\s*:\s*time\s+([\d.]+)\s+seconds"
)
# [SCORE] Bandwidth 1.234 GiB/s : IOPS 12345.67 kIOPS : TOTAL 123.456
_SCORE_RE = re.compile(
    r"\[SCORE\]\s+Bandwidth\s+([\d.]+)\s+GiB/s\s*:\s*IOPS\s+([\d.]+)\s+kIOPS\s*:\s*TOTAL\s+([\d.]+)"
)


class Io500Parser(BenchmarkParser):
    """Parses IO500 storage benchmark output.

    Captures the final score (bandwidth GiB/s, IOPS kIOPS, composite TOTAL)
    and per-phase results for ior-easy/hard and mdtest-easy/hard.
    """

    names = ["io500"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        metrics: dict[str, float] = {}
        score_found = False

        for line in stdout.splitlines():
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())

            m = _SCORE_RE.search(line)
            if m:
                metrics["bandwidth_GiB_s"] = float(m.group(1))
                metrics["iops_kIOPS"] = float(m.group(2))
                metrics["score"] = float(m.group(3))
                score_found = True
                continue

            m = _RESULT_RE.search(line)
            if m:
                phase = m.group(1).replace("-", "_")
                value = float(m.group(2))
                unit = m.group(3)
                # normalise: GiB/s phases → metric name ends in _GiB_s,
                #            kIOPS phases → metric name ends in _kIOPS
                suffix = "GiB_s" if unit == "GiB/s" else "kIOPS"
                metrics[f"{phase}_{suffix}"] = value

        if score_found:
            return ParseResult(status="PASSED", metrics=metrics)

        if metrics:
            # Partial run — some results but no final score
            return ParseResult(
                status="ERROR(INCOMPLETE)",
                metrics=metrics,
                status_detail="IO500 finished some phases but did not produce a [SCORE] line",
            )

        return ParseResult(status="NOTSTARTED")

    def metric_units(self) -> dict[str, str]:
        return {
            "score": "IO500_score",
            "bandwidth_GiB_s": "GiB/s",
            "iops_kIOPS": "kIOPS",
            "ior_easy_write_GiB_s": "GiB/s",
            "ior_easy_read_GiB_s": "GiB/s",
            "ior_hard_write_GiB_s": "GiB/s",
            "ior_hard_read_GiB_s": "GiB/s",
            "mdtest_easy_write_kIOPS": "kIOPS",
            "mdtest_easy_read_kIOPS": "kIOPS",
            "mdtest_easy_delete_kIOPS": "kIOPS",
            "mdtest_hard_write_kIOPS": "kIOPS",
            "mdtest_hard_read_kIOPS": "kIOPS",
            "mdtest_hard_delete_kIOPS": "kIOPS",
            "find_kIOPS": "kIOPS",
        }
