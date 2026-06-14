"""hw_test parser: cpuinfo — /proc/cpuinfo summary."""

from cbench.hw_tests import HwTest


class CpuInfoHwTest(HwTest):
    name = "cpuinfo"
    test_class = "cpu"

    def parse(self, lines: list[str]) -> dict:
        numcpus = 0
        bogomips = 0.0
        cpumhz = 0.0
        for line in lines:
            if "bogomips" in line.lower() and ":" in line:
                try:
                    bogomips += float(line.split(":")[1].strip().split()[0])
                    numcpus += 1
                except (ValueError, IndexError):
                    pass
            elif "cpu mhz" in line.lower() and ":" in line:
                try:
                    cpumhz += float(line.split(":")[1].strip().split()[0])
                except (ValueError, IndexError):
                    pass
        return {
            f"{self.name}_num": numcpus,
            f"{self.name}_bogomips_total": bogomips,
            f"{self.name}_cpumhz_total": cpumhz,
        }
