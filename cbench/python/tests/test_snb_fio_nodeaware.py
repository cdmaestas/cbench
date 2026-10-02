"""Tests for node-aware fio I/O testing in `cbench snb`.

Covers the pure helpers (FS-type detection, O_DIRECT probe, buffered-fallback
sizing, per-target benchmark naming) and the CLI gating (fio opt-in + required
--fs-target). All mockable on macOS dev — no real /proc or fio needed.
"""

import errno
import os

import pytest
from click.testing import CliRunner

from cbench.cli.main import cli
from cbench.cli import snb

runner = CliRunner()


# ---------------------------------------------------------------------------
# _detect_fstype — longest-mountpoint-prefix match against mountinfo
# ---------------------------------------------------------------------------

_MOUNTINFO = (
    "1 0 8:1 / / rw,relatime shared:1 - ext4 /dev/sda1 rw\n"
    "2 1 0:30 / /gpfs/scratch rw shared:2 - gpfs scratch rw\n"
    "3 1 0:31 / /mnt/lustre rw shared:3 - lustre 10.0.0.1@o2ib:/fs rw\n"
    # /data (not /home — macOS realpath rewrites /home to /System/Volumes/Data/home)
    "4 1 0:32 / /data rw shared:4 - nfs server:/export rw\n"
)


@pytest.fixture
def mountinfo(tmp_path):
    p = tmp_path / "mountinfo"
    p.write_text(_MOUNTINFO)
    return p


def test_detect_fstype_longest_prefix_gpfs(mountinfo):
    assert snb._detect_fstype("/gpfs/scratch/run1/fio", mountinfo) == "gpfs"


def test_detect_fstype_lustre(mountinfo):
    assert snb._detect_fstype("/mnt/lustre/data", mountinfo) == "lustre"


def test_detect_fstype_nfs(mountinfo):
    assert snb._detect_fstype("/data/user/tmp", mountinfo) == "nfs"


def test_detect_fstype_falls_back_to_root(mountinfo):
    assert snb._detect_fstype("/var/tmp", mountinfo) == "ext4"


def test_detect_fstype_missing_mountinfo_is_unknown(tmp_path):
    # Non-Linux / no mountinfo → "unknown", never raises
    assert snb._detect_fstype("/anything", tmp_path / "nope") == "unknown"


# ---------------------------------------------------------------------------
# _supports_odirect — syscall probe
# ---------------------------------------------------------------------------

def test_supports_odirect_true(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "O_DIRECT", getattr(os, "O_DIRECT", 0o40000), raising=False)
    monkeypatch.setattr(os, "open", lambda *a, **k: 3)
    monkeypatch.setattr(os, "close", lambda fd: None)
    monkeypatch.setattr(os, "unlink", lambda p: None)
    assert snb._supports_odirect(tmp_path) is True


def test_supports_odirect_false_on_einval(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "O_DIRECT", getattr(os, "O_DIRECT", 0o40000), raising=False)

    def _raise(*a, **k):
        raise OSError(errno.EINVAL, "Invalid argument")

    monkeypatch.setattr(os, "open", _raise)
    assert snb._supports_odirect(tmp_path) is False


def test_supports_odirect_false_without_os_odirect(tmp_path, monkeypatch):
    # macOS: os.O_DIRECT does not exist → unsupported, no crash
    monkeypatch.delattr(os, "O_DIRECT", raising=False)
    assert snb._supports_odirect(tmp_path) is False


# ---------------------------------------------------------------------------
# _fio_buffered_size_bytes — 2x MemTotal / numjobs, capped by free space
# ---------------------------------------------------------------------------

GIB = 1024 ** 3


def test_buffered_size_two_x_memtotal_divided(tmp_path):
    # 8 GiB RAM, 4 jobs, ample free → 2*8/4 = 4 GiB per job, no caveat
    per_job, caveat = snb._fio_buffered_size_bytes(8 * GIB, 4, free_bytes=100 * GIB)
    assert per_job == 4 * GIB
    assert caveat is False


def test_buffered_size_capped_by_free_space_sets_caveat():
    # 8 GiB RAM wants 16 GiB aggregate, but only 10 GiB free → capped, caveat set
    per_job, caveat = snb._fio_buffered_size_bytes(8 * GIB, 4, free_bytes=10 * GIB)
    assert caveat is True
    # capped aggregate <= 90% of free, divided across jobs
    assert per_job * 4 <= int(10 * GIB * 0.9)
    assert per_job > 0


# ---------------------------------------------------------------------------
# _fio_benchmark_name — target encoded into benchmark, node identity in jobname
# ---------------------------------------------------------------------------

def test_fio_benchmark_name_encodes_fstype_and_basename():
    assert snb._fio_benchmark_name("gpfs", "/gpfs/scratch") == "snb_fio_gpfs_scratch"


def test_fio_benchmark_name_sanitizes():
    name = snb._fio_benchmark_name("nfs", "/weird path/a.b")
    assert " " not in name and "." not in name
    assert name.startswith("snb_fio_nfs_")


# ---------------------------------------------------------------------------
# CLI gating: fio is opt-in, and requires --fs-target when selected
# ---------------------------------------------------------------------------

def test_fio_not_in_default_suite():
    # The default --tests must no longer include fio (opt-in only)
    src = (snb.run_cmd.params)
    default_tests = next(p.default for p in src if p.name == "tests")
    assert "fio" not in default_tests


def test_fio_selected_without_fs_target_errors(tmp_path):
    result = runner.invoke(cli, [
        "snb", "run", "--tests", "fio",
        "--destdir", str(tmp_path), "--ident", "t1",
        "--dry-run",
    ])
    assert result.exit_code != 0
    assert "fs-target" in result.output.lower()


def test_default_run_does_not_require_fs_target(tmp_path):
    # Running the default suite (no fio) must not demand --fs-target
    result = runner.invoke(cli, [
        "snb", "run",
        "--destdir", str(tmp_path), "--ident", "t2",
        "--dry-run",
    ])
    assert "fs-target" not in result.output.lower()


# ---------------------------------------------------------------------------
# _parse_fio_targets — the collector half (what the DB/report consume)
# ---------------------------------------------------------------------------

_FIO_TWO_TARGETS = (
    "### CBENCH FS-TARGET path=/gpfs/scratch fstype=gpfs odirect=1 caveat=0\n"
    "seq_rw: (groupid=0, jobs=1): err= 0: pid=1:\n"
    "  read: IOPS=100k, BW=1000MiB/s (1049MB/s)(60.0GiB/60s)\n"
    "  write: IOPS=50k, BW=500MiB/s (524MB/s)(30.0GiB/60s)\n"
    "### CBENCH FS-TARGET path=/local/tmp fstype=ext4 odirect=0 caveat=1\n"
    "seq_rw: (groupid=0, jobs=1): err= 0: pid=2:\n"
    "  read: IOPS=200k, BW=2000MiB/s (2097MB/s)(120GiB/60s)\n"
)


def test_parse_fio_targets_round_trip(tmp_path):
    f = tmp_path / "host.snb.fio.out"
    f.write_text(_FIO_TWO_TARGETS)
    results = snb._parse_fio_targets(f)

    assert len(results) == 2
    by_name = {bench: (detail, metrics) for bench, detail, metrics in results}

    assert "snb_fio_gpfs_scratch" in by_name
    detail1, metrics1 = by_name["snb_fio_gpfs_scratch"]
    assert "fstype=gpfs" in detail1 and "odirect=1" in detail1
    assert "cache-influenced" not in detail1
    assert metrics1["read_bw_MiB_s"] == pytest.approx(1000.0)

    assert "snb_fio_ext4_tmp" in by_name
    detail2, metrics2 = by_name["snb_fio_ext4_tmp"]
    assert "caveat=1" in detail2 and "cache-influenced" in detail2
    assert metrics2["read_bw_MiB_s"] == pytest.approx(2000.0)


def test_parse_fio_targets_no_marker_backcompat(tmp_path):
    # A marker-less file (single untargeted run) still yields one snb_fio result
    f = tmp_path / "host.snb.fio.out"
    f.write_text(
        "seq_rw: (groupid=0, jobs=1): err= 0: pid=1:\n"
        "  read: IOPS=10k, BW=100MiB/s (105MB/s)(6.0GiB/60s)\n"
    )
    results = snb._parse_fio_targets(f)
    assert len(results) == 1
    assert results[0][0] == "snb_fio"
