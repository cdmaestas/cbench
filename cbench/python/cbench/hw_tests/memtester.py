"""hw_test parser: memtester — memory tester."""

import re
from cbench.hw_tests import HwTest


class MemtesterHwTest(HwTest):
    name = "memtester"
    test_class = "memory"

    def parse(self, lines: list[str]) -> dict:
        fail = 0
        incomplete = 0
        loop = 0
        elapsed = -1.0

        for line in lines:
            if re.search(r"FAILED", line):
                fail = 1
            if re.search(r"Elapsed Time:\s+([\d.]+)\s+minutes", line):
                m = re.search(r"Elapsed Time:\s+([\d.]+)\s+minutes", line)
                if m:
                    elapsed = float(m.group(1))
            if re.search(r"Loop\s+\d+", line):
                m = re.search(r"Loop\s+(\d+)", line)
                if m:
                    loop = int(m.group(1))
            if re.search(r"incomplete|timed out", line, re.IGNORECASE):
                incomplete = 1

        n = self.name
        data: dict = {
            f"{n}_fail": fail,
            f"{n}_incomplete": incomplete,
        }
        if elapsed != -1.0:
            data[f"{n}_elapsed_minutes"] = elapsed
        if loop:
            data[f"{n}_loops"] = loop
        return data
