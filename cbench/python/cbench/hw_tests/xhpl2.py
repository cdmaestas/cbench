"""hw_test parser: xhpl2 — single-node HP Linpack 2.0."""

import re
from cbench.hw_tests import HwTest


class Xhpl2HwTest(HwTest):
    name = "xhpl2"
    test_class = "cpu"

    _RESULT_RE = re.compile(
        r"^\S+\s+\d+\s+\d+\s+\d+\s+\d+\s+([\d.]+)\s+([\d.]+)(e\+(\d+))?"
    )

    def parse(self, lines: list[str]) -> dict:
        n = self.name
        clean = [l for l in lines if not re.search(r"memfree\s+=\s+\d+\s+", l)]

        fail = 0
        max_gflops = 0.0
        total_time = 0.0
        in_result = False
        pending_gflops: float | None = None
        results_found = 0
        results_ok = 0

        i = 0
        while i < len(clean):
            line = clean[i]

            if "Memory allocation failed" in line:
                fail = 1

            if re.search(r"T/V\s+N\s+NB", line):
                in_result = True
                pending_gflops = None
                i += 1
                continue

            if in_result:
                m = self._RESULT_RE.match(line)
                if m:
                    total_time += float(m.group(1))
                    mantissa = float(m.group(2))
                    exp = int(m.group(4)) if m.group(4) else 0
                    gflops = mantissa * (10 ** exp)
                    pending_gflops = gflops
                    results_found += 1
                    in_result = False
                    i += 1
                    continue

            if pending_gflops is not None and re.search(r"Ax-b.*eps.*PASSED", line):
                results_ok += 1
                if pending_gflops > max_gflops:
                    max_gflops = pending_gflops

            i += 1

        if results_found > 0 and results_found != results_ok:
            fail = 1

        return {
            f"{n}_gflops": max_gflops,
            f"{n}_fail": fail,
        }
