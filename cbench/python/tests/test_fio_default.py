"""fio as the default node-local IOPS/metadata test (cbench.fioprofile).

Covers the shared job set, the per-job-name parser, `snb run` fio wiring
(profile, time cap, metadata engines) and the gen-jobs iometadata_fio job.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from cbench import fioprofile, iosizing
from cbench.cli import snb
from cbench.cli.main import cli
from cbench.config import ClusterConfig, ConfigError, load_config
from cbench.parsers.fio import FioParser

GIB = 1024 ** 3


# ---------------------------------------------------------------------------
# profiles / job set
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("profile, fstype, expected", [
    ("ai", "xfs", ("ai", "1m")),
    ("general", "gpfs", ("general", "4m")),
    ("hpc", "ext4", ("hpc", "8m")),
    ("streaming", None, ("streaming", "16m")),
    ("auto", "gpfs", ("hpc", "8m")),
    ("auto", "lustre", ("hpc", "8m")),
    ("auto", "xfs", ("general", "4m")),
    ("auto", None, ("general", "4m")),
])
def test_seq_block_size_by_profile(profile, fstype, expected):
    assert fioprofile.seq_block_size(profile, fstype) == expected


def test_seq_bs_override_wins():
    assert fioprofile.seq_block_size("hpc", "gpfs", "2m") == ("hpc", "2m")


def test_unknown_profile_rejected():
    with pytest.raises(ValueError):
        fioprofile.seq_block_size("bogus", None)


@pytest.mark.parametrize("threads, n", [(1, 1), (4, 4), (64, 64), (0, 1)])
def test_numjobs_is_the_io_thread_count(threads, n):
    assert fioprofile.numjobs(threads) == n


def test_data_jobs_are_time_based_and_group_reported():
    jobs = dict(fioprofile.data_jobs("fio", "/t", seq_bs="8m", njobs=4, runtime_s=300, direct=True))
    assert list(jobs) == ["seq_rw", "rand_rw"]
    for argv in jobs.values():
        assert "--time_based" in argv and "--runtime=300" in argv and "--group_reporting" in argv
    assert "--bs=8m" in jobs["seq_rw"] and "--numjobs=1" in jobs["seq_rw"]
    assert "--bs=4k" in jobs["rand_rw"] and "--numjobs=4" in jobs["rand_rw"]


def test_metadata_jobs_bounded_by_files_not_time():
    jobs = dict(fioprofile.metadata_jobs("fio", "/t", njobs=4, runtime_s=300))
    assert list(jobs) == ["md_create", "md_stat", "md_delete"]
    for name, engine in [("md_create", "filecreate"), ("md_stat", "filestat"),
                         ("md_delete", "filedelete")]:
        assert f"--ioengine={engine}" in jobs[name]
        assert "--time_based" not in jobs[name]   # a time-based delete would run out of files


def test_has_metadata_engines():
    assert fioprofile.has_metadata_engines("Available IO engines:\n\tlibaio\n\tfilecreate\n\tfilestat\n\tfiledelete\n")
    assert not fioprofile.has_metadata_engines("Available IO engines:\n\tlibaio\n\tfilecreate\n")


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

def test_config_io_profile_keys(tmp_path):
    f = tmp_path / "cluster.yaml"
    f.write_text("fio_runtime_s: 60\nio_profile: streaming\nio_seq_bs: 2m\n")
    cfg = load_config(f)
    assert (cfg.fio_runtime_s, cfg.io_profile, cfg.io_seq_bs) == (60, "streaming", "2m")
    assert ClusterConfig().fio_runtime_s == 300 and ClusterConfig().io_profile == "auto"


def test_config_deprecated_fio_profile_alias(tmp_path):
    f = tmp_path / "cluster.yaml"
    f.write_text("fio_profile: hpc\nfio_seq_bs: 2m\n")
    with pytest.warns(DeprecationWarning, match="is deprecated") as rec:
        cfg = load_config(f)
    assert {str(w.message).split(": ")[-1] for w in rec} == {
        "fio_profile is deprecated, use io_profile", "fio_seq_bs is deprecated, use io_seq_bs"}
    assert (cfg.io_profile, cfg.io_seq_bs) == ("hpc", "2m")
    f.write_text("fio_profile: hpc\nio_profile: ai\n")
    with pytest.raises(ConfigError, match="not both"):
        load_config(f)


@pytest.mark.parametrize("bad", ["io_profile: fast", "fio_profile: fast", "fio_runtime_s: 0",
                                 "io_seq_bs: 8MB"])
def test_config_fio_keys_validated(tmp_path, bad):
    f = tmp_path / "cluster.yaml"
    f.write_text(bad + "\n")
    with pytest.raises(ConfigError):
        load_config(f)


# ---------------------------------------------------------------------------
# parser: one block per cbench job name
# ---------------------------------------------------------------------------

_JOBSET = """\
seq_rw: (g=0): rw=rw, bs=(R) 4096KiB-4096KiB, (W) 4096KiB-4096KiB, ioengine=libaio, iodepth=8
fio-3.35
Starting 1 process
seq_rw: (groupid=0, jobs=1): err= 0: pid=101: Sat Oct  3 20:00:00 2026
  read: IOPS=50, BW=200MiB/s (210MB/s)(58.6GiB/300001msec)
    clat (msec): min=1, avg=80.00, stdev=5.00, max=200
  write: IOPS=40, BW=160MiB/s (168MB/s)(46.9GiB/300001msec)
    clat (msec): min=1, avg=90.00, stdev=5.00, max=210

Run status group 0 (all jobs):
   READ: bw=200MiB/s (210MB/s), 200MiB/s-200MiB/s (210MB/s-210MB/s), io=58.6GiB, run=300001-300001msec
  WRITE: bw=160MiB/s (168MB/s), 160MiB/s-160MiB/s (168MB/s-168MB/s), io=46.9GiB, run=300001-300001msec
rand_rw: (g=0): rw=randrw, bs=(R) 4096B-4096B, (W) 4096B-4096B, ioengine=libaio, iodepth=32
fio-3.35
Starting 4 processes
rand_rw: (groupid=0, jobs=4): err= 0: pid=201: Sat Oct  3 20:05:00 2026
  read: IOPS=12.5k, BW=48.8MiB/s (51.2MB/s)(14.3GiB/300002msec)
    clat (usec): min=50, avg=4000.50, stdev=100.00, max=90000
     clat percentiles (usec):
     |  1.00th=[  100],  5.00th=[  200], 50.00th=[ 3000],
     | 99.00th=[ 9000], 99.90th=[20000]
  write: IOPS=12.4k, BW=48.4MiB/s (50.8MB/s)(14.2GiB/300002msec)
    clat (usec): min=60, avg=5000.25, stdev=120.00, max=95000
     clat percentiles (usec):
     |  1.00th=[  110],  5.00th=[  210], 50.00th=[ 4000],
     | 99.00th=[11000], 99.90th=[25000]

Run status group 0 (all jobs):
   READ: bw=48.8MiB/s (51.2MB/s), 12.2MiB/s-12.2MiB/s, io=14.3GiB, run=300002-300002msec
  WRITE: bw=48.4MiB/s (50.8MB/s), 12.1MiB/s-12.1MiB/s, io=14.2GiB, run=300002-300002msec
md_create: (groupid=0, jobs=4): err= 0: pid=301: Sat Oct  3 20:10:00 2026
  write: IOPS=3500, BW=13.7MiB/s (14.3MB/s)(15.6MiB/1143msec)
md_stat: (groupid=0, jobs=4): err= 0: pid=401: Sat Oct  3 20:10:05 2026
  read: IOPS=90.0k, BW=352MiB/s (369MB/s)(15.6MiB/44msec)
md_delete: (groupid=0, jobs=4): err= 0: pid=501: Sat Oct  3 20:10:06 2026
  read: IOPS=4200, BW=16.4MiB/s (17.2MB/s)(15.6MiB/952msec)
"""


def test_parser_splits_metrics_by_job_name():
    r = FioParser().parse(_JOBSET)
    assert r.status == "PASSED"
    m = r.metrics
    # sequential: bandwidth only, at the profile block size
    assert m["seq_read_bw_MiB_s"] == pytest.approx(200.0)
    assert m["seq_write_bw_MiB_s"] == pytest.approx(160.0)
    # random: IOPS for ALL 4 jobs (group reported), not the seq job's IOPS
    assert m["rand_read_iops"] == pytest.approx(12500)
    assert m["rand_write_iops"] == pytest.approx(12400)
    assert m["rand_read_lat_avg_us"] == pytest.approx(4000.50)
    assert m["rand_write_lat_p99_us"] == pytest.approx(11000)
    # metadata: one op per I/O, whichever direction the engine reports
    assert (m["create_ops"], m["stat_ops"], m["delete_ops"]) == (3500, 90000, 4200)
    assert "read_iops" not in m and "seq_read_iops" not in m
    assert set(m) <= set(FioParser().metric_units())


def test_parser_without_metadata_jobs():
    text = _JOBSET[:_JOBSET.index("md_create:")]
    m = FioParser().parse(text).metrics
    assert "create_ops" not in m and m["rand_read_iops"] == pytest.approx(12500)


# ---------------------------------------------------------------------------
# snb run fio
# ---------------------------------------------------------------------------

def _snb_dry(tmp_path, monkeypatch, *extra, fstype="xfs", config=None):
    monkeypatch.setattr(shutil, "which", lambda n: "/usr/bin/fio" if n == "fio" else None)
    monkeypatch.setattr(snb.console, "width", 10000)
    monkeypatch.setattr(snb, "_supports_odirect", lambda d: True)
    monkeypatch.setattr(snb, "_detect_fstype", lambda p, *a: fstype)
    monkeypatch.setattr(shutil, "disk_usage",
                        lambda p: shutil._ntuple_diskusage(2048 * GIB, 0, 1024 * GIB))
    target = tmp_path / "target"
    target.mkdir(exist_ok=True)
    args = ["snb", "run", "--tests", "fio", "--fs-target", str(target), "--numcores", "4",
            "--destdir", str(tmp_path / "out"), "--ident", "x", "--dry-run", *extra]
    if config:
        args += ["--config", str(config)]
    res = CliRunner().invoke(cli, args)
    assert res.exit_code == 0, res.output
    return res.output


def test_snb_auto_profile_on_gpfs_uses_8m(tmp_path, monkeypatch):
    out = _snb_dry(tmp_path, monkeypatch, fstype="gpfs")
    assert re.search(r"--name=seq_rw\b.*--bs=8m\b", out)
    assert "profile=hpc seq_bs=8m runtime_s=300" in out


def test_snb_auto_profile_on_local_uses_4m(tmp_path, monkeypatch):
    out = _snb_dry(tmp_path, monkeypatch, fstype="xfs")
    assert re.search(r"--name=seq_rw\b.*--bs=4m\b", out)


def test_snb_fio_profile_and_runtime_flags(tmp_path, monkeypatch):
    out = _snb_dry(tmp_path, monkeypatch, "--fio-profile", "streaming", "--fio-runtime", "45")
    assert re.search(r"--name=seq_rw\b.*--bs=16m\b.*--runtime=45\b", out)
    assert re.search(r"--name=rand_rw\b.*--bs=4k\b.*--time_based\b.*--runtime=45\b", out)


def test_snb_cluster_yaml_profile(tmp_path, monkeypatch):
    cfg = tmp_path / "cluster.yaml"
    cfg.write_text("io_profile: ai\nfio_runtime_s: 30\n")
    out = _snb_dry(tmp_path, monkeypatch, fstype="gpfs", config=cfg)
    assert re.search(r"--name=seq_rw\b.*--bs=1m\b.*--runtime=30\b", out)


def test_snb_runs_metadata_jobs(tmp_path, monkeypatch):
    out = _snb_dry(tmp_path, monkeypatch)
    for engine in ("filecreate", "filestat", "filedelete"):
        assert f"--ioengine={engine}" in out
    assert re.search(r"--name=md_create\b.*--numjobs=4\b", out)


def test_snb_skips_metadata_when_engines_missing(tmp_path, monkeypatch):
    fio = tmp_path / "fio"
    fio.write_text("#!/bin/sh\necho 'Available IO engines:'; echo libaio\n")
    fio.chmod(0o755)
    monkeypatch.setattr(shutil, "which", lambda n: str(fio) if n == "fio" else None)
    monkeypatch.setattr(snb.console, "width", 10000)
    monkeypatch.setattr(snb, "_supports_odirect", lambda d: True)
    monkeypatch.setattr(snb, "_detect_fstype", lambda p, *a: "xfs")
    target = tmp_path / "target"
    target.mkdir()
    res = CliRunner().invoke(cli, ["snb", "run", "--tests", "fio", "--fs-target", str(target),
                                   "--numcores", "2", "--fio-runtime", "1",
                                   "--destdir", str(tmp_path / "out"), "--ident", "x"])
    assert res.exit_code == 0, res.output
    assert "metadata ops not measured" in res.output
    outfile = next((tmp_path / "out").rglob("*.snb.fio.out")).read_text()
    assert "md=0" in outfile and "md_create" not in outfile
    rows = snb._parse_fio_targets(next((tmp_path / "out").rglob("*.snb.fio.out")))
    assert rows == []  # the fake fio printed no results


def test_parse_fio_targets_detail_records_profile_and_missing_metadata(tmp_path):
    f = tmp_path / "n1.snb.fio.out"
    f.write_text("### CBENCH FS-TARGET path=/gpfs/s fstype=gpfs odirect=1 caveat=0 "
                 "profile=hpc seq_bs=8m runtime_s=300 md=0\n" + _JOBSET)
    ((bench, status, detail, metrics),) = snb._parse_fio_targets(f)
    assert bench == "snb_fio_gpfs_s" and status == "PASSED"
    assert "profile=hpc seq_bs=8m runtime_s=300" in detail
    assert "metadata ops not measured" in detail
    assert metrics["rand_read_iops"] == pytest.approx(12500)


def test_remote_dispatch_forwards_fio_options():
    cmd = snb._build_remote_cmd(
        ClusterConfig(remotecmd_method="ssh", remotecmd_extraargs=""), remote_node="n1",
        ident="x", destdir="/d", numcores=4, tests="fio", binpath=None, mpi_cmd="mpirun",
        dry_run=True, store=False, config=None, fs_target=("/t",),
        io_profile="hpc", fio_runtime=60,
    )
    assert "--io-profile hpc" in cmd[-1] and "--fio-runtime 60" in cmd[-1]


# ---------------------------------------------------------------------------
# gen-jobs: iometadata_fio
# ---------------------------------------------------------------------------

def _facts(local_fstype="xfs", cpus=4, local_free=7606080):
    return {
        "schema_version": 1, "name": "typeA",
        "created": "2026-10-03T00:00:00+00:00",
        "allow_heterogeneous": False,
        "verdict": {"ok": True, "heterogeneous": False, "errors": [], "warnings": []},
        "aggregate": {
            "cpus": {"min": cpus, "max": cpus},
            "memtotal_kb": {"min": 7705320, "max": 7706776},
            "models": [],
            "targets": {"node-local": {"path": "/tmp", "fstype": local_fstype, "shared": False,
                                       "free_kb_min": local_free}},
        },
    }


@pytest.fixture
def genv(tmp_path, monkeypatch):
    # created now: a fixed date would trip load_facts' staleness warning
    from datetime import datetime, timezone

    def run(*args, facts=None, cfg_extra=""):
        cfg = tmp_path / "cluster.yaml"
        cfg.write_text("cluster_name: zima\nmax_nodes: 2\nprocs_per_node: 4\nbatch_method: slurm\n"
                       "io_targets:\n  node-local: /tmp\n" + cfg_extra)
        (tmp_path / "nodefacts").mkdir(exist_ok=True)
        f = facts or _facts()
        f["created"] = datetime.now(timezone.utc).isoformat()
        (tmp_path / "nodefacts" / "typeA.json").write_text(json.dumps(f))
        return CliRunner().invoke(cli, ["gen-jobs", "--testset", "iometadata", "--ident", "t1",
                                        "--run-type", "batch", "--config", str(cfg),
                                        "--cbenchtest", str(tmp_path), *args])

    def jobs():
        return sorted(p.name for p in (tmp_path / "iometadata" / "t1").iterdir())

    def script(job):
        return next((tmp_path / "iometadata" / "t1" / job).glob("*.slurm")).read_text()

    return SimpleNamespace(tmp=tmp_path, run=run, jobs=jobs, script=script)


def test_genjobs_fio_single_job_sized_from_facts(genv):
    res = genv.run("--nodefacts", "typeA")
    assert res.exit_code == 0, res.output
    assert [j for j in genv.jobs() if j.startswith("fio")] == ["fio-4ppn-4"]
    s = genv.script("fio-4ppn-4")
    assert "numjobs=4\n" in s and "runtime=300\n" in s and "seqbs=4m\n" in s
    # O_DIRECT 256 MiB per job, buffered fallback 1 GiB; preflight uses the one picked
    assert "size_mb=256\n" in s and "size_mb=1024\n" in s
    assert 'cbench_io_preflight "$PWD" "$((numjobs * size_mb * 1024))" ""' in s
    assert 'IO_TARGET_DIR="/tmp"' in s
    assert "--ioengine=filedelete" in s and "--group_reporting" in s


def test_genjobs_fio_profile_from_target_fstype_and_config(genv):
    res = genv.run("--nodefacts", "typeA", facts=_facts(local_fstype="gpfs"))
    assert res.exit_code == 0, res.output
    assert "seqbs=8m\n" in genv.script("fio-4ppn-4")
    res = genv.run("--nodefacts", "typeA", cfg_extra="io_profile: streaming\nfio_runtime_s: 120\n")
    s = genv.script("fio-4ppn-4")
    assert "seqbs=16m\n" in s and "runtime=120\n" in s


def test_genjobs_fio_numjobs_all_cpus_unless_capped(genv):
    res = genv.run("--nodefacts", "typeA", facts=_facts(cpus=64, local_free=10**9))
    assert res.exit_code == 0, res.output
    assert "numjobs=64\n" in genv.script("fio-64ppn-64")
    res = genv.run("--nodefacts", "typeA", facts=_facts(cpus=64, local_free=10**9),
                   cfg_extra="io_threads_max: 16\n")
    assert res.exit_code == 0, res.output
    assert "numjobs=16\n" in genv.script("fio-16ppn-16")


def test_genjobs_fio_warns_when_target_short(genv):
    # 16 jobs x 256 MiB = 4 GiB vs ~0.9 GiB usable
    res = genv.run("--nodefacts", "typeA", facts=_facts(cpus=16, local_free=1_000_000))
    assert res.exit_code == 0, res.output
    assert "fio needs 4194304 kB" in res.output


def test_genjobs_fio_cpus_from_explicit_procs_per_node(genv):
    res = genv.run(cfg_extra="memory_per_node_mb: 7500\n")  # no facts; procs_per_node: 4
    assert res.exit_code == 0, res.output
    assert "numjobs=4\n" in genv.script("fio-4ppn-4")


def test_genjobs_fio_without_cpu_source_fails_before_rendering(genv):
    cfg = genv.tmp / "cluster.yaml"
    cfg.write_text("cluster_name: zima\nmax_nodes: 2\nmemory_per_node_mb: 7500\n")
    res = CliRunner().invoke(cli, ["gen-jobs", "--testset", "iometadata", "--ident", "t9",
                                   "--run-type", "batch", "--config", str(cfg),
                                   "--cbenchtest", str(genv.tmp)])
    assert res.exit_code != 0 and "node CPUs" in res.output
    assert not (genv.tmp / "iometadata" / "t9").exists()


def test_genjobs_skips_fileop_unless_matched(genv):
    res = genv.run("--nodefacts", "typeA")
    assert res.exit_code == 0, res.output
    assert "Skipping fileop by default" in res.output
    assert not any(j.startswith("fileop") for j in genv.jobs())
    res = genv.run("--nodefacts", "typeA", "--match", "fileop-1ppn")
    assert res.exit_code == 0, res.output
    assert "fileop-1ppn-1" in genv.jobs()


def test_genjobs_match_filters_jobnames(genv):
    res = genv.run("--nodefacts", "typeA", "--match", "^fio-")
    assert res.exit_code == 0, res.output
    assert genv.jobs() == ["fio-4ppn-4"]


def test_iometadata_fio_template_is_valid_bash(genv):
    if shutil.which("bash") is None:
        pytest.skip("bash not installed")
    genv.run("--nodefacts", "typeA")
    path = next((genv.tmp / "iometadata" / "t1" / "fio-4ppn-4").glob("*.slurm"))
    assert subprocess.run(["bash", "-n", str(path)]).returncode == 0


def test_fio_tokens_needs_cpus():
    nv = iosizing.NodeValues(cpus=None, mem_io_kb=1, mem_nonio_kb=1)
    with pytest.raises(iosizing.IOSizingError):
        iosizing.fio_tokens(nv, ClusterConfig(), testset="iometadata", benchmark="fio")


def test_snb_report_shows_each_target_with_new_metrics(tmp_path, monkeypatch):
    monkeypatch.setattr(snb.console, "width", 10000)
    d = tmp_path / "x"
    d.mkdir()
    (d / "n1.snb.fio.out").write_text(
        "### CBENCH FS-TARGET path=/tmp fstype=xfs odirect=1 caveat=0 profile=general "
        "seq_bs=4m runtime_s=30 md=1\n" + _JOBSET
        + "### CBENCH FS-TARGET path=/gpfs/s fstype=gpfs odirect=1 caveat=0 profile=hpc "
        "seq_bs=8m runtime_s=30 md=1\n" + _JOBSET
        + "### CBENCH FS-TARGET path=/scratch fstype=ext4 odirect=1 skipped=insufficient_space "
        "need_kb=16777216 usable_kb=1000\n"
    )
    res = CliRunner().invoke(cli, ["snb", "report", "--ident", "x", "--destdir", str(tmp_path),
                                   "--node", "n1"])
    assert res.exit_code == 0, res.output
    out = res.output
    assert "snb_fio_xfs_tmp" in out and "snb_fio_gpfs_s" in out and "snb_fio_ext4_scratch" in out
    assert "profile=hpc seq_bs=8m" in out and "skipped: insufficient space" in out
    assert out.count("rand_read_iops") == 2 and "12500.0" in out
    assert "create_ops" in out


def test_parser_reads_avg_latency_in_fio3_field_order():
    """fio 3.x prints clat min/max/avg/stdev (real zima fio-3.35 output)."""
    text = (
        "rand_rw: (groupid=0, jobs=4): err= 0: pid=1: Sat Oct  3 21:03:00 2026\n"
        "  read: IOPS=1621, BW=6487KiB/s (6643kB/s)(190MiB/30017msec)\n"
        "    slat (usec): min=4, max=410, avg=21.62, stdev=12.15\n"
        "    clat (usec): min=51, max=210385, avg=19706.47, stdev=21431.33\n"
        "     lat (usec): min=104, max=210410, avg=19728.43, stdev=21431.13\n"
        "  write: IOPS=1630, BW=6522KiB/s (6679kB/s)(191MiB/30017msec)\n"
        "    clat (msec): min=1, max=650, avg=58.79, stdev=60.12\n"
    )
    m = FioParser().parse(text).metrics
    assert m["rand_read_lat_avg_us"] == pytest.approx(19706.47)   # clat, not slat/lat
    assert m["rand_write_lat_avg_us"] == pytest.approx(58790.0)   # msec -> usec
    assert m["rand_read_bw_MiB_s"] == pytest.approx(6487 / 1024)


def test_snb_io_profile_flag_and_fio_alias(tmp_path, monkeypatch):
    out = _snb_dry(tmp_path, monkeypatch, "--io-profile", "ai")
    assert re.search(r"--name=seq_rw\b.*--bs=1m\b", out)
    (tmp_path / "b").mkdir()
    out = _snb_dry(tmp_path / "b", monkeypatch, "--fio-profile", "hpc")   # deprecated alias
    assert re.search(r"--name=seq_rw\b.*--bs=8m\b", out)
