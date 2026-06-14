"""Builder for NAS Parallel Benchmarks (NPB) MPI suite.

Builds the MPI class-B variants of all standard benchmarks by default.
Override via extra={'class': 'C', 'suites': 'BT CG EP FT IS LU MG SP'}.

Example:
  cbench build npb --extra class=C
  cbench build npb --extra "class=A suites=EP FT"
"""

from __future__ import annotations

import os
from pathlib import Path

from cbench.builders import BenchmarkBuilder, BuildConfig
from cbench.builders._util import console, run, require, wget_tarball, install_bins

_TARBALL_URL = "https://www.nas.nasa.gov/assets/npb/NPB3.4.2.tar.gz"

_DEFAULT_SUITES = ["BT", "CG", "EP", "FT", "IS", "LU", "MG", "SP"]
_DEFAULT_CLASS = "B"


def _write_make_def(src: Path, cfg: BuildConfig) -> None:
    """Write config/make.def for the NPB MPI suite."""
    (src / "config").mkdir(exist_ok=True)
    content = f"""\
MPIF77 = {cfg.mpif90}
MPICC  = {cfg.mpicc}
FFLAGS = {cfg.fflags}
CFLAGS = {cfg.cflags}
FLINK  = $(MPIF77)
CLINK  = $(MPICC)
F_LIB  =
C_LIB  =
RAND   = randi8
WTIME  = wtime.c
"""
    make_def = src / "config" / "make.def"
    make_def.write_text(content)
    console.print(f"  [cyan]wrote[/cyan] {make_def}")


class NpbBuilder(BenchmarkBuilder):
    name = "npb"
    description = "NAS Parallel Benchmarks MPI suite (BT, CG, EP, FT, IS, LU, MG, SP)"

    def fetch(self, srcdir: Path, *, force: bool = False, dry_run: bool = False) -> Path:
        top = wget_tarball(_TARBALL_URL, srcdir / "npb", force=force, dry_run=dry_run)
        return top / "NPB3.4-MPI"

    def build(self, src: Path, prefix: Path, cfg: BuildConfig, *, dry_run: bool = False) -> list[str]:
        npb_class = cfg.extra.get("class", _DEFAULT_CLASS).upper()
        suite_str = cfg.extra.get("suites", " ".join(_DEFAULT_SUITES))
        suites = suite_str.upper().split()

        if not dry_run:
            _write_make_def(src, cfg)
        else:
            console.print("  [dim]Would write config/make.def[/dim]")

        installed = []
        for suite in suites:
            run(
                ["make", suite, f"CLASS={npb_class}", f"-j{cfg.jobs}"],
                cwd=src, dry_run=dry_run,
            )
            binary_name = f"{suite}.{npb_class}.x"
            installed += install_bins(
                src / "bin", prefix / "bin",
                [binary_name], dry_run=dry_run,
            )

        return installed

    def check_requires(self) -> list[str]:
        return require("mpicc", "mpif90", "make")
