"""Builder for mpiBench (LLNL MPI collective benchmark)."""

from __future__ import annotations

import os
from pathlib import Path

from cbench.builders import BenchmarkBuilder, BuildConfig
from cbench.builders._util import run, require, git_clone, install_bins

_GIT_URL = "https://github.com/LLNL/mpiBench.git"


class MpiBenchBuilder(BenchmarkBuilder):
    name = "mpibench"
    description = "mpiBench LLNL MPI collective benchmark (latency across message sizes)"
    source_url = _GIT_URL

    def fetch(self, srcdir: Path, *, force: bool = False, dry_run: bool = False) -> Path:
        dest = srcdir / "mpiBench"
        git_clone(_GIT_URL, dest, force=force, dry_run=dry_run)
        return dest

    def build(self, src: Path, prefix: Path, cfg: BuildConfig, *, dry_run: bool = False) -> list[str]:
        env = dict(os.environ, MPICC=cfg.mpicc, CC=cfg.mpicc, CFLAGS=cfg.cflags)
        run(["make", "-j", str(cfg.jobs)], cwd=src, dry_run=dry_run, env=env)
        return install_bins(src, prefix / "bin", ["mpiBench"], dry_run=dry_run)

    def check_requires(self) -> list[str]:
        return require("mpicc", "make", "git")
