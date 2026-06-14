"""Builder for mpiGraph (LLNL all-pairs MPI bandwidth benchmark)."""

from __future__ import annotations

import os
from pathlib import Path

from cbench.builders import BenchmarkBuilder, BuildConfig
from cbench.builders._util import run, require, git_clone, install_bins

_GIT_URL = "https://github.com/LLNL/mpiGraph.git"


class MpiGraphBuilder(BenchmarkBuilder):
    name = "mpigraph"
    description = "mpiGraph LLNL all-pairs MPI send/recv bandwidth benchmark"

    def fetch(self, srcdir: Path, *, force: bool = False, dry_run: bool = False) -> Path:
        dest = srcdir / "mpiGraph"
        git_clone(_GIT_URL, dest, force=force, dry_run=dry_run)
        return dest

    def build(self, src: Path, prefix: Path, cfg: BuildConfig, *, dry_run: bool = False) -> list[str]:
        env = dict(os.environ, MPICC=cfg.mpicc, CC=cfg.mpicc, CFLAGS=cfg.cflags)
        run(["make", "-j", str(cfg.jobs)], cwd=src, dry_run=dry_run, env=env)
        return install_bins(src, prefix / "bin", ["mpiGraph"], dry_run=dry_run)

    def check_requires(self) -> list[str]:
        return require("mpicc", "make", "git")
