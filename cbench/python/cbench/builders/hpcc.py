"""Builder for HPCC (HPC Challenge) benchmark.

HPCC is built on HPL and runs seven tests: HPL, STREAM, RandomAccess,
DGEMM, b_eff latency/bandwidth, and FFT (bundled FFTE; optional FFTW).

Requires a BLAS library.  Pass --blas-lib, e.g.:
  cbench build run hpcc --blas-lib "-lopenblas"
"""

from __future__ import annotations

from pathlib import Path

from cbench.builders import BenchmarkBuilder, BuildConfig
from cbench.builders._util import console, run, require, git_clone, install_bins

_GIT_URL = "https://github.com/icl-utk-edu/hpcc.git"
_ARCH = "linux_MPI"


def _write_make_file(src: Path, cfg: BuildConfig) -> None:
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


class HpccBuilder(BenchmarkBuilder):
    name = "hpcc"
    description = "HPC Challenge benchmark suite (HPL, STREAM, DGEMM, FFT, RandomAccess, b_eff)"
    source_url = _GIT_URL

    def fetch(self, srcdir: Path, *, force: bool = False, dry_run: bool = False) -> Path:
        dest = srcdir / "hpcc"
        git_clone(_GIT_URL, dest, force=force, dry_run=dry_run)
        return dest

    def build(self, src: Path, prefix: Path, cfg: BuildConfig, *, dry_run: bool = False) -> list[str]:
        if not cfg.blas_lib:
            console.print(
                "[yellow]Warning: --blas-lib not set; defaulting to -lblas.[/yellow]"
            )
        if not dry_run:
            _write_make_file(src, cfg)
        else:
            console.print(f"  [dim]Would write Make.{_ARCH}[/dim]")
        run(["make", "-j", str(cfg.jobs), f"arch={_ARCH}"], cwd=src, dry_run=dry_run)
        bin_src = src / "bin" / _ARCH
        return install_bins(bin_src, prefix / "bin", ["hpcc"], dry_run=dry_run)

    def check_requires(self) -> list[str]:
        return require("mpicc", "mpif90", "make", "git")
