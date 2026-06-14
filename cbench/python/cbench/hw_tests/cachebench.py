"""hw_test parser: cachebench — cache memory benchmark."""

import re
from cbench.hw_tests import HwTest


class CachebenchHwTest(HwTest):
    name = "cachebench"
    test_class = "cpu"

    def parse(self, lines: list[str]) -> dict:
        n = self.name
        data: dict = {}
        current_test: str | None = None
        current_values: list[float] = []

        def flush() -> None:
            if current_test and current_values:
                data[f"{n}_{current_test}"] = max(current_values)

        for line in lines:
            m = re.match(r"^====> (\S+)$", line.strip())
            if m:
                flush()
                current_test = m.group(1)
                current_values = []
            else:
                m = re.search(r"\d+\s+([\d.]+)", line)
                if m and current_test:
                    try:
                        current_values.append(float(m.group(1)))
                    except ValueError:
                        pass

        flush()
        return data
