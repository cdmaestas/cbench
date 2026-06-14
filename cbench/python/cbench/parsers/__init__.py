from cbench.parsers.base import BenchmarkParser, ParseResult, REGISTRY
from cbench.parsers import (  # noqa: F401 — side-effect: registers parsers
    xhpl, hpcc, imb, npb, ior, io500, osu,
    amg, beff, bonnie, com, fileop, graph500, hpccg, irs,
    lammps, laten, mdtest, miranda, mpibench, mpigraph, mpioverhead,
    phdmesh, rotate, rotlat, routecheck, sppm, sqmr,
    stress, sweep3d, trilinos,
)

__all__ = ["BenchmarkParser", "ParseResult", "REGISTRY", "get_parser"]


def get_parser(name: str) -> "BenchmarkParser | None":
    cls = REGISTRY.get(name)
    return cls() if cls else None
