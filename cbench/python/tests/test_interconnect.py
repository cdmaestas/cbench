"""Interconnect / GPFS transport check (backlog #3): nodecheck probe + analysis,
facts v3, gen-jobs CBENCH LABEL, and `cbench parse` keeping it."""
from __future__ import annotations

import json
import shutil
import socket
import sqlite3
import subprocess
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner

from cbench import iosizing
from cbench import nodecheck as nc
from cbench.cli.main import cli
from cbench.config import ClusterConfig

IB_UP = "InfiniBand|4: ACTIVE|100 Gb/sec (4X EDR)"
IB_DOWN = "InfiniBand|1: DOWN|10 Gb/sec (4X SDR)"
ROCE_UP = "Ethernet|4: ACTIVE|100 Gb/sec (2X EDR)"


def _host(cpus="4", **extra):
    f = {"_complete": "1", "cpus": cpus, "cores": cpus, "memtotal_kb": "8000000", "model": "x"}
    f.update(extra)
    return f


def _gpfs(verbs="enable", ports="mlx5_0/1", scoped="0"):
    return {"gpfs.cfg": "1", "gpfs.verbs_rdma": verbs, "gpfs.verbs_ports": ports,
            "gpfs.verbs_scoped": scoped}


# ---------------------------------------------------------------------------
# per-host classification
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(("ports", "expected"), [
    ({}, "tcp"),
    ({"rdma.mlx5_0/1": IB_UP}, "ib"),
    ({"rdma.mlx5_0/1": IB_DOWN}, "tcp"),
    ({"rdma.mlx5_0/1": ROCE_UP}, "roce"),
    ({"rdma.mlx5_0/1": IB_UP, "rdma.mlx5_1/1": ROCE_UP}, "ib+roce"),
])
def test_interconnect_from_active_ports(ports, expected):
    ic, gpfs, notes = nc.interconnect(ports)
    assert ic == expected and gpfs is None and notes == []


@pytest.mark.parametrize(("ports", "gpfs_keys", "transport", "note"), [
    ({"rdma.mlx5_0/1": IB_UP}, _gpfs(), "rdma", None),
    ({"rdma.mlx5_0/1": IB_UP}, _gpfs(verbs="disable"), "tcp", None),
    ({"rdma.mlx5_0/1": IB_UP}, _gpfs(verbs=""), "tcp", None),
    ({"rdma.mlx5_0/1": IB_DOWN}, _gpfs(), "tcp", "mlx5_0/1 is not ACTIVE"),
    ({"rdma.mlx5_0/1": IB_UP}, _gpfs(ports="mlx5_1/1"), "tcp", "mlx5_1/1 is not ACTIVE"),
    ({"rdma.mlx5_0/1": IB_UP}, _gpfs(ports="mlx5_0"), "rdma", None),          # port 1 default
    ({"rdma.mlx5_0/1": IB_UP}, _gpfs(ports="mlx5_0/1/1"), "rdma", None),      # /fabric suffix
    ({"rdma.mlx5_0/1": IB_UP}, _gpfs(ports=""), "rdma", None),                # any active port
    ({}, _gpfs(ports=""), "tcp", "any RDMA port is not ACTIVE"),
    ({"rdma.mlx5_0/1": IB_UP}, _gpfs(scoped="1"), "rdma", "other node sections"),
    ({}, {"gpfs.cfg": "unreadable"}, "unknown", "not readable"),
])
def test_gpfs_transport(ports, gpfs_keys, transport, note):
    _, gpfs, notes = nc.interconnect({**ports, **gpfs_keys})
    assert gpfs == transport
    if note:
        assert any(note in n for n in notes), notes
    else:
        assert notes == []


# ---------------------------------------------------------------------------
# the probe itself (sh + awk) against a fake sysfs and mmfs.cfg
# ---------------------------------------------------------------------------

def _run_probe(tmp_path, mmfs_cfg: str | None, ports: dict[str, tuple[str, str, str]]):
    sysfs = tmp_path / "sys" / "class" / "infiniband"
    for name, (ll, state, rate) in ports.items():
        dev, port = name.split("/")
        d = sysfs / dev / "ports" / port
        d.mkdir(parents=True)
        (d / "link_layer").write_text(ll + "\n")
        (d / "state").write_text(state + "\n")
        (d / "rate").write_text(rate + "\n")
    cfg = tmp_path / "mmfs.cfg"
    if mmfs_cfg is not None:
        cfg.write_text(mmfs_cfg)
    script = ("\n".join(nc._INTERCONNECT_PROBE)
              .replace("/sys/class/infiniband", str(sysfs))
              .replace(nc._MMFS_CFG, str(cfg)))
    r = subprocess.run(["sh", "-c", script], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return nc.parse_output("".join(f"n1: {ln}\n" for ln in r.stdout.splitlines())).get("n1", {})


@pytest.mark.skipif(shutil.which("awk") is None, reason="awk not installed")
def test_probe_reads_sysfs_and_section_scoped_mmfs_cfg(tmp_path):
    me = socket.gethostname().split(".")[0]
    cfg = (
        "# machine generated\nclusterName zima.cluster\n"
        "verbsRdma disable\n"
        f"[{me}.example.com,othernode]\nverbsRdma enable\nverbsPorts mlx5_0/1 mlx5_1/1\n"
        "[common]\nmaxMBpS 2048\n"
    )
    f = _run_probe(tmp_path, cfg, {"mlx5_0/1": ("InfiniBand", "4: ACTIVE", "100 Gb/sec (4X EDR)"),
                                   "mlx5_1/1": ("InfiniBand", "1: DOWN", "10 Gb/sec")})
    assert f["rdma.mlx5_0/1"] == IB_UP
    assert f["gpfs.verbs_rdma"] == "enable" and f["gpfs.verbs_ports"] == "mlx5_0/1 mlx5_1/1"
    assert f["gpfs.verbs_scoped"] == "0"
    assert nc.interconnect(f)[:2] == ("ib", "rdma")


@pytest.mark.skipif(shutil.which("awk") is None, reason="awk not installed")
def test_probe_flags_settings_scoped_to_other_nodes(tmp_path):
    cfg = "verbsRdma disable\n[some_node_class]\nverbsRdma enable\n[common]\n"
    f = _run_probe(tmp_path, cfg, {})
    assert f["gpfs.verbs_rdma"] == "disable" and f["gpfs.verbs_scoped"] == "1"
    ic, gpfs, notes = nc.interconnect(f)
    assert (ic, gpfs) == ("tcp", "tcp") and any("node classes" in n for n in notes)


def test_probe_without_rdma_or_gpfs_prints_nothing(tmp_path):
    assert _run_probe(tmp_path, None, {}) == {}


def test_probe_script_includes_interconnect_section():
    s = nc.build_probe_script({})
    assert "/sys/class/infiniband/*/ports/*" in s and nc._MMFS_CFG in s
    assert s.rstrip().endswith(nc._SENTINEL.join(['echo "', '"']))


# ---------------------------------------------------------------------------
# analyze: a mismatch is an error unless --allow-heterogeneous
# ---------------------------------------------------------------------------

def test_uniform_pool_records_transport():
    hosts = {h: _host(**{"rdma.mlx5_0/1": IB_UP}, **_gpfs()) for h in ("n1", "n2")}
    r = nc.analyze(["n1", "n2"], hosts, {})
    assert r["verdict"]["ok"], r["verdict"]
    assert r["aggregate"]["interconnect"] == "ib" and r["aggregate"]["gpfs_transport"] == "rdma"


def test_no_gpfs_leaves_gpfs_transport_unset():
    r = nc.analyze(["n1"], {"n1": _host()}, {})
    assert r["aggregate"]["interconnect"] == "tcp" and r["aggregate"]["gpfs_transport"] is None


def test_node_fallen_back_to_tcp_is_an_error():
    hosts = {"n1": _host(**{"rdma.mlx5_0/1": IB_UP}, **_gpfs()),
             "n2": _host(**{"rdma.mlx5_0/1": IB_DOWN}, **_gpfs())}
    r = nc.analyze(["n1", "n2"], hosts, {})
    assert not r["verdict"]["ok"] and r["verdict"]["heterogeneous"]
    errs = " | ".join(r["verdict"]["errors"])
    assert "interconnect differs" in errs and "GPFS transport differs" in errs
    assert "node set is heterogeneous" in errs
    assert any("n2: GPFS verbsRdma is enabled" in w for w in r["verdict"]["warnings"])


def test_mismatch_allowed_becomes_warning_and_mixed():
    hosts = {"n1": _host(**{"rdma.mlx5_0/1": IB_UP}), "n2": _host()}
    r = nc.analyze(["n1", "n2"], hosts, {}, allow_heterogeneous=True)
    assert r["verdict"]["ok"]
    assert any("interconnect differs" in w for w in r["verdict"]["warnings"])
    assert r["aggregate"]["interconnect"] == "mixed"


def test_group_summary_splits_on_transport():
    hosts = {"n1": _host(**{"rdma.mlx5_0/1": IB_UP}), "n2": _host(**{"rdma.mlx5_0/1": IB_UP}),
             "n3": _host()}
    rows = nc.group_summary(hosts, ["n1", "n2", "n3"], {})
    assert [(r["hosts"], r["interconnect"], r["gpfs_transport"]) for r in rows] == [
        ("n[1-2]", "ib", "-"), ("n3", "tcp", "-")]


# ---------------------------------------------------------------------------
# facts v3 -> gen-jobs label -> parse status_detail
# ---------------------------------------------------------------------------

def _facts(**agg_extra):
    agg = {"cpus": {"min": 2, "max": 2}, "cores": {"min": 2, "max": 2},
           "memtotal_kb": {"min": 8000000, "max": 8000000}, "models": [], "targets": {}}
    agg.update(agg_extra)
    return {"schema_version": 3, "name": "t", "created": datetime.now(timezone.utc).isoformat(),
            "allow_heterogeneous": False,
            "verdict": {"ok": True, "heterogeneous": False, "errors": [], "warnings": []},
            "aggregate": agg}


def test_schema_v3_and_older_still_load(tmp_path):
    assert nc.SCHEMA_VERSION >= 3 and {1, 2, 3} <= set(nc.SUPPORTED_SCHEMA_VERSIONS)
    for v in (1, 2, 3):
        f = _facts()
        f["schema_version"] = v
        (tmp_path / "nodefacts").mkdir(exist_ok=True)
        (tmp_path / "nodefacts" / f"v{v}.json").write_text(json.dumps(f))
        nc.load_facts(tmp_path, f"v{v}")


@pytest.mark.parametrize(("agg", "labels"), [
    ({"interconnect": "ib", "gpfs_transport": "rdma"}, "interconnect=ib gpfs_transport=rdma"),
    ({"interconnect": "tcp", "gpfs_transport": None}, "interconnect=tcp"),
    ({}, ""),                                   # facts v1/v2
])
def test_labels_from_facts(agg, labels):
    nv = iosizing.resolve_node_values(ClusterConfig(), _facts(**agg))
    assert nv.labels == labels
    assert iosizing.resolve_node_values(ClusterConfig()).labels == ""


def _genjobs(tmp_path, facts):
    (tmp_path / "nodefacts").mkdir()
    (tmp_path / "nodefacts" / "t.json").write_text(json.dumps(facts))
    cfg = tmp_path / "c.yaml"
    cfg.write_text("cluster_name: zima\nmax_nodes: 1\nprocs_per_node: 2\nbatch_method: slurm\n")
    res = CliRunner().invoke(cli, ["gen-jobs", "--testset", "latency", "--ident", "t1",
                                   "--run-type", "batch", "--ppn", "2", "--maxprocs", "2",
                                   "--match", "^imb-2ppn-2", "--nodefacts", "t",
                                   "--config", str(cfg), "--cbenchtest", str(tmp_path)])
    assert res.exit_code == 0, res.output
    return (tmp_path / "latency" / "t1" / "imb-2ppn-2" / "imb-2ppn-2.slurm").read_text()


def _label_block_output(script: str) -> str:
    start = script.index('CBENCH_LABELS="')
    block = script[start:script.index("esac\n", start) + 5]
    return subprocess.run(["bash", "-c", 'cbench_echo() { echo "$@"; }\n' + block],
                          capture_output=True, text=True).stdout


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")
def test_job_prints_label_from_facts(tmp_path):
    s = _genjobs(tmp_path, _facts(interconnect="ib", gpfs_transport="rdma"))
    assert _label_block_output(s) == "CBENCH LABEL: interconnect=ib gpfs_transport=rdma\n"


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")
def test_job_without_v3_facts_prints_no_label(tmp_path):
    s = _genjobs(tmp_path, _facts())
    assert _label_block_output(s) == ""
    # a Perl-rendered script leaves the bare token: also silent
    perl = s.replace('CBENCH_LABELS=""', 'CBENCH_LABELS="CBENCH_LABELS_HERE"')
    assert _label_block_output(perl) == ""


def test_parse_keeps_label_in_status_detail(tmp_path):
    fixture = next((Path(__file__).parent / "fixtures" / "io").glob("mdtest*"))
    d = tmp_path / "iometadata" / "r1" / "mdtest-4ppn-4"
    d.mkdir(parents=True)
    (d / "job.o1").write_text("CBENCH LABEL: interconnect=ib gpfs_transport=rdma\n"
                              + fixture.read_text())
    res = CliRunner().invoke(cli, ["parse", "--testset", "iometadata", "--ident", "r1",
                                   "--cbenchtest", str(tmp_path)])
    assert res.exit_code == 0, res.output
    with closing(sqlite3.connect(tmp_path / "cbench_results.db")) as con:
        status, detail = con.execute("SELECT status, status_detail FROM runs").fetchone()
    assert status == "PASSED"
    assert "CBENCH LABEL: interconnect=ib gpfs_transport=rdma" in detail
