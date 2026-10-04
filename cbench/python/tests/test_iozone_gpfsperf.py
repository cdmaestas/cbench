"""iozone (node-local) and gpfsperf (gpfs) in the io-default profile.

Parser fixtures follow iozone 3.5xx throughput-mode and gpfsperf (Storage
Scale 5.x) output formats; real-output validation happens on zima.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from cbench import iosizing
from cbench.cli.main import cli
from cbench.config import ClusterConfig
from cbench.parsers import get_parser
from cbench.parsers.gpfsperf import GpfsperfParser
from cbench.parsers.iozone import IozoneParser

GPFS = "/gpfs/zimafs1/cdmaestas"

_IOZONE = """\
Cbench iozone: profile=general record=4m threads=4 size=1668m
\tIozone: Performance Test of File I/O
\t        Version $Revision: 3.506 $
\tRecord Size 4096 kB
\tFile size set to 1708032 kB
\tCommand line used: iozone -i 0 -i 1 -i 2 -e -c -t 4 -s 1668m -r 4m -F ./iozone.1 ./iozone.2 ./iozone.3 ./iozone.4
\tThroughput test with 4 processes
\tChildren see throughput for  4 initial writers \t=  262144.00 kB/sec
\tParent sees throughput for  4 initial writers \t=  250000.00 kB/sec
\tChildren see throughput for  4 rewriters \t=  204800.00 kB/sec
\tChildren see throughput for  4 readers \t\t= 1048576.00 kB/sec
\tChildren see throughput for 4 re-readers \t= 2097152.00 kB/sec
\tChildren see throughput for 4 random readers \t=   51200.00 kB/sec
\tChildren see throughput for 4 random writers \t=   10240.00 kB/sec

iozone test complete.
"""

_GPFSPERF = """\
Cbench gpfsperf: profile=hpc record=8m threads=4 size=15056m
Cbench joblaunch cmd line: /usr/lpp/mmfs/samples/perf/gpfsperf create seq ./gpfsperf.dat -r 8m -n 15056m -th 4
/usr/lpp/mmfs/samples/perf/gpfsperf create seq ./gpfsperf.dat
  recSize 8M nBytes 15056M fileSize 15056M
  nProcesses 1 nThreadsPerProcess 4
    Data rate was 102400.00 Kbytes/sec, Op Rate was 12.50 Ops/sec, Avg Latency was 320.000 milliseconds, thread utilization 0.990, bytesTransferred 15787360256
Cbench joblaunch cmd line: /usr/lpp/mmfs/samples/perf/gpfsperf read seq ./gpfsperf.dat -r 8m -n 15056m -th 4
/usr/lpp/mmfs/samples/perf/gpfsperf read seq ./gpfsperf.dat
  recSize 8M nBytes 15056M fileSize 15056M
  nProcesses 1 nThreadsPerProcess 4
    Data rate was 2048000.00 Kbytes/sec, Op Rate was 250.00 Ops/sec, Avg Latency was 16.000 milliseconds, thread utilization 0.950, bytesTransferred 15787360256
Cbench joblaunch cmd line: /usr/lpp/mmfs/samples/perf/gpfsperf read rand ./gpfsperf.dat -r 8m -n 15056m -th 4
/usr/lpp/mmfs/samples/perf/gpfsperf read rand ./gpfsperf.dat
  recSize 8M nBytes 15056M fileSize 15056M
  nProcesses 1 nThreadsPerProcess 4
    Data rate was 409600.00 Kbytes/sec, Op Rate was 50.00 Ops/sec, Avg Latency was 80.000 milliseconds, thread utilization 0.900, bytesTransferred 15787360256
Cbench joblaunch cmd line: /usr/lpp/mmfs/samples/perf/gpfsperf write rand ./gpfsperf.dat -r 8m -n 15056m -th 4
/usr/lpp/mmfs/samples/perf/gpfsperf write rand ./gpfsperf.dat
  recSize 8M nBytes 15056M fileSize 15056M
  nProcesses 1 nThreadsPerProcess 4
    Data rate was 81920.00 Kbytes/sec, Op Rate was 10.00 Ops/sec, Avg Latency was 400.000 milliseconds, thread utilization 0.980, bytesTransferred 15787360256
Cbench gpfsperf: finished
"""


# ---------------------------------------------------------------------------
# iozone parser
# ---------------------------------------------------------------------------

def test_iozone_throughput_mode():
    r = IozoneParser().parse(_IOZONE)
    assert r.status == "PASSED"
    m = r.metrics
    assert m["write_MiB_s"] == pytest.approx(256.0)          # children, not parent
    assert m["rewrite_MiB_s"] == pytest.approx(200.0)
    assert m["read_MiB_s"] == pytest.approx(1024.0)
    assert m["reread_MiB_s"] == pytest.approx(2048.0)
    assert m["random_read_MiB_s"] == pytest.approx(50.0)
    assert m["random_write_MiB_s"] == pytest.approx(10.0)
    assert m["threads"] == 4
    assert set(m) <= set(IozoneParser().metric_units())


def test_iozone_unfinished_is_started():
    partial = _IOZONE[: _IOZONE.index("\tChildren see throughput for  4 readers")]
    assert IozoneParser().parse(partial).status == "ERROR(STARTED)"


def test_iozone_no_results():
    assert IozoneParser().parse("Iozone: Performance Test of File I/O\n").status == "NOTSTARTED"
    assert IozoneParser().parse("CBENCH NOTICE: insufficient space\n").status == "NOTICE"


def test_profile_names_resolve():
    assert isinstance(get_parser("iozone-local"), IozoneParser)
    assert isinstance(get_parser("gpfsperf-gpfs"), GpfsperfParser)


# ---------------------------------------------------------------------------
# gpfsperf parser: several operations per job
# ---------------------------------------------------------------------------

def test_gpfsperf_multi_op_metrics_prefixed():
    r = GpfsperfParser().parse(_GPFSPERF)
    assert r.status == "PASSED"
    m = r.metrics
    assert m["create_seq_throughput_MB_s"] == pytest.approx(100.0)
    assert m["read_seq_throughput_MB_s"] == pytest.approx(2000.0)
    assert m["read_rand_iops"] == pytest.approx(50.0)
    assert m["write_rand_latency_avg_ms"] == pytest.approx(400.0)
    assert m["nthreads_per_process"] == 4
    assert "throughput_MB_s" not in m      # nothing overwritten into one unprefixed value
    assert r.status_detail == "operations=create_seq,read_seq,read_rand,write_rand"
    assert set(m) <= set(GpfsperfParser().metric_units())


def test_gpfsperf_job_without_end_line_is_started():
    partial = _GPFSPERF[: _GPFSPERF.index("Cbench joblaunch cmd line: /usr/lpp/mmfs/samples/perf/gpfsperf read rand")]
    r = GpfsperfParser().parse(partial)
    assert r.status == "ERROR(STARTED)" and r.metrics == {}


# ---------------------------------------------------------------------------
# sizing tokens
# ---------------------------------------------------------------------------

def _nv(local_free=None, gpfs_free=None, cpus=4):
    targets = {"node-local": {"path": "/tmp", "fstype": "xfs", "shared": False,
                              "free_kb_min": local_free},
               "gpfs": {"path": GPFS, "fstype": "gpfs", "shared": True, "free_kb_min": gpfs_free}}
    return iosizing.NodeValues(cpus=cpus, mem_io_kb=7706776, mem_nonio_kb=7705320, targets=targets)


def test_iozone_tokens_split_2x_ram_rounded_to_record():
    t = iosizing.iozone_tokens(_nv(), ClusterConfig(), testset="iolocal", benchmark="iozone")
    assert (t["IOZONE_THREADS"], t["IOZONE_RECORD"], t["IOZONE_PROFILE"]) == ("4", "4m", "general")
    size = int(t["IOZONE_SIZE"][:-1])
    assert size % 4 == 0 and size * 4 * 1024 >= 2 * 7706776          # IO rounds up
    assert t["IO_CAVEAT"] == "" and t["IO_TARGET_DIR"] == "/tmp"


def test_iozone_tokens_capped_with_caveat():
    t = iosizing.iozone_tokens(_nv(local_free=7606080), ClusterConfig(),
                               testset="iolocal", benchmark="iozone")
    assert int(t["IO_REQUIRED_KB"]) <= 0.9 * 7606080
    assert "iozone size capped" in t["IO_CAVEAT"]


def test_iozone_threads_follow_cap():
    t = iosizing.iozone_tokens(_nv(cpus=64), ClusterConfig(io_threads_max=8),
                               testset="iolocal", benchmark="iozone")
    assert t["IOZONE_THREADS"] == "8"


def test_gpfsperf_tokens_hpc_profile_and_2x_ram():
    t = iosizing.gpfsperf_tokens(_nv(), ClusterConfig(), testset="iogpfs", benchmark="gpfsperf")
    assert (t["GPFSPERF_THREADS"], t["GPFSPERF_RECORD"], t["GPFSPERF_PROFILE"]) == ("4", "8m", "hpc")
    size = int(t["GPFSPERF_SIZE"][:-1])
    assert size % 8 == 0 and size * 1024 >= 2 * 7706776
    assert t["IO_TARGET_DIR"] == GPFS


def test_gpfs_target_alias_from_facts():
    facts = {"schema_version": 2, "name": "x", "created": "2026-10-04T00:00:00+00:00",
             "aggregate": {"cpus": {"min": 4, "max": 4}, "memtotal_kb": {"min": 1, "max": 1},
                           "targets": {"parallel": {"path": GPFS, "fstype": "gpfs",
                                                    "shared": True, "free_kb_min": 1}}}}
    nv = iosizing.resolve_node_values(ClusterConfig(io_targets={"parallel": GPFS}), facts)
    assert nv.targets["gpfs"]["path"] == GPFS
    facts["aggregate"]["targets"]["parallel"]["fstype"] = "lustre"
    nv = iosizing.resolve_node_values(ClusterConfig(io_targets={"parallel": GPFS}), facts)
    assert "gpfs" not in nv.targets


# ---------------------------------------------------------------------------
# gen-jobs
# ---------------------------------------------------------------------------

def _facts(parallel_fstype="gpfs"):
    return {"schema_version": 2, "name": "typeA",
            "created": datetime.now(timezone.utc).isoformat(), "allow_heterogeneous": False,
            "verdict": {"ok": True, "heterogeneous": False, "errors": [], "warnings": []},
            "aggregate": {"cpus": {"min": 4, "max": 4}, "cores": {"min": 4, "max": 4},
                          "memtotal_kb": {"min": 7705320, "max": 7706776}, "models": [],
                          "targets": {"node-local": {"path": "/tmp", "fstype": "xfs",
                                                     "shared": False, "free_kb_min": 10**9},
                                      "parallel": {"path": GPFS, "fstype": parallel_fstype,
                                                   "shared": True, "free_kb_min": 10**12}}}}


@pytest.fixture
def genv(tmp_path):
    def run(*args, facts=None, targets=f"  node-local: /tmp\n  parallel: {GPFS}\n"):
        cfg = tmp_path / "cluster.yaml"
        cfg.write_text("cluster_name: zima\nmax_nodes: 2\nprocs_per_node: 4\nbatch_method: slurm\n"
                       "io_targets:\n" + targets)
        (tmp_path / "nodefacts").mkdir(exist_ok=True)
        (tmp_path / "nodefacts" / "typeA.json").write_text(json.dumps(facts or _facts()))
        return CliRunner().invoke(cli, ["gen-jobs", "--ident", "b1", "--run-type", "batch",
                                        "--config", str(cfg), "--cbenchtest", str(tmp_path),
                                        "--nodefacts", "typeA", *args])

    def script(job):
        return next((tmp_path / "io-default" / "b1" / job).glob("*.slurm")).read_text()

    return SimpleNamespace(tmp=tmp_path, run=run, script=script)


def test_genjobs_gpfs_group_from_gpfs_parallel_target(genv):
    res = genv.run("--profile", "io-default", "--group", "gpfs")
    assert res.exit_code == 0, res.output
    s = genv.script("gpfsperf-gpfs-4ppn-4")
    assert f'IO_TARGET_DIR="{GPFS}"' in s
    assert re.search(r'opts="-r 8m -n \d+m -th \$threads"', s) and "threads=4\n" in s
    assert 'for op in "create seq" "read seq" "read rand" "write rand"' in s


def test_genjobs_iozone_in_node_local(genv):
    res = genv.run("--profile", "io-default")
    assert res.exit_code == 0, res.output
    s = genv.script("iozone-local-4ppn-4")
    assert re.search(r"-t \$threads -s \d+m -r 4m -F \$files", s) and "threads=4\n" in s
    assert 'IO_TARGET_DIR="/tmp"' in s


def test_genjobs_profile_scripts_have_no_unresolved_tokens(genv):
    res = genv.run("--profile", "io-default", "--group", "all")
    assert res.exit_code == 0, res.output
    for script in (genv.tmp / "io-default" / "b1").glob("*/*.slurm"):
        leftover = re.findall(r"\b[A-Z][A-Z0-9_]*_HERE\w*", script.read_text())
        assert not leftover, f"{script.name}: {leftover}"
