"""hw_test parser: meminfo — /proc/meminfo summary."""

import re
from cbench.hw_tests import HwTest


class MemInfoHwTest(HwTest):
    name = "meminfo"
    test_class = "memory"

    def parse(self, lines: list[str]) -> dict:
        mem_total = 0
        for line in lines:
            m = re.search(r"MemTotal:\s+(\d+)", line)
            if m:
                mem_total = int(m.group(1))
        return {f"{self.name}_mem_total": mem_total}
