"""hw_test parser: xhpl — single-node HPL/Linpack."""

import re
from cbench.hw_tests import HwTest


class XhplHwTest(HwTest):
    name = "xhpl"
    test_class = "cpu"

    def parse(self, lines: list[str]) -> dict:
        fail = 0
        max_gflops = 0.0
        in_result = False

        for line in lines:
            if "WR" in line or re.search(r"^\s*W[A-Z]{1,2}\s+", line):
                parts = line.split()
                # HPL result line: WR... N NB P Q Time Gflops
                if len(parts) >= 7:
                    try:
                        gflops = float(parts[-1])
                        max_gflops = max(max_gflops, gflops)
                        in_result = True
                    except ValueError:
                        pass

            if re.search(r"FAILED", line):
                fail = 1

        if max_gflops == 0.0 and not in_result:
            fail = 1

        n = self.name
        return {
            f"{n}_gflops": max_gflops,
            f"{n}_fail": fail,
        }
