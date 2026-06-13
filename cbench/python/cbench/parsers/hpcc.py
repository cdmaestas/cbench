"""Parser for HPCC (HPC Challenge) benchmark output."""

from __future__ import annotations

import re

from cbench.parsers.base import BenchmarkParser, ParseResult


class HpccParser(BenchmarkParser):
    """Parses DARPA/DOE HPC Challenge Benchmark output.

    Mirrors perllib/output_parse/hpcc.pm.
    """

    names = ["hpcc"]

    # Maps summary section keys → our metric names
    _METRICS: list[tuple[re.Pattern, str, float]] = [
        (re.compile(r"HPL_Tflops=([\d.]+)"), "hpl", 1000.0),       # Tflops → Gflops
        (re.compile(r"StarDGEMM_Gflops=([\d.]+)"), "ep_dgemm", 1.0),
        (re.compile(r"PTRANS_GBs=([\d.]+)"), "ptrans", 1.0),
        (re.compile(r"StarSTREAM_Triad=([\d.]+)"), "stream_triad", 1.0),
        (re.compile(r"SingleSTREAM_Triad=([\d.]+)"), "single_stream_triad", 1.0),
        (re.compile(r"MPIRandomAccess_GUPs=([\d.]+)"), "random_access", 1.0),
        (re.compile(r"StarFFT_Gflops=([\d.]+)"), "fft", 1.0),
    ]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        status = "NOTSTARTED"
        found_end = False
        metrics: dict[str, float] = {}

        for line in stdout.splitlines():
            if "CBENCH NOTICE" in line:
                return ParseResult(status="NOTICE", status_detail=line.strip())

            if "DARPA/DOE HPC Challenge Benchmark" in line:
                status = "STARTED"

            if "Begin of Summary section" in line:
                found_end = True
                status = "COMPLETED"

            if not found_end:
                continue

            for pattern, key, scale in self._METRICS:
                m = pattern.search(line)
                if m:
                    metrics[key] = float(m.group(1)) * scale

        if status == "COMPLETED":
            return ParseResult(status="PASSED", metrics=metrics)

        return ParseResult(status=f"ERROR({status})")

    def metric_units(self) -> dict[str, str]:
        return {
            "hpl": "GigaFlops",
            "ep_dgemm": "GigaFlops",
            "ptrans": "GB/s",
            "stream_triad": "GB/s",
            "single_stream_triad": "GB/s",
            "random_access": "GUPs",
            "fft": "GigaFlops",
        }
