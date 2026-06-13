"""hw_test parser: nodeperf — single-node DGEMM performance."""

import re
from cbench.hw_tests import HwTest


class NodeperfHwTest(HwTest):
    name = "nodeperf"
    test_class = "cpu"

    def parse(self, lines: list[str]) -> dict:
        mflops = -10.0
        mflops_taskset = 0.0
        mflops_tmp = 0.0
        error = 0

        for line in lines:
            if line.startswith("====> "):
                if "TASKSET" in line:
                    mflops_taskset = max(mflops_taskset, mflops_tmp)
                else:
                    mflops = max(mflops, mflops_tmp)
                mflops_tmp = 0.0
            else:
                m = re.search(
                    r"\(0 of 1\):\s+\S+\s+lda=\s*\d+\s+ldb=\s*\d+\s+ldc=\s*\d+\s+\d+\s+\d+\s+\d+\s+([\d.]+)",
                    line,
                )
                if m:
                    mflops_tmp = float(m.group(1))
                if re.search(r"error|ERROR", line):
                    error = 1

        # flush last
        mflops = max(mflops, mflops_tmp)

        n = self.name
        data: dict = {
            f"{n}_mflops": mflops,
            f"{n}_error": error,
        }
        if mflops_taskset > 0:
            data[f"{n}_mflops_taskset"] = mflops_taskset
        return data
