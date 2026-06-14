"""hw_test parser: psnap — packet snapping latency."""

import re
from cbench.hw_tests import HwTest


class PsnapHwTest(HwTest):
    name = "psnap"
    test_class = "cpu"

    def parse(self, lines: list[str]) -> dict:
        n = self.name
        total = 0
        count = 0
        bins = 0

        for line in lines:
            m = re.match(r"^(\d+)\s+(\d+)\s+(\d+)\s+\S+$", line.strip())
            if m:
                total += int(m.group(2)) * int(m.group(3))
                count += int(m.group(3))
                bins += 1

        return {
            f"{n}_ave": total / count if count > 0 else 0,
            f"{n}_numbins": bins,
        }
