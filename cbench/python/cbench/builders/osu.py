"""Builder for OSU MPI Micro-Benchmarks."""

from __future__ import annotations

from pathlib import Path

from cbench.builders import BenchmarkBuilder, BuildConfig
from cbench.builders._util import console, run, require, wget_tarball

_TARBALL_URL = "https://mvapich.cse.ohio-state.edu/download/mvapich/osu-micro-benchmarks-7.3.tar.gz"


class OsuBuilder(BenchmarkBuilder):
    name = "osu"
    description = "OSU MPI Micro-Benchmarks — pt2pt, collective, one-sided"
    source_url = _TARBALL_URL

    def fetch(self, srcdir: Path, *, force: bool = False, dry_run: bool = False) -> Path:
        url = _TARBALL_URL
        return wget_tarball(url, srcdir / "osu", force=force, dry_run=dry_run)

    def build(self, src: Path, prefix: Path, cfg: BuildConfig, *, dry_run: bool = False) -> list[str]:
        osu_prefix = prefix / "osu"
        run(
            ["./configure", f"CC={cfg.mpicc}", f"CXX={cfg.mpicxx}",
             f"--prefix={osu_prefix}"],
            cwd=src, dry_run=dry_run,
        )
        run(["make", "-j", str(cfg.jobs)], cwd=src, dry_run=dry_run)
        run(["make", "install"], cwd=src, dry_run=dry_run)

        # Collect all installed binaries from the deep libexec tree
        installed = []
        mpi_dir = osu_prefix / "libexec" / "osu-micro-benchmarks" / "mpi"
        prefix_bin = prefix / "bin"
        prefix_bin.mkdir(parents=True, exist_ok=True)
        if not dry_run and mpi_dir.exists():
            import shutil
            for binary in sorted(mpi_dir.rglob("osu_*")):
                if binary.is_file():
                    dst = prefix_bin / binary.name
                    shutil.copy2(binary, dst)
                    dst.chmod(0o755)
                    installed.append(binary.name)
                    console.print(f"  [green]install[/green] {dst}")
        elif dry_run:
            installed = ["osu_latency", "osu_bw", "osu_bibw", "osu_allreduce", "..."]
        return installed

    def check_requires(self) -> list[str]:
        return require("mpicc", "make")
