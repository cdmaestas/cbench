"""hw_test parser: stride — stride memory access benchmark."""

import re
from cbench.hw_tests import HwTest


class StrideHwTest(HwTest):
    name = "stride"
    test_class = "memory"

    def _iter_testcases(self, lines: list[str]):
        """Yield (case_name, case_lines) for each ==testcase==> block."""
        buf: list[str] = []
        case: str | None = None
        for line in lines:
            m = re.match(r"==testcase==> (\S+)\s+at\s+", line)
            if m:
                if case is not None:
                    yield case, buf
                case = m.group(1)
                buf = []
            elif case is not None:
                buf.append(line)
        if case is not None:
            yield case, buf

    def parse(self, lines: list[str]) -> dict:
        n = self.name
        data: dict = {}

        for case, case_lines in self._iter_testcases(lines):
            for line in case_lines:
                m = re.search(r"Elapsed Time:\s+([\d.]+)\s+minutes", line)
                if m:
                    key = f"{n}_{case}_elapsed"
                    try:
                        data[key] = max(data.get(key, 0.0), float(m.group(1)))
                    except ValueError:
                        pass

        return data
