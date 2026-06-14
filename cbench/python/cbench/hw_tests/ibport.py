"""hw_test parser: ibport — InfiniBand port diagnostics."""

from cbench.hw_tests import HwTest


class IbportHwTest(HwTest):
    name = "ibport"
    test_class = "thunderbird"

    def parse(self, lines: list[str]) -> dict:
        n = self.name
        result: dict = {}
        for line in lines:
            if "RESULT" in line:
                if "PASSED" in line:
                    result[f"{n}_fail"] = 0
                elif "FAILED" in line:
                    result[f"{n}_fail"] = 1
        return result
