"""Builder for IOzone filesystem benchmark.

IOzone ships as a source tarball from iozone.org.  It uses a platform-specific
make target rather than autoconf.  Override the target via --extra target=linux
if the default (linux-AMD64) is wrong for your system.

Common targets: linux-AMD64, linux, linux-arm, macosx, freebsd
"""

from __future__ import annotations

from pathlib import Path

from cbench.builders import BenchmarkBuilder, BuildConfig
from cbench.builders._util import console, run, require, wget_tarball, install_bins

_TARBALL_URL = "https://www.iozone.org/src/current/iozone3_506.tar"
_DEFAULT_TARGET = "linux-AMD64"


class IozoneBuilder(BenchmarkBuilder):
    name = "iozone"
    description = "IOzone filesystem benchmark (sequential, random, mmap I/O)"
    source_url = _TARBALL_URL

    def fetch(self, srcdir: Path, *, force: bool = False, dry_run: bool = False) -> Path:
        top = wget_tarball(_TARBALL_URL, srcdir / "iozone", force=force, dry_run=dry_run)
        # Source lives one level deeper: iozone3_506/src/current/
        return top / "src" / "current"

    def build(self, src: Path, prefix: Path, cfg: BuildConfig, *, dry_run: bool = False) -> list[str]:
        import os
        target = cfg.extra.get("target", _DEFAULT_TARGET)
        console.print(f"  [dim]make target: {target}[/dim]")
        env = dict(os.environ, CC=cfg.cc, CFLAGS=cfg.cflags)
        run(["make", target], cwd=src, dry_run=dry_run, env=env)
        return install_bins(src, prefix / "bin" / "hwtests", ["iozone"], dry_run=dry_run)

    def check_requires(self) -> list[str]:
        return require("cc", "make")
