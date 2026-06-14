"""hw_test parser: idle — idle load average measurement."""

import re
from cbench.hw_tests import HwTest


class IdleHwTest(HwTest):
    name = "idle"
    test_class = "cpu"

    def parse(self, lines: list[str]) -> dict:
        n = self.name
        load_total = 0.0
        load_samples = 0

        for line in lines:
            m = re.search(r"up .*, .*load average:\s+([\d.]+),\s+([\d.]+),\s+([\d.]+)", line)
            if m:
                load_total += float(m.group(1))
                load_samples += 1

        result: dict = {}
        if load_samples > 0:
            result[f"{n}_load"] = load_total / load_samples
        return result
