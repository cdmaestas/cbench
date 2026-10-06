"""Per-node gpfsperf (backlog #7c): io-default group gpfs-node, one -dio job per
node, one node at a time by default, and parse's per-node outlier report."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime, timezone

import pytest
from click.testing import CliRunner

from cbench import iosizing, nodecompare, profiles
from cbench.cli.main import cli
from cbench.config import ClusterConfig

GPFS = "/gpfs/zimafs1/cdmaestas"


def _facts(hosts=("zimabg1", "zimabg2")):
    return {"schema_version": 4, "name": "bg", "created": datetime.now(timezone.utc).isoformat(),
            "allow_heterogeneous": False, "hosts": list(hosts),
            "verdict": {"ok": True, "heterogeneous": False, "errors": [], "warnings": []},
            "aggregate": {"cpus": {"min": 8, "max": 8}, "cores": {"min": 4, "max": 4},
                          "memtotal_kb": {"min": 15471748, "max": 15471748}, "models": [],
                          "targets": {"parallel": {"path": GPFS, "fstype": "gpfs", "shared": True,
                                                   "free_kb_min": 5851619328,
                                                   "block_kb": 4096}}}}


def _gen(tmp_path, *args, facts=None, cfg_extra=""):
    (tmp_path / "nodefacts").mkdir(exist_ok=True)
    (tmp_path / "nodefacts" / "bg.json").write_text(json.dumps(facts or _facts()))
    cfg = tmp_path / "c.yaml"
    cfg.write_text(f"cluster_name: zimabg\nmax_nodes: 2\nprocs_per_node: 8\nbatch_method: slurm\n"
                   f"io_targets:\n  parallel: {GPFS}\n" + cfg_extra)
    res = CliRunner().invoke(cli, ["gen-jobs", "--ident", "r1", "--run-type", "batch",
                                   "--nodefacts", "bg", "--config", str(cfg),
                                   "--cbenchtest", str(tmp_path), *args])
    assert res.exit_code == 0, res.output
    return res


def _jobs(tmp_path, testset="io-default"):
    return sorted(p.name for p in (tmp_path / testset / "r1").iterdir())


def _script(tmp_path, job, testset="io-default"):
    return next((tmp_path / testset / "r1" / job).glob("*.slurm")).read_text()


# ---------------------------------------------------------------------------
# sizing / template
# ---------------------------------------------------------------------------

def test_bounded_dio_size_not_2x_ram():
    nv = iosizing.resolve_node_values(ClusterConfig(), _facts())
    t = iosizing.gpfsperfnode_tokens(nv, ClusterConfig(), node="zimabg1", testset="iogpfs",
                                     benchmark="gpfsperfnode")
    assert t["GPFSPERF_SIZE"] == "4096m" and t["GPFSPERF_THREADS"] == "8"
    assert t["GPFSPERF_IOPS_BYTES"] == "256m" and t["PERNODE_HOST"] == "zimabg1"
    cfg = ClusterConfig(gpfsperf_node_size_mib=1000)          # rounded up to the 8m record
    assert iosizing.gpfsperfnode_tokens(nv, cfg, node="n", testset="iogpfs",
                                        benchmark="gpfsperfnode")["GPFSPERF_SIZE"] == "1000m"
    cfg = ClusterConfig(gpfsperf_node_size_mib=1001)
    assert iosizing.gpfsperfnode_tokens(nv, cfg, node="n", testset="iogpfs",
                                        benchmark="gpfsperfnode")["GPFSPERF_SIZE"] == "1008m"


def test_one_job_per_node_pinned_and_serialized(tmp_path):
    _gen(tmp_path, "--profile", "io-default", "--group", "gpfs-node")
    assert _jobs(tmp_path) == ["gpfsperfnode-gpfsnode-zimabg1-8ppn-8",
                               "gpfsperfnode-gpfsnode-zimabg2-8ppn-8"]
    s = _script(tmp_path, "gpfsperfnode-gpfsnode-zimabg2-8ppn-8")
    assert ("#SBATCH -N 1 --ntasks-per-node 8 -w zimabg2 -J cbench-pernode-io-default-r1 "
            "--dependency=singleton") in s
    assert 'NODE="zimabg2"' in s and 'ON_NODE="ssh -o BatchMode=yes $NODE"' in s
    assert 'seq_opts="-r 8m -n 4096m -th $threads -dio"' in s
    assert 'iops_opts="-r 4k -n 256m -th $threads -dio"' in s
    assert "threads=8\n" in s and 'cbench_scratch_dir "$DATADIR"' in s


def test_concurrent_drops_the_singleton(tmp_path):
    _gen(tmp_path, "--profile", "io-default", "--group", "gpfs-node", "--concurrent")
    s = _script(tmp_path, "gpfsperfnode-gpfsnode-zimabg1-8ppn-8")
    assert "#SBATCH -N 1 --ntasks-per-node 8 -w zimabg1\n" in s and "singleton" not in s


def test_nodelist_overrides_facts_hosts(tmp_path):
    _gen(tmp_path, "--profile", "io-default", "--group", "gpfs-node", "--nodelist", "cn-[01-03]")
    assert _jobs(tmp_path) == [f"gpfsperfnode-gpfsnode-cn-0{i}-8ppn-8" for i in (1, 2, 3)]


def test_no_node_list_skips_with_warning(tmp_path):
    res = _gen(tmp_path, "--testset", "iogpfs", facts=_facts(hosts=()))
    assert "skipping gpfsperfnode: no node list" in res.output
    assert not any(j.startswith("gpfsperfnode") for j in _jobs(tmp_path, "iogpfs"))


def test_group_registered_and_opt_in():
    g = profiles.PROFILES["io-default"].groups["gpfs-node"]
    assert (g.target, g.suffix, [m.benchmark for m in g.members]) == ("gpfs", "gpfsnode",
                                                                      ["gpfsperfnode"])
    assert profiles.PROFILES["io-default"].default_groups == ("node-local",)


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")
def test_on_node_runs_locally_on_its_node_else_over_ssh(tmp_path):
    _gen(tmp_path, "--profile", "io-default", "--group", "gpfs-node")
    s = _script(tmp_path, "gpfsperfnode-gpfsnode-zimabg1-8ppn-8")
    block = s[s.index('NODE="zimabg1"'):s.index("fi\n", s.index('NODE="zimabg1"')) + 3]
    me = subprocess.run(["hostname", "-s"], capture_output=True, text=True).stdout.strip()
    for node, expect in ((me, ""), (f"{me}.example.com", ""), ("elsewhere", "ssh -o BatchMode=yes")):
        out = subprocess.run(["bash", "-c", block.replace('NODE="zimabg1"', f'NODE="{node}"')
                              + 'echo "ON=[$ON_NODE]"'], capture_output=True, text=True).stdout
        assert f"ON=[{expect}" in out, (node, out)


# ---------------------------------------------------------------------------
# start-jobs --interactive --concurrent
# ---------------------------------------------------------------------------

def _fake_jobs(tmp_path, n=3):
    base = tmp_path / "t" / "r1"
    for i in range(n):
        d = base / f"job{i}-1ppn-1"
        d.mkdir(parents=True)
        # each job waits until all have started, so a serial run would deadlock
        (d / f"job{i}-1ppn-1.sh").write_text(
            f'touch "{base}/started.{i}"\n'
            f'for _ in $(seq 1 40); do [ $(ls "{base}" | grep -c started) -ge {n} ] && exit 0; '
            "sleep 0.05; done\nexit 7\n")
    return base


def test_interactive_concurrent_starts_all_jobs_at_once(tmp_path):
    _fake_jobs(tmp_path)
    res = CliRunner().invoke(cli, ["start-jobs", "--testset", "t", "--ident", "r1",
                                   "--interactive", "--concurrent", "--cbenchtest", str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert "Submitted 3 job(s)" in res.output


def test_interactive_serial_runs_one_at_a_time(tmp_path):
    _fake_jobs(tmp_path)
    res = CliRunner().invoke(cli, ["start-jobs", "--testset", "t", "--ident", "r1",
                                   "--interactive", "--delay", "0", "--cbenchtest", str(tmp_path)])
    assert res.exit_code == 1 and "exited nonzero" in res.output   # they never overlapped


def test_concurrent_needs_interactive(tmp_path):
    res = CliRunner().invoke(cli, ["start-jobs", "--testset", "t", "--ident", "r1",
                                   "--concurrent", "--cbenchtest", str(tmp_path)])
    assert res.exit_code != 0 and "--concurrent only applies with --interactive" in res.output


# ---------------------------------------------------------------------------
# comparison
# ---------------------------------------------------------------------------

def _row(node, thr, iops, lat, status="PASSED"):
    return {"benchmark": f"gpfsperfnode-gpfsnode-{node}", "node": node, "status": status,
            "metrics": {"create_seq_throughput_MB_s": thr, "read_rand_iops": iops,
                        "read_rand_latency_avg_ms": lat, "create_seq_bytes_transferred": 1e9,
                        "nprocesses": 1.0}}


def test_compare_flags_slow_node_in_each_direction():
    rows = [_row("n1", 100, 700, 10), _row("n2", 101, 705, 10.2), _row("n3", 70, 690, 14)]
    groups, outliers = nodecompare.compare(rows, 10)
    assert set(groups) == {"gpfsperfnode-gpfsnode"} and set(groups["gpfsperfnode-gpfsnode"]) == {
        "n1", "n2", "n3"}
    got = {(o.node, o.metric) for o in outliers}
    assert got == {("n3", "create_seq_throughput_MB_s"), ("n3", "read_rand_latency_avg_ms")}
    assert all(o.metric not in ("create_seq_bytes_transferred", "nprocesses") for o in outliers)


def test_compare_ignores_failed_and_lone_nodes():
    assert nodecompare.compare([_row("n1", 100, 1, 1), _row("n2", 10, 1, 1, "ERROR(X)")], 10)[1] == []
    assert nodecompare.compare([{"benchmark": "imb", "node": None, "status": "PASSED",
                                 "metrics": {"x": 1}}], 10) == ({}, [])


def test_node_from_output_and_group_key():
    assert nodecompare.node_from_output("Cbench gpfsperf: profile=hpc dio=1 node=cn-01\n") == "cn-01"
    assert nodecompare.node_from_output("Cbench gpfsperf: profile=hpc threads=8\n") is None
    assert nodecompare.group_key("gpfsperfnode-gpfsnode-cn-01", "cn-01") == "gpfsperfnode-gpfsnode"


def _job_output(node, create_kbs):
    def op(o, p, rate, ops, lat):
        return (f"/x/gpfsperf {o} {p} /gpfs/x/gpfsperf.dat\n  recSize 8M nBytes 4096M fileSize 4096M\n"
                "  nProcesses 1 nThreadsPerProcess 8\n"
                f"    Data rate was {rate} Kbytes/sec, Op Rate was {ops} Ops/sec, "
                f"Avg Latency was {lat} milliseconds, thread utilization 0.950\n")
    return (f"Cbench gpfsperf: profile=hpc record=8m threads=8 size=4096m dio=1 node={node}\n"
            + op("create", "seq", create_kbs, "9.00", "800.0")
            + op("read", "seq", "115000.00", "14.00", "560.0")
            + op("read", "rand", "2900.00", "714.00", "11.2")
            + op("write", "rand", "14000.00", "3500.00", "2.2")
            + "Cbench gpfsperf: finished\n")


def test_parse_prints_per_node_table_and_outliers(tmp_path, monkeypatch):
    from cbench.cli import main as main_mod
    monkeypatch.setattr(main_mod.console, "width", 300)
    for node, rate in (("zimabg1", "73000.00"), ("zimabg2", "74000.00"), ("zimabg3", "40000.00")):
        d = tmp_path / "io-default" / "r1" / f"gpfsperfnode-gpfsnode-{node}-8ppn-8"
        d.mkdir(parents=True)
        (d / "job.o1").write_text(_job_output(node, rate))
    res = CliRunner().invoke(cli, ["parse", "--testset", "io-default", "--ident", "r1",
                                   "--cbenchtest", str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert "Per-node comparison: gpfsperfnode-gpfsnode (3 nodes)" in res.output
    assert "Outlier nodes (more than 10% worse than the median)" in res.output
    assert re.search(r"zimabg3 gpfsperfnode-gpfsnode create_seq_throughput_MB_s=39\.\d+ "
                     r"\(median 71\.\d+, 45% worse\)", res.output), res.output
    res = CliRunner().invoke(cli, ["parse", "--testset", "io-default", "--ident", "r1",
                                   "--cbenchtest", str(tmp_path), "--outlier-pct", "50"])
    assert "No outlier nodes (all within 50% of the median)" in res.output
