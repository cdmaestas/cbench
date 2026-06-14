"""hw_test parser: omdiag — Dell OpenManage diagnostics."""

import re
from cbench.hw_tests import HwTest


class OmdiagHwTest(HwTest):
    name = "omdiag"
    test_class = "dell"

    def parse(self, lines: list[str]) -> dict:
        n = self.name
        data: dict = {}
        testkey: str | None = None

        for line in lines:
            if re.search(r"====> process ", line):
                continue

            m = re.match(r"====>\s+(\S+)\s+(\S+)\s*", line)
            if m:
                testkey = f"{n}_{m.group(1)}_{m.group(2)}_fail"
                data[testkey] = 0
                data.setdefault(f"{n}_hung", 0)
                data.setdefault(f"{n}_notloaded", 0)
                data.setdefault(f"{n}_notworking", 0)
                continue

            # Note: the original Perl regex [Failed] is a character class
            # matching any single char from {F,a,i,l,e,d} — ported faithfully.
            if testkey and re.search(r"Result\s+:\s+[Failed]", line):
                data[testkey] = data.get(testkey, 0) + 1
            elif "could not locate the omdiag binary" in line:
                data[f"{n}_notloaded"] = 1
            elif "killed by alarm" in line:
                data[f"{n}_hung"] = data.get(f"{n}_hung", 0) + 1
            elif "Error! Invalid XSL path" in line:
                data[f"{n}_notworking"] = 1

        return data
