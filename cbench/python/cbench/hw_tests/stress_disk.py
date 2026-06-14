"""hw_test parser: stress_disk — disk stress test."""

import re
from cbench.hw_tests import HwTest


class StressDiskHwTest(HwTest):
    name = "stress_disk"
    test_class = "disk"

    def parse(self, lines: list[str]) -> dict:
        elapsed = -1.0
        fail = 1
        for line in lines:
            m = re.search(r"Stress Elapsed Time:\s+([\d.]+)\s+minutes", line)
            if m:
                elapsed = float(m.group(1))
            if re.search(r"stress: info: \[\d+\] successful run completed", line):
                fail = 0
        n = self.name
        data: dict = {f"{n}_fail": fail}
        if elapsed != -1.0:
            data[f"{n}_minutes"] = elapsed
        return data
