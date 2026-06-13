"""hw_test parser: streams — STREAM memory bandwidth benchmark."""

import re
from cbench.hw_tests import HwTest


class StreamsHwTest(HwTest):
    name = "streams"
    test_class = "memory"

    def parse(self, lines: list[str]) -> dict:
        copy = scale = add = triad = 0.0
        failed = 0
        copy_tmp = scale_tmp = add_tmp = triad_tmp = 0.0
        failed_tmp = 0

        for line in lines:
            if line.startswith("====> "):
                # delimiter for new binary/iteration
                if failed_tmp == 0:
                    copy = max(copy, copy_tmp)
                    scale = max(scale, scale_tmp)
                    add = max(add, add_tmp)
                    triad = max(triad, triad_tmp)
                copy_tmp = scale_tmp = add_tmp = triad_tmp = 0.0
                failed_tmp = 0
            elif "FAILED" in line.upper() and "validation" in line.lower():
                failed_tmp = 1
                failed = 1
            else:
                m = re.search(r"Copy:\s+([\d.]+)", line)
                if m:
                    copy_tmp = float(m.group(1)) / 1000
                m = re.search(r"Scale:\s+([\d.]+)", line)
                if m:
                    scale_tmp = float(m.group(1)) / 1000
                m = re.search(r"Add:\s+([\d.]+)", line)
                if m:
                    add_tmp = float(m.group(1)) / 1000
                m = re.search(r"Triad:\s+([\d.]+)", line)
                if m:
                    triad_tmp = float(m.group(1)) / 1000

        # flush final binary
        if failed_tmp == 0:
            copy = max(copy, copy_tmp)
            scale = max(scale, scale_tmp)
            add = max(add, add_tmp)
            triad = max(triad, triad_tmp)

        n = self.name
        return {
            f"{n}_copy": copy,
            f"{n}_scale": scale,
            f"{n}_add": add,
            f"{n}_triad": triad,
            f"{n}_failed": failed,
        }
