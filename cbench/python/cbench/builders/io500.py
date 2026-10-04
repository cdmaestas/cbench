"""Builder for the IO500 storage benchmark (github.com/IO500/io500).

IO500's own ``prepare.sh`` clones the IOR and pfind revisions it is pinned to
(so the build host needs network access), bootstraps and builds IOR with
autotools, and links everything into one ``io500`` binary in the repo root
(its Makefile uses ``mpicc``). Only ``io500`` is installed into
``<prefix>/bin``; IO500's private IOR build stays in its source tree, separate
from cbench's ``ior`` builder.
"""

from __future__ import annotations

import os
from pathlib import Path

from cbench.builders import BenchmarkBuilder, BuildConfig
from cbench.builders._util import git_clone, install_bins, require, run

_GIT_URL = "https://github.com/IO500/io500.git"


class Io500Builder(BenchmarkBuilder):
    name = "io500"
    description = "IO500 storage benchmark (bundled IOR/mdtest/pfind phases)"
    source_url = _GIT_URL

    def fetch(self, srcdir: Path, *, force: bool = False, dry_run: bool = False) -> Path:
        dest = srcdir / "io500"
        git_clone(_GIT_URL, dest, force=force, dry_run=dry_run)
        return dest

    def build(self, src: Path, prefix: Path, cfg: BuildConfig, *, dry_run: bool = False) -> list[str]:
        # CC reaches IOR's ./configure; NPROC is prepare.sh's make -j
        env = dict(os.environ, CC=cfg.mpicc, NPROC=str(cfg.jobs))
        run(["./prepare.sh"], cwd=src, dry_run=dry_run, env=env)
        return install_bins(src, prefix / "bin", ["io500"], dry_run=dry_run)

    def check_requires(self) -> list[str]:
        return require("mpicc", "make", "git", "autoconf", "automake", "libtool")
