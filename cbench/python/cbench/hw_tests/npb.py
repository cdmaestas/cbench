"""hw_test parser: npb — single-node NAS Parallel Benchmarks."""

import re
from cbench.hw_tests import HwTest


class NpbHwTest(HwTest):
    name = "npb"
    test_class = "cpu"

    def parse(self, lines: list[str]) -> dict:
        data: dict = {}
        test = None
        mops_tmp = None
        error = 0

        for line in lines:
            m = re.match(r"====> (\S+)", line)
            if m:
                # flush previous test
                if test is not None and mops_tmp is not None:
                    data[test] = mops_tmp
                test = f"{self.name}_{m.group(1).replace('.', '')}"
                mops_tmp = None

            m = re.search(r"Mop/s total\s+=\s+([\d.]+)", line)
            if m:
                mops_tmp = float(m.group(1))

            m = re.search(r"Verification\s+=\s+(\S+)", line)
            if m:
                status = m.group(1).upper()
                if status != "SUCCESSFUL":
                    error = 1

        # flush last test
        if test is not None and mops_tmp is not None:
            data[test] = mops_tmp

        data[f"{self.name}_error"] = error
        return data
