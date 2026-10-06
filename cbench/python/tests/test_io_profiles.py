"""IO profiles (cbench.profiles), the shared IO thread rule (iosizing.io_threads)
and nodecheck physical cores (facts schema v2).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from cbench import iosizing, nodecheck, profiles
from cbench.cli.main import cli
from cbench.config import ClusterConfig, ConfigError, load_config
from cbench.parsers import get_parser
from cbench.parsers.bonnie import BonnieParser
from cbench.parsers.fio import FioParser
from cbench.parsers.ior import IorParser
from cbench.parsers.mdtest import MdtestParser

GPFS = "/gpfs/zimafs1/cdmaestas"


# ---------------------------------------------------------------------------
# io_threads
# ---------------------------------------------------------------------------

def _nv(cpus=8, cores=4):
    return iosizing.NodeValues(cpus=cpus, cores=cores, mem_io_kb=1, mem_nonio_kb=1)


@pytest.mark.parametrize("cfg_kw, expected", [
    ({}, 8),                                                   # all logical CPUs, no cap
    ({"io_threads_max": 6}, 6),                                # explicit cap
    ({"io_threads_max": 64}, 8),                               # cap above the count is a no-op
    ({"io_threads_basis": "physical"}, 4),                     # physical cores
    ({"io_threads_basis": "physical", "io_threads_max": 2}, 2),
])
def test_io_threads(cfg_kw, expected):
    assert iosizing.io_threads(_nv(), ClusterConfig(**cfg_kw)) == expected


def test_io_threads_physical_falls_back_to_logical_with_warning():
    nv = _nv(cores=None)  # schema v1 facts, or cluster.yaml values
    assert iosizing.io_threads(nv, ClusterConfig(io_threads_basis="physical")) == 8
    assert any("physical cores are unknown" in w for w in nv.warnings)
    iosizing.io_threads(nv, ClusterConfig(io_threads_basis="physical"))
    assert len(nv.warnings) == 1  # warned once


def test_io_threads_needs_cpus():
    with pytest.raises(iosizing.IOSizingError):
        iosizing.io_threads(_nv(cpus=None), ClusterConfig())


@pytest.mark.parametrize("bad", ["io_threads_max: 0", "io_threads_basis: smt"])
def test_io_threads_config_validated(tmp_path, bad):
    f = tmp_path / "cluster.yaml"
    f.write_text(bad + "\n")
    with pytest.raises(ConfigError):
        load_config(f)


def test_io_threads_config_loads(tmp_path):
    f = tmp_path / "cluster.yaml"
    f.write_text("io_threads_max: 32\nio_threads_basis: physical\n")
    cfg = load_config(f)
    assert (cfg.io_threads_max, cfg.io_threads_basis) == (32, "physical")
    assert ClusterConfig().io_threads_max is None and ClusterConfig().io_threads_basis == "logical"


# ---------------------------------------------------------------------------
# nodecheck: physical cores, schema v2
# ---------------------------------------------------------------------------

def test_probe_collects_physical_cores():
    script = nodecheck.build_probe_script({})
    assert "cores=$(awk" in script and "core id" in script and "tr -d ' '" in script


def _host(cpus, cores, mem=7705320):
    return {"cpus": str(cpus), "cores": str(cores), "memtotal_kb": str(mem), "model": "x",
            "_complete": "1"}


def test_analyze_aggregates_cores():
    per = {"n1": _host(8, 4), "n2": _host(8, 4)}
    res = nodecheck.analyze(["n1", "n2"], per, {}, allow_heterogeneous=False)
    assert res["aggregate"]["cores"] == {"min": 4, "max": 4} and res["verdict"]["ok"]


def test_analyze_flags_smt_mismatch():
    per = {"n1": _host(8, 4), "n2": _host(8, 8)}  # same logical count, SMT off on n2
    res = nodecheck.analyze(["n1", "n2"], per, {}, allow_heterogeneous=False)
    assert not res["verdict"]["ok"]
    assert any("physical core count differs" in e for e in res["verdict"]["errors"])


def test_analyze_cores_unknown_when_any_host_lacks_them():
    per = {"n1": _host(8, 4), "n2": _host(8, 0)}
    res = nodecheck.analyze(["n1", "n2"], per, {}, allow_heterogeneous=False)
    assert res["aggregate"]["cores"] is None and res["verdict"]["ok"]


def _facts(version=2, cores=2, cpus=4):
    agg = {"cpus": {"min": cpus, "max": cpus}, "memtotal_kb": {"min": 7705320, "max": 7706776},
           "models": [], "targets": {"node-local": {"path": "/tmp", "fstype": "xfs",
                                                    "shared": False, "free_kb_min": 10**9},
                                     "parallel": {"path": GPFS, "fstype": "gpfs",
                                                  "shared": True, "free_kb_min": 10**12}}}
    if version >= 2:
        agg["cores"] = {"min": cores, "max": cores}
    return {"schema_version": version, "name": "typeA",
            "created": datetime.now(timezone.utc).isoformat(), "allow_heterogeneous": False,
            "verdict": {"ok": True, "heterogeneous": False, "errors": [], "warnings": []},
            "aggregate": agg}


def test_load_facts_accepts_v1_and_v2(tmp_path):
    for v in (1, 2):
        path = tmp_path / f"v{v}.json"
        path.write_text(json.dumps(_facts(version=v)))
        facts, _ = nodecheck.load_facts(tmp_path, str(path))
        nv = iosizing.resolve_node_values(ClusterConfig(), facts)
        assert nv.cores == (2 if v == 2 else None)


# ---------------------------------------------------------------------------
# profile definitions + parser resolution
# ---------------------------------------------------------------------------

def test_select_groups():
    p = profiles.get_profile("io-default")
    assert profiles.select_groups(p, ()) == ["node-local"]          # user: default is local
    assert profiles.select_groups(p, ("all",)) == ["node-local", "parallel", "gpfs", "gpfs-mpi",
                                                  "gpfs-node"]
    assert profiles.select_groups(p, ("parallel", "parallel")) == ["parallel"]
    with pytest.raises(profiles.ProfileError):
        profiles.select_groups(p, ("bogus",))
    with pytest.raises(profiles.ProfileError):
        profiles.get_profile("nope")


def test_io_default_composition():
    p = profiles.get_profile("io-default")
    names = {g: [m.benchmark for m in grp.members] for g, grp in p.groups.items()}
    assert names["node-local"] == ["fio", "bonnie", "iozone"]
    assert names["parallel"] == ["ior1mNtoN", "mdtest"]
    assert names["gpfs"] == ["gpfsperf"]


@pytest.mark.parametrize("bench, cls", [
    ("fio-local", FioParser), ("bonnie-local", BonnieParser),
    ("ior1mNtoN-parallel", IorParser), ("mdtest-parallel", MdtestParser),
])
def test_group_qualified_names_resolve(bench, cls):
    assert isinstance(get_parser(bench), cls)


def test_unknown_qualified_name_still_none():
    assert get_parser("nosuch-local") is None


# ---------------------------------------------------------------------------
# gen-jobs --profile
# ---------------------------------------------------------------------------

@pytest.fixture
def genv(tmp_path):
    def run(*args, targets="  node-local: /tmp\n  parallel: " + GPFS + "\n", cfg_extra="",
            facts=None):
        cfg = tmp_path / "cluster.yaml"
        cfg.write_text("cluster_name: zima\nmax_nodes: 2\nprocs_per_node: 4\nbatch_method: slurm\n"
                       "io_targets:\n" + targets + cfg_extra)
        (tmp_path / "nodefacts").mkdir(exist_ok=True)
        (tmp_path / "nodefacts" / "typeA.json").write_text(json.dumps(facts or _facts()))
        return CliRunner().invoke(cli, ["gen-jobs", "--ident", "p1", "--run-type", "batch",
                                        "--config", str(cfg), "--cbenchtest", str(tmp_path),
                                        "--nodefacts", "typeA", *args])

    def jobs():
        d = tmp_path / "io-default" / "p1"
        return sorted(p.name for p in d.iterdir()) if d.exists() else []

    def script(job):
        return next((tmp_path / "io-default" / "p1" / job).glob("*.slurm")).read_text()

    return SimpleNamespace(tmp=tmp_path, run=run, jobs=jobs, script=script)


def test_profile_default_is_node_local(genv):
    res = genv.run("--profile", "io-default")
    assert res.exit_code == 0, res.output
    assert genv.jobs() == ["bonnie-local-4ppn-4", "fio-local-4ppn-4", "iozone-local-4ppn-4"]
    s = genv.script("fio-local-4ppn-4")
    assert 'Cbench benchmark: fio-local"' in s and "/io-default/p1/fio-local-4ppn-4" in s
    assert "numjobs=4\n" in s


def test_profile_all_groups_skips_unconfigured_targets(genv):
    # facts say the parallel target is xfs here, and there is no io_targets.gpfs
    facts = _facts()
    facts["aggregate"]["targets"]["parallel"]["fstype"] = "xfs"
    res = genv.run("--profile", "io-default", "--group", "all", facts=facts)
    assert res.exit_code == 0, res.output
    assert "skipping group 'gpfs'" in res.output and "is not GPFS" in res.output
    assert "generating groups node-local, parallel" in res.output
    jobs = genv.jobs()
    assert "ior1mNtoN-parallel-4ppn-4" in jobs and "mdtest-parallel-4ppn-4" in jobs
    assert not any("-8ppn-" in j for j in jobs)   # top ppn = io_threads (4)


def test_profile_group_without_target_is_an_error_when_only_one(genv):
    res = genv.run("--profile", "io-default", "--group", "parallel", targets="  node-local: /tmp\n")
    assert res.exit_code != 0 and "nothing to generate" in res.output


def test_profile_threads_follow_cap_and_basis(genv):
    res = genv.run("--profile", "io-default", cfg_extra="io_threads_basis: physical\n")
    assert res.exit_code == 0, res.output
    # facts: 2 physical cores -> 2 threads, and the job name says so
    assert "numjobs=2\n" in genv.script("fio-local-2ppn-2")
    assert "instances=2\n" in genv.script("bonnie-local-2ppn-2")
    res = genv.run("--profile", "io-default", cfg_extra="io_threads_max: 1\n")
    assert "numjobs=1\n" in genv.script("fio-local-1ppn-1")


def test_profile_and_testset_are_exclusive(genv):
    assert genv.run("--profile", "io-default", "--testset", "io").exit_code != 0
    res = CliRunner().invoke(cli, ["gen-jobs", "--testset", "io", "--group", "x", "--ident", "p"])
    assert res.exit_code != 0 and "--group only applies" in res.output


def test_profile_jobs_parse_as_one_testset(genv):
    genv.run("--profile", "io-default")
    job = genv.tmp / "io-default" / "p1" / "fio-local-4ppn-4"
    (job / "fio-local-4ppn-4.o1").write_text(
        "Cbench fio: profile=general seq_bs=4m numjobs=4 size=256m direct=1 runtime=300s\n"
        "rand_rw: (groupid=0, jobs=4): err= 0: pid=2: Sat Oct  3 21:09:00 2026\n"
        "  read: IOPS=1460, BW=5857KiB/s (5998kB/s)(1716MiB/300003msec)\n"
        "Cbench fio: finished\n")
    res = CliRunner().invoke(cli, ["parse", "--testset", "io-default", "--ident", "p1", "--no-db",
                                   "--cbenchtest", str(genv.tmp)])
    assert res.exit_code == 0, res.output
    assert "fio-local-4ppn-4" in res.output and "PASSED" in res.output


def test_snb_detect_physical_cores(tmp_path):
    from cbench.cli import snb
    lines = []
    for cpu in range(8):  # 1 socket, 4 cores, SMT 2
        lines += [f"processor\t: {cpu}", "physical id\t: 0", f"core id\t\t: {cpu % 4}", ""]
    f = tmp_path / "cpuinfo"
    f.write_text("\n".join(lines))
    assert snb._detect_physical_cores(f) == 4
    f.write_text("processor\t: 0\nprocessor\t: 1\n")      # no core ids (some ARM/VMs)
    assert snb._detect_physical_cores(f) == 0
    assert snb._detect_physical_cores(tmp_path / "missing") == 0


def test_genjobs_fio_runtime_flag_overrides_config(genv):
    res = genv.run("--profile", "io-default", "--fio-runtime", "30",
                   cfg_extra="fio_runtime_s: 600\n")
    assert res.exit_code == 0, res.output
    assert "runtime=30\n" in genv.script("fio-local-4ppn-4")


def test_interactive_header_names_the_sh_script(genv):
    res = genv.run("--profile", "io-default", "--run-type", "both")
    assert res.exit_code == 0, res.output
    job = genv.tmp / "io-default" / "p1" / "fio-local-4ppn-4"
    assert "fio-local-4ppn-4/fio-local-4ppn-4.sh" in (job / "fio-local-4ppn-4.sh").read_text()
    assert "fio-local-4ppn-4/fio-local-4ppn-4.slurm" in (job / "fio-local-4ppn-4.slurm").read_text()


def test_single_node_jobs_request_their_thread_count(genv):
    """fio/bonnie run T threads on 1 node: the job name and the batch request
    say T, not 1 (a 1-task Slurm allocation can pin a 4-thread job to 1 core)."""
    res = genv.run("--profile", "io-default")
    assert res.exit_code == 0, res.output
    assert genv.jobs() == ["bonnie-local-4ppn-4", "fio-local-4ppn-4", "iozone-local-4ppn-4"]
    s = genv.script("fio-local-4ppn-4")
    assert "--ntasks-per-node=4" in s or "--ntasks-per-node 4" in s
    assert "-N 1" in s or "--nodes=1" in s or "-N1" in s


def test_rendered_profile_scripts_pass_shellcheck(genv):
    """Job scripts the Python toolchain renders must have no shellcheck errors
    (warnings from the shared legacy headers are tolerated)."""
    import shutil
    import subprocess
    if shutil.which("shellcheck") is None:
        pytest.skip("shellcheck not installed")
    res = genv.run("--profile", "io-default", "--group", "all", "--run-type", "both")
    assert res.exit_code == 0, res.output
    scripts = sorted((genv.tmp / "io-default" / "p1").glob("*/*.s*"))
    assert scripts
    for script in scripts:
        r = subprocess.run(["shellcheck", "-S", "error", "-s", "bash", str(script)],
                           capture_output=True, text=True)
        assert r.returncode == 0, f"{script.name}:\n{r.stdout}"
