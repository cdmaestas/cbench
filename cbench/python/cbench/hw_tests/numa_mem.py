"""hw_test parser: numa_mem — NUMA memory bandwidth (STREAM)."""

from __future__ import annotations

import re
from collections import defaultdict
from cbench.hw_tests import HwTest


class NumaMemHwTest(HwTest):
    name = "numa_mem"
    test_class = "memory"

    def parse(self, lines: list[str]) -> dict:
        n = self.name
        cpu_location: str | None = None
        mem_location: str | None = None
        bin_name: str | None = None
        copy = scale = add = triad = 0.0

        buckets: dict[str, list[float]] = defaultdict(list)

        for line in lines:
            m = re.search(r"--(cpunodebind=\d+)", line)
            if m:
                cpu_location = m.group(1)
            else:
                m = re.search(r"--(physcpubind=\d+)", line)
                if m:
                    cpu_location = m.group(1)

            m = re.search(r"--(membind=\d+)", line)
            if m:
                mem_location = m.group(1)

            if m := re.search(r"(stream-\S+)$", line):
                bin_name = m.group(1)
            elif m := re.search(r"Copy:\s*(\d+)", line):
                copy = float(m.group(1))
            elif m := re.search(r"Scale:\s*(\d+)", line):
                scale = float(m.group(1))
            elif m := re.search(r"Add:\s*(\d+)", line):
                add = float(m.group(1))
            elif m := re.search(r"Triad:\s*(\d+)", line):
                triad = float(m.group(1))
            elif "Solution Validates" in line and cpu_location and mem_location and bin_name:
                loc = f"{cpu_location}_{mem_location}_{bin_name}"
                for metric, val in (("copy", copy), ("scale", scale), ("add", add), ("triad", triad)):
                    buckets[f"{n}_stream_{metric}_{loc}"].append(val)

        return {k: sum(v) / len(v) for k, v in buckets.items()}
