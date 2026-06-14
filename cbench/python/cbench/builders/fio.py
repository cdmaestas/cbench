"""Builder for fio (Flexible I/O Tester)."""

from __future__ import annotations

from pathlib import Path

from cbench.builders import BenchmarkBuilder, BuildConfig
from cbench.builders._util import run, require, git_clone, install_bins

_GIT_URL = "https://github.com/axboe/fio.git"


class FioBuilder(BenchmarkBuilder):
    name = "fio"
    description = "fio Flexible I/O Tester — configurable storage benchmark"
    source_url = _GIT_URL

    def fetch(self, srcdir: Path, *, force: bool = False, dry_run: bool = False) -> Path:
        dest = srcdir / "fio"
        git_clone(_GIT_URL, dest, force=force, dry_run=dry_run)
        return dest

    def build(self, src: Path, prefix: Path, cfg: BuildConfig, *, dry_run: bool = False) -> list[str]:
        import os
        env = dict(os.environ, CC=cfg.cc, CFLAGS=cfg.cflags)
        run(["./configure", f"--prefix={prefix}"], cwd=src, dry_run=dry_run, env=env)
        run(["make", "-j", str(cfg.jobs)], cwd=src, dry_run=dry_run, env=env)
        run(["make", "install"], cwd=src, dry_run=dry_run)
        return install_bins(prefix / "bin", prefix / "bin", ["fio"], dry_run=dry_run)

    def check_requires(self) -> list[str]:
        return require("cc", "make", "git")
