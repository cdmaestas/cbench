"""hw_test parser: hpcc — single-node HPCC benchmark."""

import re
from cbench.hw_tests import HwTest


class HpccHwTest(HwTest):
    name = "hpcc"
    test_class = "cpu"

    def parse(self, lines: list[str]) -> dict:
        started = completed = False
        data: dict = {}
        n = self.name

        for line in lines:
            if "HPC Challenge Benchmark" in line:
                started = True
            elif "Begin of Summary" in line:
                completed = True

            m = re.search(r"HPL_Tflops=([\d.]+)", line)
            if m:
                data[f"{n}_hpl_gflops"] = float(m.group(1)) * 1000

            m = re.search(r"StarDGEMM_Gflops=([\d.]+)", line)
            if m:
                data[f"{n}_dgemm_gflops"] = float(m.group(1))

            m = re.search(r"PTRANS_GBs=([\d.]+)", line)
            if m:
                data[f"{n}_ptrans_gbs"] = float(m.group(1))

            m = re.search(r"StarRandomAccess_GUPs=([\d.]+)", line)
            if m:
                data[f"{n}_randomaccess_gups"] = float(m.group(1))

            m = re.search(r"StarSTREAM_Triad=([\d.]+)", line)
            if m:
                data[f"{n}_stream_triad_gbs"] = float(m.group(1))

            m = re.search(r"MPIFFT_Gflops=([\d.]+)", line)
            if m:
                data[f"{n}_fft_gflops"] = float(m.group(1))

        fail = 0 if (started and completed) else 1
        data[f"{n}_fail"] = fail
        return data
