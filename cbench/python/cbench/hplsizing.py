"""HPL.dat / hpccinf.txt generation for gen-jobs (port of Perl xhpl/hpcc_gen_innerloop).

Linpack (xhpl, xhpl2, xhplintel) and HPCC jobs read their problem definition
from an input file in the job directory (the job script ``cd``s there). For
each job, gen-jobs renders it from ``xhpl_dat.in`` / ``hpccinf_txt.in``:

  * N, one per memory utilization factor, from ``compute_n`` — memory-sized,
    so it rounds DOWN and uses the MIN MemTotal across the nodes (a too-large N
    swaps or OOMs on the smallest node);
  * P x Q from ``compute_pq``; a proc count with no acceptable grid is skipped,
    as in Perl.

The ``shakedown`` testset uses a single 0.45 factor to keep Linpack short.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cbench.utils import compute_n, compute_pq

SHAKEDOWN_MEM_UTIL_FACTORS = [0.45]


class HplSizingError(Exception):
    """Values needed to size HPL are unavailable."""


@dataclass(frozen=True)
class InputSpec:
    template: str   # file in the templates dir
    filename: str   # written into the job directory
    prefix: str     # token prefix: XHPL_N_HERE / HPCC_N_HERE ...


_XHPL = InputSpec("xhpl_dat.in", "HPL.dat", "XHPL")
_HPCC = InputSpec("hpccinf_txt.in", "hpccinf.txt", "HPCC")
_SPECS = {"xhpl": _XHPL, "xhpl2": _XHPL, "xhplintel": _XHPL, "hpcc": _HPCC}


def input_spec(benchmark: str) -> InputSpec | None:
    """The input file *benchmark* needs generated, or None."""
    return _SPECS.get(benchmark)


def mem_util_factors(cfg, testset: str) -> list[float]:
    return list(SHAKEDOWN_MEM_UTIL_FACTORS) if testset == "shakedown" else list(cfg.memory_util_factors)


def render(
    spec: InputSpec,
    templates_dir: Path,
    *,
    numprocs: int,
    ppn: int,
    mem_per_node_mb: int,
    factors: list[float],
) -> str | None:
    """Rendered input file, or None when *numprocs* has no usable P x Q grid."""
    pq = compute_pq(numprocs)
    if pq is None:
        return None
    nvals = compute_n(numprocs, ppn, mem_per_node_mb, factors)
    if not nvals or min(nvals) <= 0:
        raise HplSizingError(f"HPL N came out as {nvals} for {numprocs} procs; check memory_util_factors")
    text = (templates_dir / spec.template).read_text()
    tokens = {
        f"{spec.prefix}_NUM_N_HERE": str(len(nvals)),
        f"{spec.prefix}_N_HERE": " ".join(str(n) for n in nvals),
        f"{spec.prefix}_P_HERE": str(pq[0]),
        f"{spec.prefix}_Q_HERE": str(pq[1]),
    }
    for token, value in tokens.items():
        if token not in text:
            raise HplSizingError(f"{spec.template} has no {token}")
        text = text.replace(token, value)
    return text
