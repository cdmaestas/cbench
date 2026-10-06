"""Builder for gpfsperf, the IBM Storage Scale (GPFS) I/O benchmark.

Usually not needed: GPFS ships a prebuilt ``gpfsperf`` in
``/usr/lpp/mmfs/samples/perf``, and the iogpfs_gpfsperf job uses it when no
cbench build exists. Build your own only for a custom variant (e.g. other
compiler flags); a binary in ``<prefix>/bin`` takes precedence in the job.
GPFS RDMA (``verbsRdma``) is done by the GPFS daemon, so it needs no special
gpfsperf build; ``cbench nodecheck`` records which transport GPFS is set to use.

gpfsperf is not downloadable: it ships as source with GPFS (root-owned,
read-only) and links against ``-lgpfs``, so it can only be built on a host
with GPFS installed. The builder copies that directory into the cbench source
tree and runs the makefile's ``gpfsperf`` target. It overrides CC; the
makefile's CFLAGS (``-O -Wno-format-security -DGPFS_LINUX``) are kept unless
``--extra cflags="..."`` replaces them — include ``-DGPFS_LINUX`` when you do.

gpfsperf-mpi (the multi-node iogpfs_gpfsperfmpi job) is NOT shipped prebuilt,
so it is built too whenever the configured mpicc exists: the makefile's
``gpfsperf-mpi`` target with ``MPCC=<mpicc>``. The makefile links
``MPLIBS = -lmpich``, which only MPICH has; mpicc already links its own MPI,
so the builder passes ``MPLIBS=`` (empty) unless ``--extra mplibs="..."`` sets
it. ``--extra mpi=no`` skips it; ``--extra mpi=yes`` makes a missing mpicc an
error instead of a skip.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from cbench.builders import BenchmarkBuilder, BuildConfig
from cbench.builders._util import console, install_bins, require, run

SAMPLES_DIR = Path("/usr/lpp/mmfs/samples/perf")


class GpfsperfBuilder(BenchmarkBuilder):
    name = "gpfsperf"
    description = "IBM Storage Scale (GPFS) gpfsperf, built from the GPFS samples"
    source_url = SAMPLES_DIR.as_uri()
    optional = True  # most hosts have no GPFS; `build all` skips it there
    update_note = "source ships with GPFS; updated by GPFS upgrades"

    samples_dir: Path = SAMPLES_DIR

    def fetch(self, srcdir: Path, *, force: bool = False, dry_run: bool = False) -> Path:
        dest = srcdir / "gpfsperf"
        if dest.exists() and not force:
            console.print(f"  [green]Already copied:[/green] {dest}")
            return dest
        console.print(f"  [cyan]copy[/cyan] {self.samples_dir} -> {dest}")
        if not dry_run:
            if dest.exists():
                shutil.rmtree(dest)
            # the samples ship a prebuilt binary; build our own from the source
            shutil.copytree(self.samples_dir, dest,
                            ignore=shutil.ignore_patterns("*.o", "gpfsperf", "gpfsperf-mpi"))
        return dest

    def build(self, src: Path, prefix: Path, cfg: BuildConfig, *, dry_run: bool = False) -> list[str]:
        cflags = [f"CFLAGS={cfg.extra['cflags']}"] if cfg.extra.get("cflags") else []
        run(["make", "gpfsperf", f"CC={cfg.cc}", *cflags], cwd=src, dry_run=dry_run)
        names = ["gpfsperf"]
        mpi = str(cfg.extra.get("mpi", "auto")).lower()
        if mpi not in ("no", "0", "false", "off"):
            if shutil.which(cfg.mpicc):
                run(["make", "gpfsperf-mpi", f"MPCC={cfg.mpicc}",
                     f"MPLIBS={cfg.extra.get('mplibs', '')}", *cflags], cwd=src, dry_run=dry_run)
                names.append("gpfsperf-mpi")
            elif mpi in ("yes", "1", "true", "on"):
                raise RuntimeError(f"gpfsperf-mpi needs an MPI compiler: {cfg.mpicc} not found")
            else:
                console.print(f"  [yellow]{cfg.mpicc} not found: building gpfsperf only "
                              "(gpfsperf-mpi needs MPI; --extra mpi=no silences this)[/yellow]")
        return install_bins(src, prefix / "bin", names, dry_run=dry_run)

    def check_requires(self) -> list[str]:
        missing = require("cc", "make")
        if not (self.samples_dir / "gpfsperf.c").is_file():
            missing.append(f"GPFS samples ({self.samples_dir}/gpfsperf.c) — GPFS not installed")
        return missing

    def update_source(self, srcdir: Path, *, dry_run: bool = False) -> bool:
        """The GPFS samples change only with a GPFS upgrade; re-copy with --force."""
        return False
