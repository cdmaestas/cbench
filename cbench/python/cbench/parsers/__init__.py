from cbench.parsers.base import BenchmarkParser, ParseResult, REGISTRY
from cbench.parsers import xhpl, hpcc, imb, npb, ior, osu  # noqa: F401 — registers parsers

__all__ = ["BenchmarkParser", "ParseResult", "REGISTRY", "get_parser"]


def get_parser(name: str) -> "BenchmarkParser | None":
    cls = REGISTRY.get(name)
    return cls() if cls else None
