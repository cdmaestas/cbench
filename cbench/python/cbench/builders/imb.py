"""Builder for Intel MPI Benchmarks (IMB)."""

from __future__ import annotations

from pathlib import Path

from cbench.builders import BenchmarkBuilder, BuildConfig
from cbench.builders._util import console, run, require, git_clone, install_bins

_GIT_URL = "https://github.com/intel/mpi-benchmarks.git"

# Binaries produced under src_c/ after make
_BINARIES = [
    "IMB-MPI1",
    "IMB-P2P",
    "IMB-EXT",
    "IMB-IO",
    "IMB-NBC",
    "IMB-RMA",
]


class ImbBuilder(BenchmarkBuilder):
    name = "imb"
    description = "Intel MPI Benchmarks — latency, bandwidth, collective"

    def fetch(self, srcdir: Path, *, force: bool = False, dry_run: bool = False) -> Path:
        dest = srcdir / "mpi-benchmarks"
        git_clone(_GIT_URL, dest, force=force, dry_run=dry_run)
        return dest

    def build(self, src: Path, prefix: Path, cfg: BuildConfig, *, dry_run: bool = False) -> list[str]:
        import os
        env = dict(os.environ, CC=cfg.mpicc, CXX=cfg.mpicxx)
        run(["make", "-j", str(cfg.jobs), "-C", "src_c"], cwd=src, dry_run=dry_run, env=env)
        bin_dir = src / "src_c"
        return install_bins(bin_dir, prefix / "bin", _BINARIES, dry_run=dry_run)

    def check_requires(self) -> list[str]:
        return require("mpicc", "make", "git")
