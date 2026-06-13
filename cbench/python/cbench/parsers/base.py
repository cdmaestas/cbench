"""Base class and registry for benchmark output parsers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar

REGISTRY: dict[str, type["BenchmarkParser"]] = {}


@dataclass
class ParseResult:
    status: str                           # PASSED | ERROR(...) | NOTICE | NOTSTARTED
    status_detail: str = ""
    metrics: dict[str, float] = field(default_factory=dict)


class BenchmarkParser:
    """Abstract base class for benchmark output parsers.

    Subclasses register themselves into REGISTRY by setting ``names``.
    """

    names: ClassVar[list[str]] = []

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        for name in cls.names:
            REGISTRY[name] = cls

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        raise NotImplementedError

    def metric_units(self) -> dict[str, str]:
        return {}

    def file_list(self) -> list[str]:
        return ["STDOUT"]
