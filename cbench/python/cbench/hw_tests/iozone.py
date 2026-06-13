"""hw_test parser: iozone — I/O throughput benchmark."""

import re
from cbench.hw_tests import HwTest


class IozoneHwTest(HwTest):
    name = "iozone"
    test_class = "disk"

    def parse(self, lines: list[str]) -> dict:
        read = write = rread = rwrite = 0.0
        for line in lines:
            # "Parent sees throughput for N random writers = X KB/sec"
            m = re.search(r"Parent sees throughput for.* random writers\s+=\s+([\d.]+)", line)
            if m:
                rwrite = max(float(m.group(1)) / 1000, rwrite)
            m = re.search(r"Parent sees throughput for.* random readers\s+=\s+([\d.]+)", line)
            if m:
                rread = max(float(m.group(1)) / 1000, rread)
            m = re.search(r"Parent sees throughput for.* writers\s+=\s+([\d.]+)", line)
            if m:
                write = max(float(m.group(1)) / 1000, write)
            m = re.search(r"Parent sees throughput for.* readers\s+=\s+([\d.]+)", line)
            if m:
                read = max(float(m.group(1)) / 1000, read)
        n = self.name
        return {
            f"{n}_read": read,
            f"{n}_write": write,
            f"{n}_randomread": rread,
            f"{n}_randomwrite": rwrite,
        }
