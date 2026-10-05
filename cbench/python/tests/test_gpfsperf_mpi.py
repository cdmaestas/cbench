"""Multi-node gpfsperf-mpi (backlog #7b): io-default group gpfs-mpi, one job
per node count at ppn = IO threads (-th 1), one shared file of 2x the RAM of
the job's nodes."""
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone

import pytest
from click.testing import CliRunner

from cbench import iosizing, profiles
from cbench.cli.main import cli
from cbench.config import ClusterConfig
from cbench.parsers import get_parser
from cbench.parsers.gpfsperf import GpfsperfParser

MEM_KB = 7706776            # zima type A MemTotal
GPFS = "/gpfs/zimafs1/cdmaestas"


def _nv(free_kb=5852028928):
    return iosizing.NodeValues(
        cpus=4, mem_io_kb=MEM_KB, mem_nonio_kb=MEM_KB,
        targets={"gpfs": {"path": GPFS, "fstype": "gpfs", "shared": True, "free_kb_min": free_kb}})


def _cfg():
    cfg = ClusterConfig()
    cfg.explicit_keys = frozenset()
    return cfg


# ---------------------------------------------------------------------------
# sizing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(("nodes", "ranks", "size_m", "iops_m"), [
    (1, 4, 15056, 1024),
    (2, 8, 30112, 2048),      # 2x RAM of both nodes, rounded up to the 8m record
    (4, 16, 60216, 4096),
])
def test_file_scales_with_nodes_and_iops_with_ranks(nodes, ranks, size_m, iops_m):
    t = iosizing.gpfsperfmpi_tokens(_nv(), _cfg(), numnodes=nodes, numprocs=ranks,
                                    testset="iogpfs", benchmark="gpfsperfmpi")
    assert t["GPFSPERF_SIZE"] == f"{size_m}m" and size_m % 8 == 0
    assert size_m * 1024 >= 2 * MEM_KB * nodes
    assert t["GPFSPERF_IOPS_BYTES"] == f"{iops_m}m"
    assert (t["GPFSPERF_RECORD"], t["GPFSPERF_IOPS_RECORD"]) == ("8m", "4k")
    assert t["IO_TARGET_DIR"] == GPFS and t["IO_REQUIRED_KB"] == str(size_m * 1024)
    assert "GPFSPERF_THREADS" not in t        # ranks come from the launcher, -th 1


def test_capped_to_free_space_with_caveat():
    t = iosizing.gpfsperfmpi_tokens(_nv(free_kb=20 * 1024 ** 2), _cfg(), numnodes=4,
                                    numprocs=16, testset="iogpfs", benchmark="gpfsperfmpi")
    assert int(t["GPFSPERF_SIZE"][:-1]) * 1024 <= 20 * 1024 ** 2 * 0.9
    assert "2x RAM of 4 nodes" in t["IO_CAVEAT"]


def test_single_node_gpfsperf_unchanged():
    t = iosizing.gpfsperf_tokens(_nv(), _cfg(), testset="iogpfs", benchmark="gpfsperf")
    assert (t["GPFSPERF_SIZE"], t["GPFSPERF_THREADS"], t["GPFSPERF_IOPS_BYTES"]) == (
        "15056m", "4", "1024m")


# ---------------------------------------------------------------------------
# gen-jobs
# ---------------------------------------------------------------------------

def _facts():
    return {"schema_version": 4, "name": "t", "created": datetime.now(timezone.utc).isoformat(),
            "allow_heterogeneous": False,
            "verdict": {"ok": True, "heterogeneous": False, "errors": [], "warnings": []},
            "aggregate": {"cpus": {"min": 4, "max": 4}, "cores": {"min": 4, "max": 4},
                          "memtotal_kb": {"min": MEM_KB, "max": MEM_KB}, "models": [],
                          "targets": {"parallel": {"path": GPFS, "fstype": "gpfs", "shared": True,
                                                   "free_kb_min": 5852028928}}}}


def _gen(tmp_path, *args, max_nodes=4):
    (tmp_path / "nodefacts").mkdir(exist_ok=True)
    (tmp_path / "nodefacts" / "t.json").write_text(json.dumps(_facts()))
    cfg = tmp_path / "c.yaml"
    cfg.write_text(f"cluster_name: zima\nmax_nodes: {max_nodes}\nprocs_per_node: 4\n"
                   f"batch_method: slurm\nio_targets:\n  parallel: {GPFS}\n")
    res = CliRunner().invoke(cli, ["gen-jobs", "--ident", "m1", "--run-type", "batch",
                                   "--nodefacts", "t", "--config", str(cfg),
                                   "--cbenchtest", str(tmp_path), *args])
    assert res.exit_code == 0, res.output
    return res


def _jobs(tmp_path, testset):
    return sorted(p.name for p in (tmp_path / testset / "m1").iterdir())


def _script(tmp_path, testset, job):
    return next((tmp_path / testset / "m1" / job).glob("*.slurm")).read_text()


def test_gpfs_mpi_group_one_job_per_node_count(tmp_path):
    _gen(tmp_path, "--profile", "io-default", "--group", "gpfs-mpi")
    assert _jobs(tmp_path, "io-default") == [
        "gpfsperfmpi-gpfsmpi-4ppn-16", "gpfsperfmpi-gpfsmpi-4ppn-4", "gpfsperfmpi-gpfsmpi-4ppn-8"]
    s = _script(tmp_path, "io-default", "gpfsperfmpi-gpfsmpi-4ppn-8")
    assert "#SBATCH -N 2 --ntasks-per-node 4" in s
    assert '--map-by ppr:4:node -np 8 $GPFSPERFMPI $op $file $seq_opts"' in s
    assert 'seq_opts="-r 8m -n 30112m -th 1"' in s and 'iops_opts="-r 4k -n 2048m -th 1"' in s
    assert 'cbench_scratch_dir "$DATADIR"' in s and 'IO_TARGET_DIR="/gpfs/zimafs1/cdmaestas"' in s


def test_maxprocs_limits_the_sweep(tmp_path):
    _gen(tmp_path, "--profile", "io-default", "--group", "gpfs-mpi", "--maxprocs", "8")
    assert _jobs(tmp_path, "io-default") == ["gpfsperfmpi-gpfsmpi-4ppn-4",
                                             "gpfsperfmpi-gpfsmpi-4ppn-8"]


def test_gpfs_group_stays_single_node(tmp_path):
    _gen(tmp_path, "--profile", "io-default", "--group", "gpfs")
    assert _jobs(tmp_path, "io-default") == ["gpfsperf-gpfs-4ppn-4"]


def test_iogpfs_testset_has_both(tmp_path):
    _gen(tmp_path, "--testset", "iogpfs", max_nodes=2)
    assert _jobs(tmp_path, "iogpfs") == ["gpfsperf-4ppn-4", "gpfsperfmpi-4ppn-4",
                                         "gpfsperfmpi-4ppn-8"]


def test_gpfs_mpi_group_registered():
    g = profiles.PROFILES["io-default"].groups["gpfs-mpi"]
    assert (g.target, g.suffix, [m.benchmark for m in g.members]) == ("gpfs", "gpfsmpi",
                                                                      ["gpfsperfmpi"])
    assert profiles.PROFILES["io-default"].default_groups == ("node-local",)


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")
def test_generated_script_is_valid_bash(tmp_path):
    _gen(tmp_path, "--profile", "io-default", "--group", "gpfs-mpi")
    path = next((tmp_path / "io-default" / "m1" / "gpfsperfmpi-gpfsmpi-4ppn-16").glob("*.slurm"))
    assert subprocess.run(["bash", "-n", str(path)]).returncode == 0


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------

def _op(op, pattern, rate, ops, lat_ms):
    # current gpfsperf result line (see test_parser_gpfsperf's full format)
    return (f"/u/c/bin/gpfsperf-mpi {op} {pattern} /gpfs/x/gpfsperfmpi.1/gpfsperf.dat\n"
            "  recSize 8M nBytes 30112M fileSize 30112M\n"
            "  nProcesses 8 nThreadsPerProcess 1\n"
            "  file cache flushed before test\n  not using data shipping\n"
            f"    Data rate was {rate} Kbytes/sec, Op Rate was {ops} Ops/sec, "
            f"Avg Latency was {lat_ms} milliseconds, thread utilization 0.950\n")


_MPI_JOB = ("Cbench gpfsperf: profile=hpc record=8m iops_record=4k ranks=8 nodes=2 size=30112m "
            "iops_bytes=2048m\n"
            + _op("create", "seq", "819200.00", "100.00", "79.000")
            + _op("read", "seq", "1048576.00", "128.00", "62.000")
            + _op("read", "rand", "40960.00", "10240.00", "0.780")
            + _op("write", "rand", "20480.00", "5120.00", "1.560")
            + "Cbench gpfsperf: finished\n")


@pytest.mark.parametrize("jobbench", ["gpfsperfmpi", "gpfsperfmpi-gpfsmpi"])
def test_parser_resolves_job_names(jobbench):
    assert isinstance(get_parser(jobbench), GpfsperfParser)


def test_parse_multi_op_mpi_job():
    r = GpfsperfParser().parse(_MPI_JOB)
    assert r.status == "PASSED", r.status_detail
    assert r.metrics["create_seq_throughput_MB_s"] == pytest.approx(800.0)
    assert r.metrics["read_seq_throughput_MB_s"] == pytest.approx(1024.0)
    assert r.metrics["read_rand_iops"] == pytest.approx(10240.0)
    assert r.metrics["write_rand_iops"] == pytest.approx(5120.0)
    assert r.metrics["nprocesses"] == pytest.approx(8.0)     # job-level, all ranks


def test_unfinished_mpi_job_is_started_not_passed():
    r = GpfsperfParser().parse(_MPI_JOB.replace("Cbench gpfsperf: finished\n", ""))
    assert r.status == "ERROR(STARTED)"
