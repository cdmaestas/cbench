"""Builder for HPL (High Performance Linpack) benchmark.

HPL requires a BLAS library.  Pass --blas-lib to cbench build, e.g.:
  cbench build hpl --blas-lib "-lopenblas"
  cbench build hpl --blas-lib "-L/opt/intel/mkl/lib/intel64 -lmkl_rt"

The builder generates a minimal Make.linux_MPI setup file targeting the
system MPI wrappers.  For production tuning (block size, process grid,
problem size) edit the HPL.dat that gen-jobs generates.
"""

from __future__ import annotations

import os
from pathlib import Path

from cbench.builders import BenchmarkBuilder, BuildConfig
from cbench.builders._util import console, run, require, wget_tarball, install_bins

_TARBALL_URL = "https://www.netlib.org/benchmark/hpl/hpl-2.3.tar.gz"
_ARCH = "linux_MPI"


def _write_make_file(src: Path, cfg: BuildConfig) -> None:
    """Write a minimal Make.<arch> suitable for most Linux + MPI setups."""
    blas_lib = cfg.blas_lib or "-lblas"
    make_path = src / f"Make.{_ARCH}"
    content = f"""\
ARCH         = {_ARCH}
TOPdir       = {src}
INCdir       = $(TOPdir)/include
BINdir       = $(TOPdir)/bin/$(ARCH)
LIBdir       = $(TOPdir)/lib/$(ARCH)
HPLlib       = $(LIBdir)/libhpl.a

MPdir        =
MPinc        =
MPlib        =

LAdir        =
LAinc        = {cfg.blas_inc}
LAlib        = {blas_lib}

F2CDEFS      = -DAdd__ -DF77_INTEGER=int -DStringSunStyle

HPL_INCLUDES = -I$(INCdir) -I$(INCdir)/$(ARCH) $(LAinc) $(MPinc)
HPL_LIBS     = $(HPLlib) $(LAlib) $(MPlib) -lm

HPL_OPTS     =
HPL_DEFS     = $(F2CDEFS) $(HPL_OPTS) $(HPL_INCLUDES)

CC           = {cfg.mpicc}
CCNOOPT      = $(HPL_DEFS)
CCFLAGS      = $(HPL_DEFS) {cfg.cflags}

LINKER       = {cfg.mpif90}
LINKFLAGS    = {cfg.fflags}

ARCHIVER     = ar
ARFLAGS      = r
RANLIB       = echo
"""
    make_path.write_text(content)
    console.print(f"  [cyan]wrote[/cyan] {make_path}")


class HplBuilder(BenchmarkBuilder):
    name = "hpl"
    description = "HPL High Performance Linpack benchmark (requires BLAS)"
    source_url = _TARBALL_URL

    def fetch(self, srcdir: Path, *, force: bool = False, dry_run: bool = False) -> Path:
        return wget_tarball(_TARBALL_URL, srcdir / "hpl", force=force, dry_run=dry_run)

    def build(self, src: Path, prefix: Path, cfg: BuildConfig, *, dry_run: bool = False) -> list[str]:
        if not cfg.blas_lib:
            console.print(
                "[yellow]Warning: --blas-lib not set; defaulting to -lblas. "
                "Pass e.g. --blas-lib '-lopenblas' for a working build.[/yellow]"
            )

        if not dry_run:
            _write_make_file(src, cfg)
        else:
            console.print(f"  [dim]Would write Make.{_ARCH}[/dim]")

        run(
            ["make", "-j", str(cfg.jobs), f"arch={_ARCH}"],
            cwd=src, dry_run=dry_run,
        )

        bin_src = src / "bin" / _ARCH
        installed = install_bins(bin_src, prefix / "bin", ["xhpl"], dry_run=dry_run)
        # Also copy HPL.dat template
        dat_src = bin_src / "HPL.dat"
        if dat_src.exists() and not dry_run:
            import shutil
            shutil.copy2(dat_src, prefix / "bin" / "HPL.dat")
        return installed

    def check_requires(self) -> list[str]:
        return require("mpicc", "mpif90", "make")
