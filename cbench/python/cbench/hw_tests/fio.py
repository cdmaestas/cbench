"""hw_test parser: fio — I/O throughput benchmark (iozone replacement).

Produces the same four throughput metrics as the ``iozone`` hw_test —
sequential/random read/write — so fio can stand in for iozone on nodes where
iozone is unavailable. Values are MB/s (decimal megabytes per second).

Sequential vs random is determined by the fio *job name*: a job whose name
contains "rand" is treated as random. Each job's ``read:``/``write:`` summary
line supplies the bandwidth. The node_hw_test runner is expected to emit four
jobs (e.g. ``seqread``, ``seqwrite``, ``randread``, ``randwrite``); a mixed
``randrw`` job that emits both read: and write: lines maps to the two random
metrics, and a sequential ``rw`` job maps to the two sequential ones.
"""

import re
from cbench.hw_tests import HwTest

# fio job header, e.g. "randwrite: (groupid=2, jobs=1): err= 0: pid=123: ..."
_JOB_HEADER_RE = re.compile(r"^(\S+?):\s+\(groupid=")

# Per-direction summary line, e.g. "  write: IOPS=125k, BW=512MB/s (...)"
_BW_RE = re.compile(
    r"^\s*(read|write):\s+IOPS=\S+,\s+BW=([\d.]+)([KMGT]?i?B)/s",
    re.IGNORECASE,
)


def _bw_to_mb_s(value: str, unit: str) -> float:
    """Convert a fio bandwidth value to decimal MB/s."""
    v = float(value)
    u = unit.upper()
    factors = {
        "B": 1e-6,
        "KB": 1e-3,
        "MB": 1.0,
        "GB": 1e3,
        "TB": 1e6,
        "KIB": 1024 / 1e6,
        "MIB": 1024**2 / 1e6,
        "GIB": 1024**3 / 1e6,
        "TIB": 1024**4 / 1e6,
    }
    return v * factors.get(u, 1.0)


class FioHwTest(HwTest):
    name = "fio"
    test_class = "disk"

    def parse(self, lines: list[str]) -> dict:
        read = write = rread = rwrite = 0.0
        is_random = False

        for line in lines:
            header = _JOB_HEADER_RE.match(line)
            if header:
                is_random = "rand" in header.group(1).lower()
                continue

            m = _BW_RE.match(line)
            if m:
                direction = m.group(1).lower()
                mb_s = _bw_to_mb_s(m.group(2), m.group(3))
                if direction == "read":
                    if is_random:
                        rread = max(rread, mb_s)
                    else:
                        read = max(read, mb_s)
                else:  # write
                    if is_random:
                        rwrite = max(rwrite, mb_s)
                    else:
                        write = max(write, mb_s)

        n = self.name
        return {
            f"{n}_read": read,
            f"{n}_write": write,
            f"{n}_randomread": rread,
            f"{n}_randomwrite": rwrite,
        }
