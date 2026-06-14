"""hw_test parser: numa_gpu — NUMA GPU bandwidth (SHOC)."""

import re
from collections import defaultdict
from cbench.hw_tests import HwTest


class NumaGpuHwTest(HwTest):
    name = "numa_gpu"
    test_class = "gpu"

    def parse(self, lines: list[str]) -> dict:
        n = self.name
        mode: str | None = None
        device: str | None = None
        cpu_location: str | None = None
        mem_location: str | None = None
        bspeed_download: float | None = None
        bspeed_readback: float | None = None

        buckets: dict[str, list[float]] = defaultdict(list)

        for line in lines:
            m = re.search(r"CBENCH RUN_NUMA_TEST COMMAND:.*-(cuda|opencl)", line)
            if m:
                mode = m.group(1)

            m = re.search(r"CBENCH RUN_NUMA_TEST COMMAND:.*-d (\d+)", line)
            if m:
                device = m.group(1)

            m = re.search(r"result for bspeed_download:\s+([\d.]+) GB", line)
            if m:
                bspeed_download = float(m.group(1))

            m = re.search(r"result for bspeed_readback:\s+([\d.]+) GB", line)
            if m:
                bspeed_readback = float(m.group(1))

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

            if (bspeed_download is not None and bspeed_readback is not None
                    and "result for s3d_dp_pcie:" in line
                    and mode and device and cpu_location and mem_location):
                prefix = f"{n}_shoc_pcie_bandwidth"
                buckets[f"{prefix}_BusSpeedDownload_{mode}_Device_{device}_{cpu_location}_{mem_location}"].append(bspeed_download)
                buckets[f"{prefix}_BusSpeedReadback_{mode}_Device_{device}_{cpu_location}_{mem_location}"].append(bspeed_readback)

        return {k: sum(v) / len(v) for k, v in buckets.items()}
