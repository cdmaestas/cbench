"""hw_test parser: stream2 — STREAM2 memory bandwidth benchmark."""

import re
from cbench.hw_tests import HwTest


class Stream2HwTest(HwTest):
    name = "stream2"
    test_class = "memory"

    def parse(self, lines: list[str]) -> dict:
        fill_vals: list[float] = []
        copy_vals: list[float] = []
        dxapy_vals: list[float] = []
        sum_vals: list[float] = []

        for line in lines:
            # Size  Iter  FILL  COPY  DAXPY  SUM  overhead
            m = re.match(
                r"\s+(\d+)\s+(\d+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)",
                line,
            )
            if m:
                fill_vals.append(float(m.group(3)))
                copy_vals.append(float(m.group(4)))
                dxapy_vals.append(float(m.group(5)))
                sum_vals.append(float(m.group(6)))

        n = self.name
        return {
            f"{n}_fill": max(fill_vals) if fill_vals else 0.0,
            f"{n}_copy": max(copy_vals) if copy_vals else 0.0,
            f"{n}_dxapy": max(dxapy_vals) if dxapy_vals else 0.0,
            f"{n}_sum": max(sum_vals) if sum_vals else 0.0,
        }
