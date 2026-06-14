"""Builder for AMG (Algebraic Multigrid) benchmark from LLNL."""

from __future__ import annotations

import os
from pathlib import Path

from cbench.builders import BenchmarkBuilder, BuildConfig
from cbench.builders._util import run, require, git_clone, install_bins

_GIT_URL = "https://github.com/LLNL/AMG.git"


class AmgBuilder(BenchmarkBuilder):
    name = "amg"
    description = "AMG algebraic multigrid benchmark (LLNL)"

    def fetch(self, srcdir: Path, *, force: bool = False, dry_run: bool = False) -> Path:
        dest = srcdir / "AMG"
        git_clone(_GIT_URL, dest, force=force, dry_run=dry_run)
        return dest

    def build(self, src: Path, prefix: Path, cfg: BuildConfig, *, dry_run: bool = False) -> list[str]:
        env = dict(os.environ,
                   CC=cfg.mpicc,
                   CFLAGS=cfg.cflags,
                   MPICC=cfg.mpicc)
        run(["make", "-j", str(cfg.jobs)], cwd=src, dry_run=dry_run, env=env)
        return install_bins(src / "test", prefix / "bin", ["amg"], dry_run=dry_run)

    def check_requires(self) -> list[str]:
        return require("mpicc", "make", "git")
