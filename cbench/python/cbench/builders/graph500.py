"""Builder for Graph500 graph analytics benchmark."""

from __future__ import annotations

import os
from pathlib import Path

from cbench.builders import BenchmarkBuilder, BuildConfig
from cbench.builders._util import run, require, git_clone, install_bins

_GIT_URL = "https://github.com/graph500/graph500.git"

_BINARIES = [
    "graph500_reference_bfs",
    "graph500_reference_bfs_sssp",
]


class Graph500Builder(BenchmarkBuilder):
    name = "graph500"
    description = "Graph500 BFS and BFS+SSSP graph analytics benchmark"
    source_url = _GIT_URL

    def fetch(self, srcdir: Path, *, force: bool = False, dry_run: bool = False) -> Path:
        dest = srcdir / "graph500"
        git_clone(_GIT_URL, dest, force=force, dry_run=dry_run)
        return dest

    def build(self, src: Path, prefix: Path, cfg: BuildConfig, *, dry_run: bool = False) -> list[str]:
        mpi_dir = src / "mpi"
        env = dict(os.environ, MPICC=cfg.mpicc, CC=cfg.mpicc, CFLAGS=cfg.cflags)
        run(["make", "-j", str(cfg.jobs)], cwd=mpi_dir, dry_run=dry_run, env=env)
        return install_bins(mpi_dir, prefix / "bin", _BINARIES, dry_run=dry_run)

    def check_requires(self) -> list[str]:
        return require("mpicc", "make", "git")
