"""MCP layer (backlog #5): the operations `cbench mcp` exposes (cbench.mcp_tools).
No MCP SDK needed: these run on every supported Python."""
from __future__ import annotations

import json
import time

import pytest
import yaml
from click.testing import CliRunner

from cbench import mcp_tools as t
from cbench import upstream
from cbench.cli.main import cli
from cbench.db import ParseResult, ResultsDB


@pytest.fixture
def ct(tmp_path, monkeypatch):
    """An empty CBENCHTEST with no cluster.yaml anywhere on the search path."""
    for var in ("CBENCHOME", "CBENCHSTANDALONEDIR", "CBENCHCLUSTER"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("CBENCHTEST", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# cluster.yaml
# ---------------------------------------------------------------------------

def test_set_config_plans_then_writes_with_backup(ct):
    cy = ct / "cluster.yaml"
    cy.write_text("# site config\ncluster_name: zima\nmax_nodes: 2\n")
    plan = t.set_config({"max_nodes": 4, "fio_runtime_s": 120}, remove=["cluster_name"])
    assert plan["confirmed"] is False and "confirm=true" in plan["next"]
    assert plan["diff"] == {"set": {"max_nodes": {"old": 2, "new": 4},
                                    "fio_runtime_s": {"old": None, "new": 120}},
                            "removed": ["cluster_name"]}
    assert "comments" in plan["note"]
    assert "max_nodes: 2" in cy.read_text()                     # nothing written yet
    done = t.set_config({"max_nodes": 4, "fio_runtime_s": 120}, remove=["cluster_name"], confirm=True)
    assert done["changed"] and done["backup"].endswith("cluster.yaml.bak")
    assert yaml.safe_load(cy.read_text()) == {"max_nodes": 4, "fio_runtime_s": 120}
    assert "max_nodes: 2" in (ct / "cluster.yaml.bak").read_text()
    assert t.get_config()["set_in_file"] == ["fio_runtime_s", "max_nodes"]


def test_set_config_validates_before_writing(ct):
    with pytest.raises(t.ToolError, match="io_profile"):
        t.set_config({"io_profile": "fast"}, confirm=True)
    with pytest.raises(t.ToolError, match="not both"):
        t.set_config({"io_profile": "hpc", "fio_profile": "ai"}, confirm=True)
    with pytest.raises(t.ToolError, match="nothing to change"):
        t.set_config()
    assert not (ct / "cluster.yaml").exists()


def test_set_config_creates_file_in_cbenchtest_and_noop(ct):
    out = t.set_config({"cluster_name": "bg", "io_targets": {"parallel": "/gpfs/x"}}, confirm=True)
    assert out["creates_file"] and out["backup"] is None
    assert yaml.safe_load((ct / "cluster.yaml").read_text())["io_targets"] == {"parallel": "/gpfs/x"}
    again = t.set_config({"cluster_name": "bg"}, confirm=True)
    assert again["changed"] is False


def test_get_config_schema_and_defaults(ct):
    out = t.get_config(include_schema=True)
    assert out["config_file"] is None and out["set_in_file"] == []
    assert out["values"]["job_heartbeat_s"] == 60 and "explicit_keys" not in out["values"]
    assert "io_profile" in out["schema"]["properties"]


# ---------------------------------------------------------------------------
# read-only views
# ---------------------------------------------------------------------------

def test_list_testsets_and_profiles(ct):
    out = t.list_testsets()
    assert "fio" in out["testsets"]["iometadata"]
    for helper in ("common", "slurm", "xhpl", "hpccinf", "interactive"):
        assert helper not in out["testsets"], helper
    io = out["profiles"]["io-default"]
    assert io["custom"] is False and "iometadata_fio" in io["groups"]["node-local"]["members"]


def _facts(ct, name="bg", ok=True):
    from cbench import nodecheck
    facts = {"schema_version": 4, "name": name, "created": "2025-01-01T00:00:00+00:00",
             "nodelist": "zimabg[1-2]", "hosts": ["zimabg1", "zimabg2"],
             "aggregate": {"cpus": 8}, "verdict": {"ok": ok, "errors": [] if ok else ["cpu mismatch"]}}
    nodecheck.write_facts(nodecheck.facts_path(ct, name), facts)


def test_node_facts_list_and_show(ct):
    _facts(ct)
    _facts(ct, "bad", ok=False)
    assert {f["name"]: f["ok"] for f in t.node_facts()["facts"]} == {"bad": False, "bg": True}
    one = t.node_facts("bg")
    assert one["hosts"] == ["zimabg1", "zimabg2"] and one["aggregate"] == {"cpus": 8}
    assert any("days old" in w for w in one["warnings"])
    assert any("FAILED" in w for w in t.node_facts("bad")["warnings"])
    with pytest.raises(t.ToolError, match="Invalid facts name"):
        t.node_facts("../x")
    with pytest.raises(t.ToolError, match="run nodecheck first"):
        t.node_facts("nope")


def test_status(ct):
    _facts(ct)
    (ct / "io-default" / "r1").mkdir(parents=True)
    out = t.status()
    assert out["cbenchtest"] == str(ct) and out["config_file"] is None
    assert out["node_facts"][0]["name"] == "bg" and out["testsets_with_jobs"] == ["io-default"]
    assert out["results_db"] is None


def test_watch_jobs(ct):
    d = ct / "t" / "r1" / "a"
    d.mkdir(parents=True)
    (d / "a.heartbeat").write_text(
        "Cbench heartbeat: a (jobid 7) exited rc=0, elapsed 0h00m05s at 2026-10-05 12:00:00, every 60s\n")
    (ct / "t" / "r1" / "b").mkdir()
    out = t.watch_jobs("t", "r1")
    assert out["counts"] == {"finished": 1, "not started": 1} and not out["all_done"]
    assert out["jobs"][0]["status"] == "finished"
    with pytest.raises(t.ToolError, match="run gen_jobs first"):
        t.watch_jobs("t", "r2")
    with pytest.raises(t.ToolError, match="invalid testset"):
        t.watch_jobs("../etc", "r1")


def test_query_results(ct):
    with pytest.raises(t.ToolError, match="no results database"):
        t.query_results()
    ResultsDB(ct / "cbench_results.db").store(ParseResult(
        cluster="bg", testset="t", ident="r1", jobname="fio-8ppn-8", benchmark="fio",
        numprocs=8, ppn=8, numnodes=1, status="PASSED",
        metrics={"seq_read_bw_MiB_s": 900.0}, metric_units={"seq_read_bw_MiB_s": "MiB/s"}))
    out = t.query_results(benchmark="fio")
    assert out["count"] == 1
    assert out["results"][0]["metrics"]["seq_read_bw_MiB_s"]["value"] == 900.0
    assert t.query_results(benchmark="ior")["count"] == 0


# ---------------------------------------------------------------------------
# dependencies / updates
# ---------------------------------------------------------------------------

def test_check_deps_suggests_and_never_installs(ct, monkeypatch):
    import shutil as _shutil

    from cbench.builders import _util
    monkeypatch.setattr(_shutil, "which", lambda name: None)
    monkeypatch.setattr(_util.shutil, "which", lambda name: None)
    out = t.check_deps(["fio", "stream"])
    fio = next(s for s in out["system"] if s["tool"] == "fio")
    assert fio["found"] is False and fio["suggest"] == "fio"
    sbatch = next(s for s in out["system"] if s["tool"] == "sbatch")
    assert "Slurm" in sbatch["suggest"]
    stream = next(b for b in out["benchmarks"] if b["benchmark"] == "stream")
    assert stream["built"] is False and stream["missing"]
    assert "admin" in stream["next"]
    with pytest.raises(t.ToolError, match="unknown benchmark"):
        t.check_deps(["nosuch"])


def test_check_deps_sees_a_build(ct, monkeypatch):
    (ct / "bin").mkdir()
    (ct / "bin" / "stream_c.exe").write_text("")
    (ct / "build.lock").write_text(json.dumps({"stream": {
        "source_url": "x", "config_hash": "y", "built_at": "2026-10-01", "binaries": ["stream_c.exe"]}}))
    row = t.check_deps(["stream"])["benchmarks"][0]
    assert row["built"] is True and "next" not in row


def test_check_updates(ct, monkeypatch):
    monkeypatch.setattr(upstream, "check_builder", lambda b, src: upstream.Check(
        b.name, "tarball", "1", "2" if b.name == "npb" else "1",
        upstream.UPDATE if b.name == "npb" else upstream.UP_TO_DATE))
    out = t.check_updates(["npb", "hpl"])
    assert out["updates"] == ["npb"] and len(out["checks"]) == 2


# ---------------------------------------------------------------------------
# side effects need confirm
# ---------------------------------------------------------------------------

def test_plans_change_nothing(ct):
    plan = t.gen_jobs("r1", testset="mpisanity", nodefacts="bg", groups=["a", "b"])
    assert plan["confirmed"] is False
    assert plan["would_run"].startswith("cbench gen-jobs --ident r1 --testset=mpisanity --group=a --group=b")
    assert "--nodefacts=bg" in plan["would_run"]
    assert not (ct / "mpisanity").exists()
    nc = t.run_nodecheck(nodelist="zimabg[1-2]", allow_heterogeneous=True)
    assert "--allow-heterogeneous" in nc["would_run"] and not (ct / "nodefacts").exists()
    (ct / "t" / "r1").mkdir(parents=True)
    sj = t.start_jobs("t", "r1", mode="interactive", match="fio")
    assert sj["would_run"].startswith("cbench start-jobs --testset t --ident r1 --interactive --match=fio")
    assert not (ct / ".cbench-mcp").exists()


def test_option_values_cannot_become_options(ct):
    (ct / "t" / "r1").mkdir(parents=True)
    plan = t.start_jobs("t", "r1", match="--dry-run")
    assert "--match=--dry-run" in plan["would_run"].split()
    assert "--dry-run" not in plan["would_run"].split()


def test_argument_checks(ct):
    with pytest.raises(t.ToolError, match="exactly one of testset or profile"):
        t.gen_jobs("r1")
    with pytest.raises(t.ToolError, match="invalid ident"):
        t.gen_jobs("a/b", testset="x")
    with pytest.raises(t.ToolError, match="exactly one of nodelist or partition"):
        t.run_nodecheck()
    with pytest.raises(t.ToolError, match="mode must be"):
        t.start_jobs("t", "r1", mode="now")
    with pytest.raises(t.ToolError, match="run gen_jobs first"):
        t.start_jobs("t", "r1")


def test_gen_jobs_confirmed_runs_the_cli(ct):
    (ct / "cluster.yaml").write_text("cluster_name: bg\nprocs_per_node: 2\nmax_nodes: 1\n"
                                     "memory_per_node_mb: 4096\nbatch_method: slurm\n")
    out = t.gen_jobs("r1", testset="mpisanity", maxprocs=2, confirm=True)
    assert out["ok"], out
    assert out["jobs"] and all("ppn" in j for j in out["jobs"])
    w = t.watch_jobs("mpisanity", "r1")
    assert set(w["counts"]) == {"not started"}


def test_parse_results_reads_results_json(ct):
    d = ct / "t" / "r1" / "nosuch-1ppn-1"
    d.mkdir(parents=True)
    (d / "nosuch-1ppn-1.o5").write_text("hello\n")
    out = t.parse_results("t", "r1")
    assert out["ok"], out
    assert out["counts"] == {"NO_PARSER": 1} and out["results"][0]["jobname"] == "nosuch-1ppn-1"
    assert t.query_results(testset="t")["count"] == 1
    with pytest.raises(t.ToolError, match="no jobs"):
        t.parse_results("t", "r2")


def test_build_benchmark_consent_and_refusal(ct, monkeypatch):
    from cbench.builders import REGISTRY
    monkeypatch.setattr(REGISTRY["stream"], "check_requires", lambda self: ["cc"])
    out = t.build_benchmark("stream", confirm=True)
    assert out["refused"] and out["missing"][0]["suggest"] == "gcc"
    monkeypatch.setattr(REGISTRY["stream"], "check_requires", lambda self: [])
    plan = t.build_benchmark("stream")
    assert plan["confirmed"] is False and plan["source"].startswith("https://")
    with pytest.raises(t.ToolError, match="unknown benchmark"):
        t.build_benchmark("nosuch")


def _wait(task_id, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        st = t.task_status(task_id)
        if st["state"] != "running":
            return st
        time.sleep(0.2)
    raise AssertionError(f"task {task_id} still running")


def test_tasks_run_detached_and_report(ct):
    ok = t.start_task(["--version"], str(ct), "test")
    assert ok["confirmed"] and len(ok["task_id"]) == 12
    st = _wait(ok["task_id"])
    assert (st["state"], st["exit_code"]) == ("finished", 0) and "cbench" in st["log_tail"]
    bad = _wait(t.start_task(["no-such-command"], str(ct), "test")["task_id"])
    assert bad["state"] == "failed" and bad["exit_code"] == 2
    with pytest.raises(t.ToolError, match="invalid task id"):
        t.task_status("../../x")
    with pytest.raises(t.ToolError, match="no task"):
        t.task_status("0" * 12)


def test_no_cbenchtest(monkeypatch):
    monkeypatch.delenv("CBENCHTEST", raising=False)
    with pytest.raises(t.ToolError, match="no CBENCHTEST"):
        t.node_facts()


def test_cli_mcp_without_sdk(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "cbench.mcp_server", None)
    res = CliRunner().invoke(cli, ["mcp"])
    assert res.exit_code != 0 and "pip install 'cbench[mcp]'" in res.output
