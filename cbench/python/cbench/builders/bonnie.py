"""Builder for Bonnie++ disk I/O benchmark."""

from __future__ import annotations

from pathlib import Path

from cbench.builders import BenchmarkBuilder, BuildConfig
from cbench.builders._util import run, require, wget_tarball, install_bins

_TARBALL_URL = "https://www.coker.com.au/bonnie++/bonnie++-2.00a.tgz"


class BonnieBuilder(BenchmarkBuilder):
    name = "bonnie"
    description = "Bonnie++ sequential and random disk I/O benchmark"
    source_url = _TARBALL_URL

    def fetch(self, srcdir: Path, *, force: bool = False, dry_run: bool = False) -> Path:
        return wget_tarball(_TARBALL_URL, srcdir / "bonnie", force=force, dry_run=dry_run)

    def build(self, src: Path, prefix: Path, cfg: BuildConfig, *, dry_run: bool = False) -> list[str]:
        run(["./configure", f"--prefix={prefix}", f"CXX={cfg.cxx}"],
            cwd=src, dry_run=dry_run)
        run(["make", "-j", str(cfg.jobs)], cwd=src, dry_run=dry_run)
        run(["make", "install"], cwd=src, dry_run=dry_run)
        return install_bins(
            prefix / "sbin", prefix / "bin",
            ["bonnie++", "zcav"], dry_run=dry_run,
        )

    def check_requires(self) -> list[str]:
        return require("c++", "make")
