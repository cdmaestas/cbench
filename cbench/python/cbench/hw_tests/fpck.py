"""hw_test parser: fpck — floating point check."""

import re
from cbench.hw_tests import HwTest


class FpckHwTest(HwTest):
    name = "fpck"
    test_class = "cpu"

    def parse(self, lines: list[str]) -> dict:
        n = self.name
        testfail = 0
        testfail_tmp = 0
        thisproc = 0
        totproc = 0

        for line in lines:
            m = re.search(r"====> process (\d+)/(\d+) begin", line)
            if m:
                thisproc = int(m.group(1))
                totproc = int(m.group(2))
                continue

            m = re.search(r"====> process (\d+)/(\d+) end", line)
            if m:
                thisproc = int(m.group(1))
                totproc = int(m.group(2))
                if thisproc == totproc and thisproc != 0:
                    testfail = max(testfail, testfail_tmp)
                    testfail_tmp = 0
                continue

            if "FAIL" in line:
                testfail_tmp += 1

        return {f"{n}_fail": testfail}
