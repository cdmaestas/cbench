"""Cbench utility CLI subcommands (run-sizes, find-pq, find-n, npb-procs)."""

from __future__ import annotations

import math
from typing import Optional

import click

from cbench.utils import (
    filter_run_sizes,
    find_pq,
    compute_n,
    find_npb_numprocs,
)


@click.group("utils")
def utils_group() -> None:
    """Sizing and run-list utility commands."""


# ---------------------------------------------------------------------------
# run-sizes
# ---------------------------------------------------------------------------

@utils_group.command("run-sizes")
@click.option("--maxprocs", default=None, type=int, help="Upper bound on proc count")
@click.option("--minprocs", default=1, show_default=True, type=int, help="Lower bound on proc count")
@click.option("--pof2", is_flag=True, help="Include powers of two only")
@click.option("--square", is_flag=True, help="Include perfect squares only")
@click.option("--cube", is_flag=True, help="Include perfect cubes only")
@click.option("--mult", default=None, type=int, help="Include multiples of N")
@click.option("--mult256", is_flag=True, help="Shorthand for --mult 256")
@click.option("--mult100", is_flag=True, help="Shorthand for --mult 100")
@click.option("--mult3", is_flag=True, help="Shorthand for --mult 3")
@click.option("--addr", default=None, type=int, help="Arithmetic sequence step: 1×N, 2×N, …")
@click.option("--try-all", is_flag=True, help="Consider every integer 1…maxprocs")
@click.option("--newline", is_flag=True, help="Print one value per line instead of CSV")
def run_sizes_cmd(
    maxprocs: Optional[int],
    minprocs: int,
    pof2: bool,
    square: bool,
    cube: bool,
    mult: Optional[int],
    mult256: bool,
    mult100: bool,
    mult3: bool,
    addr: Optional[int],
    try_all: bool,
    newline: bool,
) -> None:
    """Print a filtered list of run sizes as a comma-separated list."""
    if mult256:
        mult = 256
    elif mult100:
        mult = 100
    elif mult3:
        mult = 3

    sizes = filter_run_sizes(
        max_procs=maxprocs,
        min_procs=minprocs,
        pof2=pof2,
        square=square,
        cube=cube,
        mult=mult,
        addr=addr,
        try_all=try_all,
    )

    if newline:
        for s in sizes:
            click.echo(s)
    else:
        click.echo(",".join(str(s) for s in sizes))


# ---------------------------------------------------------------------------
# find-pq
# ---------------------------------------------------------------------------

@utils_group.command("find-pq")
@click.option("--nprocs", required=True, type=int, help="Number of MPI ranks")
@click.option("--delta", default=60, show_default=True, type=int,
              help="Search window around sqrt(nprocs)")
@click.option("--decent-only", is_flag=True, help="Only show pairs with ratio in [1.0, 4.0]")
def find_pq_cmd(nprocs: int, delta: int, decent_only: bool) -> None:
    """Find valid HPL grid P×Q decompositions for NPROCS MPI ranks."""
    click.echo(f"sqrt({nprocs}) = {math.sqrt(nprocs):.4f}")
    click.echo(f"NPROCS={nprocs}")
    pairs = find_pq(nprocs, delta=delta)
    for p, q, ratio in pairs:
        if decent_only and not (1.0 <= ratio <= 4.0):
            continue
        decent = "    * DECENT RATIO" if 1.0 <= ratio <= 4.0 else ""
        click.echo(f"P={p} Q={q}   ratio={ratio:.4f}{decent}")


# ---------------------------------------------------------------------------
# find-n
# ---------------------------------------------------------------------------

@utils_group.command("find-n")
@click.option("--nprocs", required=True, type=int, help="Number of MPI ranks")
@click.option("--ppn", required=True, type=int, help="Processes per node")
@click.option("--memory", default=None, type=int,
              help="Memory per node in MB (overrides cluster config)")
@click.option("--util", default=None,
              help="Comma-separated utilization factors e.g. 0.5,0.6,0.7")
@click.option("--config", default=None)
def find_n_cmd(
    nprocs: int,
    ppn: int,
    memory: Optional[int],
    util: Optional[str],
    config: Optional[str],
) -> None:
    """Compute HPL problem size N for each memory utilization factor."""
    from cbench.config import load_config
    cfg = load_config(config)

    mem_mb = memory if memory is not None else cfg.memory_per_node_mb
    factors = (
        [float(x) for x in util.split(",")]
        if util
        else cfg.memory_util_factors
    )

    numnodes = math.ceil(nprocs / ppn)
    total_mb = mem_mb * numnodes
    click.echo(f"total nodes = {numnodes}  total mem = {total_mb} MB")
    click.echo(f"memory_util_factors = {factors}")

    nvals = compute_n(nprocs, ppn, mem_mb, factors)
    click.echo(f"cbench Nvals = {' '.join(str(n) for n in nvals)}")


# ---------------------------------------------------------------------------
# npb-procs
# ---------------------------------------------------------------------------

@utils_group.command("npb-procs")
@click.option("--nprocs", required=True, type=int,
              help="Target proc count — find nearest valid NPB values at or below this")
def npb_procs_cmd(nprocs: int) -> None:
    """Find the closest valid NPB processor counts (power-of-2 and perfect-square)."""
    result = find_npb_numprocs(nprocs)
    click.echo(f"closest power of two   = {result['power_of_two']}")
    click.echo(f"closest perfect square = {result['perfect_square']}")
