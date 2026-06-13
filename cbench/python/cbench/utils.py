"""Cbench sizing and run-list utility functions.

These are pure-math helpers used by job generation and HPL/NPB setup.
All functions are side-effect free and importable for use in other modules.
"""

from __future__ import annotations

import math

# Default run sizes mirroring Perl @run_sizes (from templates.py)
from cbench.templates import RUN_SIZES


# ---------------------------------------------------------------------------
# predicates
# ---------------------------------------------------------------------------

def is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def is_perfect_square(n: int) -> bool:
    if n < 0:
        return False
    root = int(math.isqrt(n))
    return root * root == n


def is_perfect_cube(n: int) -> bool:
    if n <= 0:
        return n == 0
    root = round(n ** (1 / 3))
    for r in (root - 1, root, root + 1):
        if r > 0 and r ** 3 == n:
            return True
    return False


def is_multiple_of(n: int, m: int) -> bool:
    return m > 0 and n % m == 0


# ---------------------------------------------------------------------------
# run-size list
# ---------------------------------------------------------------------------

def filter_run_sizes(
    *,
    max_procs: int | None = None,
    min_procs: int | None = None,
    pof2: bool = False,
    square: bool = False,
    cube: bool = False,
    mult: int | None = None,
    addr: int | None = None,
    try_all: bool = False,
) -> list[int]:
    """Return a filtered list of run sizes matching the requested criteria.

    If none of pof2/square/cube/mult/addr are set, returns all sizes in
    the configured range (same as Perl default behaviour — no filter).
    """
    upper = max_procs if max_procs is not None else (RUN_SIZES[-1] if RUN_SIZES else 1)
    lower = min_procs or 1

    base = list(range(1, upper + 1)) if try_all else [s for s in RUN_SIZES if s <= upper]

    # if no filter flags set, return everything in range
    any_filter = pof2 or square or cube or (mult is not None) or (addr is not None)

    if addr is not None:
        result: list[int] = []
        i = 1
        while i * addr <= upper:
            v = i * addr
            if v >= lower:
                result.append(v)
            i += 1
        return result

    if not any_filter:
        return [n for n in base if n >= lower]

    result = []
    for n in base:
        if n < lower:
            continue
        if pof2 and is_power_of_two(n):
            result.append(n)
        elif square and is_perfect_square(n):
            result.append(n)
        elif cube and is_perfect_cube(n):
            result.append(n)
        elif mult is not None and is_multiple_of(n, mult):
            result.append(n)
    return result


# ---------------------------------------------------------------------------
# HPL grid: find P × Q
# ---------------------------------------------------------------------------

def find_pq(nprocs: int, delta: int = 60) -> list[tuple[int, int, float]]:
    """Return all valid (P, Q, ratio) pairs for an HPL grid of *nprocs* ranks.

    A pair is included when Q divides nprocs exactly.  Results are sorted by
    how close Q is to sqrt(nprocs).  Pairs with ratio in [1.0, 4.0] are
    considered "decent".
    """
    if nprocs <= 0:
        return []
    start = int(math.isqrt(nprocs))
    lo = max(1, start - delta)
    hi = start + delta
    results: list[tuple[int, int, float]] = []
    for q in range(lo, hi + 1):
        if q == 0:
            continue
        if nprocs % q == 0:
            p = nprocs // q
            ratio = q / p
            results.append((p, q, ratio))
    return results


# ---------------------------------------------------------------------------
# HPL problem size N
# ---------------------------------------------------------------------------

def compute_n(
    nprocs: int,
    ppn: int,
    memory_per_node_mb: int,
    memory_util_factors: list[float],
) -> list[int]:
    """Compute HPL problem size N for each utilization factor.

    N is chosen so that the N×N double matrix fills the requested fraction
    of total available memory.
    """
    numnodes = math.ceil(nprocs / ppn)
    total_bytes = memory_per_node_mb * numnodes * 1024 * 1024
    results: list[int] = []
    for factor in memory_util_factors:
        n = math.sqrt(total_bytes / 8) * factor
        n = int(n * 1.02)
        results.append(n)
    return results


# ---------------------------------------------------------------------------
# NPB: find valid proc counts
# ---------------------------------------------------------------------------

def find_npb_numprocs(nprocs: int) -> dict[str, int]:
    """Find the closest valid proc counts for NPB benchmarks.

    NPB class A/B/C need either a perfect square (BT/SP/LU) or a power of
    two (CG/FT/IS/EP/MG).  Returns the largest value <= nprocs for each.
    """
    best_pof2 = 0
    best_square = 0
    tmp = nprocs
    while tmp > 0 and (best_pof2 == 0 or best_square == 0):
        if best_pof2 == 0 and is_power_of_two(tmp):
            best_pof2 = tmp
        if best_square == 0 and is_perfect_square(tmp):
            best_square = tmp
        tmp -= 1
    return {"power_of_two": best_pof2, "perfect_square": best_square}
