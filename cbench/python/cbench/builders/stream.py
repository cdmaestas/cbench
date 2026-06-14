"""Builder for the STREAM memory bandwidth benchmark (McCalpin)."""

from __future__ import annotations

from pathlib import Path

from cbench.builders import BenchmarkBuilder, BuildConfig
from cbench.builders._util import console, run, require, wget_tarball, install_bins

_URL = "https://www.cs.virginia.edu/stream/FTP/Code/stream.c"

# Array sizes to compile: small (fits in L3), medium, large (exceeds LLC)
_SIZES = [
    ("stream-1m", 1_000_000),
    ("stream-10m", 10_000_000),
    ("stream-100m", 100_000_000),
]


class StreamBuilder(BenchmarkBuilder):
    name = "stream"
    description = "STREAM memory bandwidth benchmark (McCalpin)"

    def fetch(self, srcdir: Path, *, force: bool = False, dry_run: bool = False) -> Path:
        dest = srcdir / "stream"
        dest.mkdir(parents=True, exist_ok=True)
        src_c = dest / "stream.c"
        if src_c.exists() and not force:
            console.print(f"  [green]Already downloaded:[/green] {src_c}")
            return dest
        console.print(f"  [cyan]wget[/cyan] {_URL}")
        if not dry_run:
            import urllib.request
            urllib.request.urlretrieve(_URL, src_c)
        return dest

    def build(self, src: Path, prefix: Path, cfg: BuildConfig, *, dry_run: bool = False) -> list[str]:
        prefix_bin = prefix / "bin" / "hwtests"
        src_c = src / "stream.c"
        installed = []
        for binary_name, array_size in _SIZES:
            out = src / binary_name
            run(
                [
                    cfg.cc, "-O3", "-fopenmp",
                    f"-DSTREAM_ARRAY_SIZE={array_size}",
                    str(src_c), "-o", str(out),
                ],
                cwd=src,
                dry_run=dry_run,
            )
            installed += install_bins(src, prefix_bin, [binary_name], dry_run=dry_run)
        return installed

    def check_requires(self) -> list[str]:
        return require("cc", "git")
