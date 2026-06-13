"""Cbench hw_test module registry.

Each module exposes an HwTest subclass with:
  - name: str                      (short name, e.g. "cpuinfo")
  - test_class: str                ("cpu", "memory", "disk", ...)
  - parse(lines: list[str]) -> dict[str, float | str]
"""

from __future__ import annotations

from typing import ClassVar

REGISTRY: dict[str, type["HwTest"]] = {}


class HwTest:
    name: ClassVar[str] = ""
    test_class: ClassVar[str] = ""

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if cls.name:
            REGISTRY[cls.name] = cls

    def parse(self, lines: list[str]) -> dict[str, float | str]:
        return {}


# Import all modules so they register themselves.
from cbench.hw_tests import (  # noqa: E402, F401
    cpuinfo,
    meminfo,
    streams,
    stream2,
    stress_cpu,
    stress_disk,
    iozone,
    hpcc,
    npb,
    xhpl,
    nodeperf,
    memtester,
    dmidecode,
)


def get_hw_test(name: str) -> "HwTest | None":
    cls = REGISTRY.get(name)
    return cls() if cls else None
