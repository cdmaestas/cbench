"""Builder for HPCCG (Mantevo miniapp)."""

from __future__ import annotations

import os
from pathlib import Path

from cbench.builders import BenchmarkBuilder, BuildConfig
from cbench.builders._util import run, require, git_clone, install_bins

_GIT_URL = "https://github.com/Mantevo/HPCCG.git"


class HpccgBuilder(BenchmarkBuilder):
    name = "hpccg"
    description = "HPCCG Mantevo miniapp — conjugate gradient on unstructured grid"
    source_url = _GIT_URL

    def fetch(self, srcdir: Path, *, force: bool = False, dry_run: bool = False) -> Path:
        dest = srcdir / "HPCCG"
        git_clone(_GIT_URL, dest, force=force, dry_run=dry_run)
        return dest

    def build(self, src: Path, prefix: Path, cfg: BuildConfig, *, dry_run: bool = False) -> list[str]:
        env = dict(os.environ, CXX=cfg.mpicxx, CC=cfg.mpicc)
        run(["make", "-j", str(cfg.jobs), "-f", "Makefile"], cwd=src, dry_run=dry_run, env=env)
        return install_bins(src, prefix / "bin", ["test_HPCCG"], dry_run=dry_run)

    def check_requires(self) -> list[str]:
        return require("mpicc", "mpicxx", "make", "git")
