"""hw_test parser: mpqc — Massively Parallel Quantum Chemistry."""

import re
from cbench.hw_tests import HwTest


class MpqcHwTest(HwTest):
    name = "mpqc"
    test_class = "apps"

    def parse(self, lines: list[str]) -> dict:
        n = self.name
        num = 0
        passed = 0
        walltime_total = 0.0

        for line in lines:
            if re.match(r"^====> \S+$", line.strip()):
                num += 1
            m = re.search(r"mpqc:\s+[\d.]+\s+([\d.]+)", line)
            if m:
                passed += 1
                walltime_total += float(m.group(1))

        return {
            f"{n}_fail": num - passed,
            f"{n}_walltime_total": walltime_total,
        }
