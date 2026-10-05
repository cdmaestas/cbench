"""The fio job set cbench runs, shared by `cbench snb` and gen-jobs (iometadata_fio).

One fio invocation per job, each printing one group-reported block named after
the job, so the parser can tell them apart:

  seq_rw      sequential read/write at the profile's block size (bandwidth)
  rand_rw     4 KiB random read/write, numjobs = IO threads (IOPS, latency)
  md_create   fio filecreate engine  (file creates/s)    \\  fio >= 3.23;
  md_stat     fio filestat engine    (stats/s)            >  skipped with a
  md_delete   fio filedelete engine  (deletes/s)         /   caveat otherwise

Data jobs are time-based (``fio_runtime_s``, default 300 s) so run time does not
grow with core count or a slow target; metadata jobs are bounded by their file
count with the same runtime as a cap. ``--runtime`` does not cover fio's file
layout, so O_DIRECT data files are kept small (256 MiB per job). The caller empties the target directory
between jobs so only one job's files exist at a time -- except between the
metadata jobs (``MD_KEEP_FILES``): md_stat and md_delete work on the files
md_create made, so each phase measures its operation on the same file set and
neither lays out files of its own.

Sequential block size comes from the IO workload profile (``io_profile``;
``fio_profile`` is a deprecated alias): ai 1m, general 4m, hpc 8m,
streaming 16m; ``auto`` picks hpc on a parallel filesystem and general
elsewhere, then -- when the filesystem's block size (or Lustre stripe size)
is known from nodecheck or a local statvfs -- moves up to the smallest
profile whose size is a whole multiple of it, so sequential transfers never
split a block (e.g. 16 MiB GPFS blocks: hpc 8m -> streaming 16m).
``io_seq_bs`` overrides it exactly, and an explicit profile is never moved.
The same size is iozone's and gpfsperf's record size and IOR's transfer
size (-t).
"""

from __future__ import annotations


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
#: transfer size for every random / IOPS test (fio rand_rw, iozone -i 2,
#: gpfsperf read/write rand): 4 KiB is the usual IOPS target
IOPS_BS = "4k"
RAND_BS = IOPS_BS
#: bytes each IO thread moves in a bounded random test (gpfsperf rand -n)
IOPS_BYTES_PER_THREAD_MIB = 256
MD_NRFILES = 1000                # files per metadata job
#: shared file names for md_create/md_stat/md_delete (fio expands the $ keys,
#: so a shell caller must keep them literal). Without it each job names its
#: files after itself and lays out its own set before the timed phase.
MD_FILENAME_FORMAT = "md.$jobnum.$filenum"
#: jobs whose files the next job uses: don't empty the target after these
MD_KEEP_FILES = frozenset({"md_create", "md_stat"})
MD_ENGINES = ("filecreate", "filestat", "filedelete")
DEFAULT_RUNTIME_S = 300


def numjobs(threads: int) -> int:
    """Random-I/O and metadata job count: the IO thread count
    (``iosizing.io_threads`` / ``cap_threads``), at least 1."""
    return max(1, int(threads))


_UNITS_KB = {"k": 1, "m": 1024, "g": 1024 ** 2}


def size_kb(size: str) -> int:
    """'4m' -> 4096 (KiB); accepts k/m/g suffixes as io_seq_bs does."""
    return int(size[:-1]) * _UNITS_KB[size[-1].lower()]


def human_kb(kb: int) -> str:
    """4096 -> '4 MiB', 512 -> '512 KiB'."""
    for unit, div in (("GiB", 1024 ** 2), ("MiB", 1024)):
        if kb >= div and kb % div == 0:
            return f"{kb // div} {unit}"
    return f"{kb} KiB"


def align_kb(target: dict | None) -> int | None:
    """The size sequential transfers should be a whole multiple of on a
    target: the larger of its block size and (Lustre) stripe size, from
    nodecheck facts; None when unknown."""
    if not target:
        return None
    sizes = [v for v in (target.get("block_kb"), target.get("stripe_kb")) if v]
    return max(sizes) if sizes else None


def auto_profile(fstype: str | None, align: int | None = None) -> tuple[str, str]:
    """(profile, note) that ``auto`` resolves to on a target.

    hpc on a parallel filesystem, else general; when ``align`` (KiB) is known
    and that size isn't a whole multiple of it, the smallest larger profile
    that is. ``note`` explains a move, or that no profile fits; "" otherwise.
    """
    base = "hpc" if (fstype or "").lower() in PARALLEL_FSTYPES else "general"
    base_kb = size_kb(PROFILES[base])
    if not align or base_kb % align == 0:
        return base, ""
    for name in sorted(PROFILES, key=lambda p: size_kb(PROFILES[p])):
        kb = size_kb(PROFILES[name])
        if kb >= base_kb and kb % align == 0:
            return name, (f"{base} ({PROFILES[base]}) is not a multiple of the "
                          f"{human_kb(align)} block size; auto uses {name} ({PROFILES[name]})")
    return base, (f"no IO profile is a multiple of the {human_kb(align)} block size; "
                  f"auto keeps {base} ({PROFILES[base]})")


def seq_block_size(profile: str, fstype: str | None, override: str = "",
                   align: int | None = None) -> tuple[str, str]:
    """(resolved profile name, sequential block size). ``align`` (KiB) makes
    ``auto`` block-size aware (see auto_profile); explicit profiles and
    ``override`` are used as given."""
    if profile == "auto":
        profile, _ = auto_profile(fstype, align)
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
    # create_on_open: md_create creates during the timed run, not at layout,
    # and md_stat/md_delete skip layout and act on md_create's (empty) files;
    # without it fio would first write each 4k file out. If the files are
    # missing, stat/delete fail with err=2 rather than creating them.
    common = [
        "--filesize=4k", f"--nrfiles={nrfiles}", "--openfiles=1", f"--numjobs={njobs}",
        f"--directory={directory}", f"--filename_format={MD_FILENAME_FORMAT}",
        "--create_on_open=1", f"--runtime={runtime_s}", "--group_reporting",
        "--output-format=normal",
    ]
    return [
        ("md_create", [fio, "--name=md_create", "--ioengine=filecreate", "--rw=write",
                       "--fallocate=none", *common]),
        ("md_stat", [fio, "--name=md_stat", "--ioengine=filestat", *common]),
        ("md_delete", [fio, "--name=md_delete", "--ioengine=filedelete", *common]),
    ]


def has_metadata_engines(enghelp_output: str) -> bool:
    """True when ``fio --enghelp`` lists every metadata engine."""
    names = set(enghelp_output.split())
    return all(e in names for e in MD_ENGINES)
