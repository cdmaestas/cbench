"""The fio job set cbench runs, shared by `cbench snb` and gen-jobs (iometadata_fio).

One fio invocation per job, each printing one group-reported block named after
the job, so the parser can tell them apart:

  seq_rw      sequential read/write at the profile's block size (bandwidth)
  rand_rw     4 KiB random read/write, numjobs = min(cores, 16)  (IOPS, latency)
  md_create   fio filecreate engine  (file creates/s)    \\  fio >= 3.23;
  md_stat     fio filestat engine    (stats/s)            >  skipped with a
  md_delete   fio filedelete engine  (deletes/s)         /   caveat otherwise

Data jobs are time-based (``fio_runtime_s``, default 300 s) so run time does not
grow with core count or a slow target; metadata jobs are bounded by their file
count with the same runtime as a cap. ``--runtime`` does not cover fio's file
layout, so O_DIRECT data files are kept small (256 MiB per job). The caller empties the target directory
between jobs so only one job's files exist at a time.

Sequential block size comes from a workload profile (``fio_profile``):
ai 1m, general 4m, hpc 8m, streaming 16m; ``auto`` picks hpc on a parallel
filesystem and general elsewhere. ``fio_seq_bs`` overrides it exactly.
"""

from __future__ import annotations

from typing import Optional

PROFILES = {"ai": "1m", "general": "4m", "hpc": "8m", "streaming": "16m"}
PROFILE_CHOICES = ["auto", *PROFILES]
PARALLEL_FSTYPES = frozenset({"gpfs", "lustre", "panfs", "beegfs", "ceph", "cephfs"})

# Per-job data file with O_DIRECT. Small on purpose: fio writes the files out
# before --runtime starts (zima: 4 x 1 GiB took ~2.5 min on xfs), the time-based
# run loops over the file, and O_DIRECT keeps the page cache out regardless.
DATA_SIZE = "256m"
DATA_SIZE_BYTES = 256 * 1024 ** 2
# Buffered runs need files larger than RAM to defeat the page cache; snb sizes
# them from MemTotal, and this is the floor when nothing better is known.
BUFFERED_FALLBACK_SIZE = "1g"
BUFFERED_FALLBACK_SIZE_BYTES = 1024 ** 3
RAND_BS = "4k"
MAX_NUMJOBS = 16
MD_NRFILES = 1000                # files per metadata job
MD_ENGINES = ("filecreate", "filestat", "filedelete")
DEFAULT_RUNTIME_S = 300


def numjobs(cpus: int) -> int:
    """Random-I/O and metadata job count: one per core, capped."""
    return max(1, min(int(cpus), MAX_NUMJOBS))


def seq_block_size(profile: str, fstype: Optional[str], override: str = "") -> tuple[str, str]:
    """(resolved profile name, sequential block size)."""
    if profile == "auto":
        profile = "hpc" if (fstype or "").lower() in PARALLEL_FSTYPES else "general"
    if profile not in PROFILES:
        raise ValueError(f"unknown fio profile {profile!r}; choose from {', '.join(PROFILE_CHOICES)}")
    return profile, (override or PROFILES[profile])


def peak_bytes(njobs: int, size_bytes: int = DATA_SIZE_BYTES) -> int:
    """Largest footprint of the job set: the random job's numjobs files."""
    return size_bytes * max(1, njobs)


def data_jobs(
    fio: str, directory: str, *, seq_bs: str, njobs: int, runtime_s: int,
    direct: bool, size: str = DATA_SIZE,
) -> list[tuple[str, list[str]]]:
    common = [
        "--ioengine=libaio", f"--direct={int(direct)}", f"--directory={directory}",
        "--time_based", f"--runtime={runtime_s}", "--group_reporting",
        "--output-format=normal",
    ]
    return [
        ("seq_rw", [fio, "--name=seq_rw", "--rw=rw", f"--bs={seq_bs}", f"--size={size}",
                    "--numjobs=1", "--iodepth=8", *common]),
        ("rand_rw", [fio, "--name=rand_rw", "--rw=randrw", f"--bs={RAND_BS}", f"--size={size}",
                     f"--numjobs={njobs}", "--iodepth=32", *common]),
    ]


def metadata_jobs(
    fio: str, directory: str, *, njobs: int, runtime_s: int, nrfiles: int = MD_NRFILES,
) -> list[tuple[str, list[str]]]:
    common = [
        "--filesize=4k", f"--nrfiles={nrfiles}", "--openfiles=1", f"--numjobs={njobs}",
        f"--directory={directory}", f"--runtime={runtime_s}", "--group_reporting",
        "--output-format=normal",
    ]
    return [
        # create_on_open: the create happens during the run, not at layout
        ("md_create", [fio, "--name=md_create", "--ioengine=filecreate", "--rw=write",
                       "--create_on_open=1", "--fallocate=none", *common]),
        ("md_stat", [fio, "--name=md_stat", "--ioengine=filestat", *common]),
        ("md_delete", [fio, "--name=md_delete", "--ioengine=filedelete", *common]),
    ]


def has_metadata_engines(enghelp_output: str) -> bool:
    """True when ``fio --enghelp`` lists every metadata engine."""
    names = set(enghelp_output.split())
    return all(e in names for e in MD_ENGINES)
