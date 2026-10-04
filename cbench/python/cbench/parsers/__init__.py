from cbench.parsers.base import ALIASES, BenchmarkParser, ParseResult, REGISTRY
from cbench.parsers import (  # noqa: F401 — side-effect: registers parsers
    xhpl, hpcc, imb, npb, ior, io500, osu, mlperf, elbencho, gpfsperf, fio,
    amg, beff, bonnie, com, fileop, graph500, hpccg, irs,
    lammps, laten, mdtest, miranda, mpibench, mpigraph, mpioverhead,
    phdmesh, rotate, rotlat, routecheck, sppm, sqmr,
    stress, sweep3d, trilinos, iozone,
)

__all__ = ["BenchmarkParser", "ParseResult", "REGISTRY", "get_parser"]


def get_parser(name: str) -> "BenchmarkParser | None":
    """Parser for benchmark *name*: an exact ``names`` match, else an
    ``alias_spec`` match, else the same lookup with a trailing ``-<qualifier>``
    removed (IO profile job names such as ``fio-local``; see cbench.profiles)."""
    cls = REGISTRY.get(name)
    if cls is None:
        cls = next((c for rx, c in ALIASES if rx.fullmatch(name)), None)
    if cls is None and "-" in name:
        return get_parser(name.rsplit("-", 1)[0])
    return cls() if cls else None
