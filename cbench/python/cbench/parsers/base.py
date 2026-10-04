"""Base class and registry for benchmark output parsers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import ClassVar

REGISTRY: dict[str, type["BenchmarkParser"]] = {}
#: (compiled alias_spec, parser class) — consulted when no name matches exactly.
ALIASES: list[tuple[re.Pattern[str], type["BenchmarkParser"]]] = []


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
    #: Regex (full match) for extra benchmark names this parser handles, e.g.
    #: the IOR parser also takes ``ior1mNtoN``. Mirrors Perl ``alias_spec()``.
    alias_spec: ClassVar[str | None] = None

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        for name in cls.names:
            REGISTRY[name] = cls
        if cls.alias_spec:
            ALIASES.append((re.compile(cls.alias_spec), cls))

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        raise NotImplementedError

    def metric_units(self) -> dict[str, str]:
        return {}

    def file_list(self) -> list[str]:
        return ["STDOUT"]
