"""hw_test parser: dmidecode — hardware/BIOS info from dmidecode output."""

import re
from cbench.hw_tests import HwTest


class DmidecodeHwTest(HwTest):
    name = "dmidecode"
    test_class = "info"

    def parse(self, lines: list[str]) -> dict:
        data: dict = {}
        section = ""
        n = self.name

        for line in lines:
            if re.match(r"^Handle 0x", line):
                section = ""
            elif line.startswith("BIOS Information"):
                section = "bios"
            elif line.startswith("System Information"):
                section = "system"
            elif line.startswith("Processor Information"):
                section = "processor"
            elif re.match(r"^\s+Version:\s+(.+)$", line) and section == "bios":
                m = re.match(r"^\s+Version:\s+(.+)$", line)
                if m:
                    data[f"{n}_bios_version"] = m.group(1).strip()
            elif re.match(r"^\s+Product Name:\s+(.+)$", line) and section == "system":
                m = re.match(r"^\s+Product Name:\s+(.+)$", line)
                if m:
                    data[f"{n}_system_product"] = m.group(1).strip()
            elif re.match(r"^\s+Max Speed:\s+(\d+)\s+MHz", line) and section == "processor":
                m = re.match(r"^\s+Max Speed:\s+(\d+)\s+MHz", line)
                if m and f"{n}_cpu_max_mhz" not in data:
                    data[f"{n}_cpu_max_mhz"] = float(m.group(1))

        return data
