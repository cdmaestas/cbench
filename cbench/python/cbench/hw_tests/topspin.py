"""hw_test parser: topspin — InfiniBand HCA diagnostics."""

import re
from cbench.hw_tests import HwTest


class TopspinHwTest(HwTest):
    name = "topspin"
    test_class = "topspin"

    def parse(self, lines: list[str]) -> dict:
        n = self.name
        device_fail = 0
        rpm_fail = 0
        firmware_fail = 0
        port0_up = 0
        pci_loopback = 0.0
        port_temp: int | None = None

        for line in lines:
            if re.search(r"PCI Device Check.*FAIL", line):
                device_fail += 1
            elif re.search(r"Host Driver RPM Check.*FAIL", line):
                rpm_fail += 1
            elif re.search(r"HCA Firmware Check.*FAIL", line):
                firmware_fail += 1
            else:
                m = re.search(r"\s+port=(\d+)", line)
                if m:
                    port_temp = int(m.group(1))

                m = re.search(r"\s+port_state=(\S+)", line)
                if m and port_temp == 1:
                    port0_up = 1 if "PORT_ACTIVE" in m.group(1) else 0
                    port_temp = None

                m = re.search(r"4000000\s+([\d.]+)", line)
                if m:
                    pci_loopback = max(pci_loopback, float(m.group(1)))

        return {
            f"{n}_device_fail": device_fail,
            f"{n}_rpm_fail": rpm_fail,
            f"{n}_firmware_fail": firmware_fail,
            f"{n}_port0_up": port0_up,
            f"{n}_pci_loopback": pci_loopback,
        }
