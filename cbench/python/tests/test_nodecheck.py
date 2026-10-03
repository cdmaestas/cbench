"""Tests for cbench nodecheck (node precheck + homogeneity + facts file).

Uses fake pdsh output shaped like zima: zima[1-4] (type A), zimabg[1-2]
(type B), zimad (type C). No real pdsh or remote nodes are needed.
"""

import json
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from cbench import nodecheck as nc
from cbench.cli import nodecheck as nc_cli
from cbench.cli.main import cli

TARGETS = {"parallel": "/gpfs/zimafs1/cdmaestas", "node-local": "/tmp"}

TYPE_A = {"cpus": "4", "memtotal_kb": "7705324", "model": "Intel(R) N100"}
TYPE_B = {"cpus": "16", "memtotal_kb": "32599748", "model": "AMD Ryzen 7 5800H"}
TYPE_C = {"cpus": "8", "memtotal_kb": "16303040", "model": "Intel(R) i5-1240P"}


def _host_lines(host, facts, *, gpfs="gpfs", local="xfs", free_gpfs=5852028928, free_local=7938972,
                complete=True):
    lines = [f"{host}: {k}={v}" for k, v in facts.items()]
    lines += [
        f"{host}: target.node-local.fstype={local}",
        f"{host}: target.node-local.free_kb={free_local}",
        f"{host}: target.parallel.fstype={gpfs}",
        f"{host}: target.parallel.free_kb={free_gpfs}",
    ]
    if complete:
        lines.append(f"{host}: cbench_probe=ok")
    return lines


def _output(spec):
    """spec: {host: facts or (facts, kwargs)} -> pdsh-style stdout."""
    lines = []
    for host, item in spec.items():
        facts, kw = item if isinstance(item, tuple) else (item, {})
        lines += _host_lines(host, facts, **kw)
    return "\n".join(lines)


ZIMA_A = {f"zima{i}": TYPE_A for i in range(1, 5)}
ZIMA_ALL = {**ZIMA_A, "zimabg1": TYPE_B, "zimabg2": TYPE_B, "zimad": TYPE_C}


# ---------------------------------------------------------------------------
# probe script + transport
# ---------------------------------------------------------------------------

def test_probe_script_reports_targets_and_sentinel():
    s = nc.build_probe_script({"parallel": "/gpfs/my dir"})
    assert "target.parallel.fstype=" in s
    assert "'/gpfs/my dir'" in s  # paths are shell-quoted
    assert s.rstrip().endswith('echo "cbench_probe=ok"')


needs_base64 = pytest.mark.skipif(shutil.which("base64") is None, reason="base64 not installed")


@needs_base64
def test_remote_shell_command_round_trips_through_a_shell():
    script = "echo 'quotes \"and\" $dollars'\necho second\n"
    res = subprocess.run(nc.remote_shell_command(script), shell=True,  # noqa: S602
                         capture_output=True, text=True, check=True)
    assert res.stdout.splitlines() == ['quotes "and" $dollars', "second"]


@needs_base64
def test_exec_suffix_survives_argv_and_whitespace_resplitting():
    script = "echo hello world\n"
    argv = nc.exec_command_suffix(script)
    # pdsh may pass argv through, or join + re-split on whitespace: both must work
    assert " ".join(argv).split() == argv
    res = subprocess.run(argv, capture_output=True, text=True, check=True)
    assert res.stdout.strip() == "hello world"


def test_build_pdsh_argv_ssh():
    argv = nc.build_pdsh_argv("zima[1-4]", "echo x\n", rcmd="ssh", exec_cmd="", extraargs="-f 700")
    assert argv[:3] == ["pdsh", "-R", "ssh"]
    assert ["-f", "700"] == argv[argv.index("-f"):argv.index("-f") + 2]
    assert argv[argv.index("-w") + 1] == "zima[1-4]"
    assert argv[-1].startswith("sh -c ")


def test_build_pdsh_argv_exec_substitutes_template():
    argv = nc.build_pdsh_argv("zima[1-4]", "echo x\n", rcmd="exec",
                              exec_cmd="srun -N1 -n1 -w %h", extraargs="")
    assert argv[argv.index("-w") + 2:argv.index("-w") + 7] == ["srun", "-N1", "-n1", "-w", "%h"]
    assert argv[-3:-1] == ["sh", "-c"]


def test_build_pdsh_argv_exec_requires_percent_h():
    with pytest.raises(nc.NodecheckError, match="%h"):
        nc.build_pdsh_argv("zima1", "echo\n", rcmd="exec", exec_cmd="srun -N1", extraargs="")


def _fake_runner(stdout="", exc=None):
    def run(*a, **k):
        if exc:
            raise exc
        return SimpleNamespace(stdout=stdout, stderr="", returncode=0)
    return run


def test_check_pdsh_rcmd_accepts_installed_module():
    nc.check_pdsh_rcmd("exec", runner=_fake_runner(
        "pdsh-2.36 (+readline+debug)\nrcmd modules: ssh,exec (default: ssh)\n"))


def test_check_pdsh_rcmd_names_missing_package():
    with pytest.raises(nc.NodecheckError, match="pdsh-rcmd-exec"):
        nc.check_pdsh_rcmd("exec", runner=_fake_runner("rcmd modules: ssh (default: ssh)\n"))


def test_check_pdsh_rcmd_without_pdsh():
    with pytest.raises(nc.NodecheckError, match="remotecmd_method: ssh"):
        nc.check_pdsh_rcmd("ssh", runner=_fake_runner(exc=FileNotFoundError()))


# ---------------------------------------------------------------------------
# parsing + analysis
# ---------------------------------------------------------------------------

def test_parse_output_ignores_pdsh_diagnostics_and_keeps_equals_in_values():
    text = "\n".join([
        "zima1: cpus=4",
        "zima1: model=Foo CPU @ 2.0GHz rev=3",
        "zima1: cbench_probe=ok",
        "pdsh@zima1: zima2: ssh exited with exit code 255",
        "garbage line",
    ])
    facts = nc.parse_output(text)
    assert set(facts) == {"zima1"}
    assert facts["zima1"]["model"] == "Foo CPU @ 2.0GHz rev=3"
    assert facts["zima1"]["_complete"] == "1"


def test_homogeneous_type_a_passes():
    hosts = list(ZIMA_A)
    r = nc.analyze(hosts, nc.parse_output(_output(ZIMA_A)), TARGETS)
    assert r["verdict"]["ok"] and not r["verdict"]["heterogeneous"]
    assert r["aggregate"]["cpus"] == {"min": 4, "max": 4}
    t = r["aggregate"]["targets"]
    assert t["parallel"]["fstype"] == "gpfs" and t["parallel"]["shared"] is True
    assert t["node-local"]["fstype"] == "xfs" and t["node-local"]["shared"] is False


def test_memtotal_within_tolerance_is_homogeneous():
    spec = dict(ZIMA_A)
    spec["zima4"] = {**TYPE_A, "memtotal_kb": str(int(7705324 * 0.99))}  # 1% lower
    r = nc.analyze(list(spec), nc.parse_output(_output(spec)), TARGETS)
    assert r["verdict"]["ok"]


def test_memtotal_beyond_tolerance_is_heterogeneous():
    spec = dict(ZIMA_A)
    spec["zima4"] = {**TYPE_A, "memtotal_kb": str(int(7705324 * 0.97))}  # 3% lower
    r = nc.analyze(list(spec), nc.parse_output(_output(spec)), TARGETS)
    assert not r["verdict"]["ok"] and r["verdict"]["heterogeneous"]
    assert any("MemTotal differs" in e for e in r["verdict"]["errors"])


def test_whole_zima_is_heterogeneous_and_fails_by_default():
    r = nc.analyze(list(ZIMA_ALL), nc.parse_output(_output(ZIMA_ALL)), TARGETS)
    assert not r["verdict"]["ok"]
    cpu_err = next(e for e in r["verdict"]["errors"] if "CPU count differs" in e)
    assert "4: zima[1-4]" in cpu_err and "16: zimabg[1-2]" in cpu_err and "8: zimad" in cpu_err


def test_allow_heterogeneous_warns_and_reports_conservative_values():
    r = nc.analyze(list(ZIMA_ALL), nc.parse_output(_output(ZIMA_ALL)), TARGETS,
                   allow_heterogeneous=True)
    assert r["verdict"]["ok"] and r["verdict"]["heterogeneous"]
    agg = r["aggregate"]
    assert agg["cpus"]["min"] == 4
    assert agg["memtotal_kb"] == {"min": 7705324, "max": 32599748}
    msg = next(w for w in r["verdict"]["warnings"] if "conservative" in w)
    assert "max MemTotal (32599748 kB)" in msg and "min MemTotal (7705324 kB)" in msg


def test_cpu_model_mismatch_is_only_a_warning():
    spec = dict(ZIMA_A)
    spec["zima2"] = {**TYPE_A, "model": "Intel(R) N100 stepping 2"}
    r = nc.analyze(list(spec), nc.parse_output(_output(spec)), TARGETS)
    assert r["verdict"]["ok"]
    assert any("CPU model differs" in w for w in r["verdict"]["warnings"])


def test_unreachable_node_fails_and_is_named():
    spec = dict(ZIMA_A)
    spec["zima3"] = (TYPE_A, {"complete": False})  # probe output cut short
    hosts = list(ZIMA_A) + ["zima9"]  # zima9 never answered
    r = nc.analyze(hosts, nc.parse_output(_output(spec)), TARGETS)
    assert not r["verdict"]["ok"]
    err = next(e for e in r["verdict"]["errors"] if "unreachable" in e)
    assert "zima[3,9]" in err and "--ignore" in err
    assert r["responded"] == ["zima1", "zima2", "zima4"]


def test_missing_target_mount_fails():
    spec = dict(ZIMA_A)
    spec["zima2"] = (TYPE_A, {"gpfs": "MISSING", "free_gpfs": 0})
    r = nc.analyze(list(spec), nc.parse_output(_output(spec)), TARGETS)
    assert not r["verdict"]["ok"]
    assert any("'parallel'" in e and "missing on zima2" in e for e in r["verdict"]["errors"])


def test_unmounted_gpfs_shows_up_as_mixed_fstype():
    # mountpoint dir exists but GPFS isn't mounted -> it reports the root fs type
    spec = dict(ZIMA_A)
    spec["zima4"] = (TYPE_A, {"gpfs": "xfs"})
    r = nc.analyze(list(spec), nc.parse_output(_output(spec)), TARGETS)
    assert not r["verdict"]["ok"]
    assert any("mixed fstypes" in e for e in r["verdict"]["errors"])


def test_free_space_minimum_across_nodes():
    spec = dict(ZIMA_A)
    spec["zima2"] = (TYPE_A, {"free_local": 1000})
    r = nc.analyze(list(spec), nc.parse_output(_output(spec)), TARGETS)
    assert r["aggregate"]["targets"]["node-local"]["free_kb_min"] == 1000


def test_group_summary_collapses_identical_nodes():
    per_host = nc.parse_output(_output(ZIMA_ALL))
    rows = nc.group_summary(per_host, sorted(ZIMA_ALL), TARGETS)
    assert [r["hosts"] for r in rows] == ["zima[1-4]", "zimabg[1-2]", "zimad"]
    assert rows[0]["count"] == 4 and rows[0]["cpus"] == "4"
    assert rows[0]["targets"] == {"node-local": "xfs", "parallel": "gpfs"}


# ---------------------------------------------------------------------------
# facts file
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad", ["../escape", "a/b", "", "has space"])
def test_facts_path_rejects_bad_names(tmp_path, bad):
    with pytest.raises(nc.NodecheckError):
        nc.facts_path(tmp_path, bad)


def _facts(tmp_path, spec, *, allow=False, now=None):
    per_host = nc.parse_output(_output(spec))
    result = nc.analyze(list(spec), per_host, TARGETS, allow_heterogeneous=allow)
    facts = nc.build_facts(name="zima", nodelist="x", ignored=[], transport={"method": "pdsh"},
                           allow_heterogeneous=allow, per_host=per_host, result=result, now=now)
    path = nc.facts_path(tmp_path, "zima")
    nc.write_facts(path, facts)
    return path, facts


def test_facts_round_trip(tmp_path):
    path, facts = _facts(tmp_path, ZIMA_A)
    assert path == (tmp_path / "nodefacts" / "zima.json").resolve()
    loaded, warnings = nc.load_facts(tmp_path, "zima")
    assert loaded["aggregate"] == facts["aggregate"]
    assert loaded["hosts"] == sorted(ZIMA_A)
    assert "_complete" not in json.dumps(loaded)
    assert warnings == []


def test_load_facts_refuses_failed_check(tmp_path):
    _facts(tmp_path, ZIMA_ALL)  # heterogeneous, not allowed -> failed verdict
    with pytest.raises(nc.NodecheckError, match="FAILED"):
        nc.load_facts(tmp_path, "zima")


def test_load_facts_warns_when_stale(tmp_path):
    old = datetime.now(timezone.utc) - timedelta(days=45)
    _facts(tmp_path, ZIMA_A, now=old)
    _, warnings = nc.load_facts(tmp_path, "zima")
    assert warnings and "45 days old" in warnings[0]


def test_load_facts_missing_and_bad_schema(tmp_path):
    with pytest.raises(nc.NodecheckError, match="run `cbench nodecheck`"):
        nc.load_facts(tmp_path, "zima")
    path, facts = _facts(tmp_path, ZIMA_A)
    path.write_text(json.dumps({**facts, "schema_version": 99}))
    with pytest.raises(nc.NodecheckError, match="schema_version"):
        nc.load_facts(tmp_path, "zima")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@pytest.fixture
def cli_env(tmp_path, monkeypatch):
    cfg = tmp_path / "cluster.yaml"
    cfg.write_text(
        "cluster_name: zima\n"
        "io_targets:\n"
        "  parallel: /gpfs/zimafs1/cdmaestas\n"
        "  node-local: /tmp\n"
    )
    monkeypatch.setattr(nc_cli.console, "width", 300)
    monkeypatch.setattr(nc, "check_pdsh_rcmd", lambda rcmd: None)
    calls = {}

    def use_output(spec):
        def fake_run_pdsh(argv):
            calls["argv"] = argv
            return _output({h: v for h, v in spec.items()}), ""
        monkeypatch.setattr(nc, "run_pdsh", fake_run_pdsh)

    return SimpleNamespace(tmp=tmp_path, cfg=str(cfg), use_output=use_output, calls=calls)


def _invoke(env, *args):
    return CliRunner().invoke(cli, ["nodecheck", *args, "--cbenchtest", str(env.tmp),
                                    "--config", env.cfg])


def test_cli_homogeneous_pool_writes_facts(cli_env):
    cli_env.use_output(ZIMA_A)
    res = _invoke(cli_env, "--nodelist", "zima[1-4]")
    assert res.exit_code == 0, res.output
    assert "nodecheck PASSED" in res.output and "zima[1-4]" in res.output
    facts = json.loads((cli_env.tmp / "nodefacts" / "zima.json").read_text())
    assert facts["verdict"]["ok"] and facts["hosts"] == sorted(ZIMA_A)
    assert cli_env.calls["argv"][cli_env.calls["argv"].index("-w") + 1] == "zima[1-4]"


def test_cli_heterogeneous_pool_exits_nonzero(cli_env):
    cli_env.use_output(ZIMA_ALL)
    res = _invoke(cli_env, "--nodelist", "zima[1-4],zimabg[1-2],zimad")
    assert res.exit_code == 1
    assert "CPU count differs" in res.output and "nodecheck FAILED" in res.output


def test_cli_allow_heterogeneous_passes_with_warning(cli_env):
    cli_env.use_output(ZIMA_ALL)
    res = _invoke(cli_env, "--nodelist", "zima[1-4],zimabg[1-2],zimad", "--allow-heterogeneous")
    assert res.exit_code == 0, res.output
    assert "conservative values" in res.output


def test_cli_ignore_excludes_nodes(cli_env):
    cli_env.use_output(ZIMA_A)
    res = _invoke(cli_env, "--nodelist", "zima[1-4],zimad", "--ignore", "zimad")
    assert res.exit_code == 0, res.output
    facts = json.loads((cli_env.tmp / "nodefacts" / "zima.json").read_text())
    assert facts["ignored"] == "zimad"


def test_cli_requires_exactly_one_node_source(cli_env):
    res = _invoke(cli_env)
    assert res.exit_code != 0 and "exactly one of --nodelist or --partition" in res.output
    res = _invoke(cli_env, "--nodelist", "zima1", "--partition", "debug")
    assert res.exit_code != 0
