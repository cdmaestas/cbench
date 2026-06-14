"""hw_test parser: ctcs_memtst — CTCS memory test."""

import re
from cbench.hw_tests import HwTest


class CtcsMemtstHwTest(HwTest):
    name = "ctcs_memtst"
    test_class = "memory"

    def parse(self, lines: list[str]) -> dict:
        n = self.name
        fail = 0
        incomplete = 0
        fail_tmp = 0
        incomplete_tmp = 0
        testrun = 0
        testpass = 0
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
                    if testrun != testpass:
                        incomplete_tmp += 1
                        testrun = testpass = 0
                    fail = max(fail, fail_tmp)
                    incomplete = max(incomplete, incomplete_tmp)
                    fail_tmp = 0
                    incomplete_tmp = 0
                continue

            if "Ceiling" in line:
                testrun += 1
            elif "OK." in line:
                testpass += 1
            elif "Failure" in line:
                fail_tmp += 1

        return {
            f"{n}_fail": fail,
            f"{n}_incomplete": incomplete,
        }
