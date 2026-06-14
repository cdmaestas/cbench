"""Builder for IOR parallel I/O benchmark (also builds mdtest)."""

from __future__ import annotations

from pathlib import Path

from cbench.builders import BenchmarkBuilder, BuildConfig
from cbench.builders._util import run, require, git_clone, install_bins

_GIT_URL = "https://github.com/hpc/ior.git"


class IorBuilder(BenchmarkBuilder):
    name = "ior"
    description = "IOR parallel I/O benchmark + mdtest metadata benchmark"
    source_url = _GIT_URL

    def fetch(self, srcdir: Path, *, force: bool = False, dry_run: bool = False) -> Path:
        dest = srcdir / "ior"
        git_clone(_GIT_URL, dest, force=force, dry_run=dry_run)
        return dest

    def build(self, src: Path, prefix: Path, cfg: BuildConfig, *, dry_run: bool = False) -> list[str]:
        run(["./bootstrap"], cwd=src, dry_run=dry_run)
        run(
            ["./configure", f"CC={cfg.mpicc}", f"--prefix={prefix}"],
            cwd=src, dry_run=dry_run,
        )
        run(["make", "-j", str(cfg.jobs)], cwd=src, dry_run=dry_run)
        run(["make", "install"], cwd=src, dry_run=dry_run)
        # IOR installs to prefix/bin/
        return install_bins(prefix / "bin", prefix / "bin", ["ior", "mdtest"], dry_run=dry_run)

    def check_requires(self) -> list[str]:
        return require("mpicc", "make", "git", "autoconf", "automake", "libtool")
