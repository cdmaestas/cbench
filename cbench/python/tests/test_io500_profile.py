"""The io500 profile: builder, template, node-count sweep and parser fixes."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from cbench import profiles
from cbench.builders import BuildConfig, get_builder
from cbench.cli.main import cli
from cbench.config import ConfigError, load_config
from cbench.parsers import get_parser
from cbench.parsers.io500 import Io500Parser

GPFS = "/gpfs/zimafs1/cdmaestas"

# Current io500 output (src/main.c): "[SCORE ]" with a space, "kiops" lowercase,
# " [INVALID]" appended when the run breaks the rules (e.g. stonewall < 300 s)
_IO500 = """\
Cbench io500: stonewall=60 datadir=/gpfs/zimafs1/cdmaestas/io500.123
IO500 version io500-sc24_v1-1-g34a5965 (standard)
[RESULT]       ior-easy-write        0.081234 GiB/s : time 61.234 seconds [INVALID]
[RESULT]    mdtest-easy-write        1.234567 kIOPS : time 60.123 seconds [INVALID]
[      ]            timestamp        0.000000 kIOPS : time 0.001 seconds
[RESULT]       ior-hard-write        0.012345 GiB/s : time 60.456 seconds [INVALID]
[RESULT]    mdtest-hard-write        0.543210 kIOPS : time 60.789 seconds [INVALID]
[RESULT]                 find       12.345678 kIOPS : time 1.234 seconds
[RESULT]        ior-easy-read        2.345678 GiB/s : time 2.345 seconds
[RESULT]     mdtest-easy-stat       45.678901 kIOPS : time 1.456 seconds
[RESULT]        ior-hard-read        0.234567 GiB/s : time 3.456 seconds
[RESULT]     mdtest-hard-stat       34.567890 kIOPS : time 1.567 seconds
[RESULT]   mdtest-easy-delete        2.345678 kIOPS : time 2.678 seconds
[RESULT]     mdtest-hard-read        5.678901 kIOPS : time 1.789 seconds
[RESULT]   mdtest-hard-delete        1.234567 kIOPS : time 2.890 seconds
[SCORE ] Bandwidth 0.123457 GiB/s : IOPS 4.567890 kiops : TOTAL 0.750878 [INVALID]
[SCOREX] Bandwidth 0.130000 GiB/s : IOPS 4.600000 kiops : TOTAL 0.773305 [INVALID]
"""


# ---------------------------------------------------------------------------
# parser
# ---------------------------------------------------------------------------

def test_parser_reads_current_score_line():
    r = Io500Parser().parse(_IO500)
    assert r.status == "PASSED"
    m = r.metrics
    assert m["bandwidth_GiB_s"] == pytest.approx(0.123457)   # [SCORE ], not [SCOREX]
    assert m["iops_kIOPS"] == pytest.approx(4.567890)
    assert m["score"] == pytest.approx(0.750878)
    assert m["ior_easy_write_GiB_s"] == pytest.approx(0.081234)
    assert m["mdtest_hard_delete_kIOPS"] == pytest.approx(1.234567)
    assert "[INVALID]" in r.status_detail


def test_parser_valid_run_has_no_invalid_note():
    r = Io500Parser().parse(_IO500.replace(" [INVALID]", ""))
    assert r.status == "PASSED" and r.status_detail == ""


def test_parser_still_reads_old_score_format():
    old = "[SCORE] Bandwidth 1.234 GiB/s : IOPS 12345.67 kIOPS : TOTAL 123.456\n"
    assert Io500Parser().parse(old).metrics["score"] == pytest.approx(123.456)


def test_profile_job_name_resolves():
    assert isinstance(get_parser("io500-parallel"), Io500Parser)


# ---------------------------------------------------------------------------
# builder + config
# ---------------------------------------------------------------------------

def test_io500_builder_runs_prepare_and_installs_binary(tmp_path, monkeypatch):
    import cbench.builders.io500 as mod
    calls = []
    monkeypatch.setattr(mod, "run", lambda cmd, **kw: calls.append((cmd, kw["env"]["CC"],
                                                                      kw["env"]["NPROC"])))
    monkeypatch.setattr(mod, "install_bins", lambda src, dst, names, **kw: names)
    out = get_builder("io500").build(tmp_path, tmp_path / "pfx", BuildConfig(mpicc="mpicc", jobs=8))
    assert calls == [(["./prepare.sh"], "mpicc", "8")] and out == ["io500"]


def test_io500_stonewall_config(tmp_path):
    f = tmp_path / "cluster.yaml"
    f.write_text("io500_stonewall_s: 60\n")
    assert load_config(f).io500_stonewall_s == 60
    f.write_text("io500_stonewall_s: 0\n")
    with pytest.raises(ConfigError):
        load_config(f)


# ---------------------------------------------------------------------------
# gen-jobs --profile io500
# ---------------------------------------------------------------------------

def _facts(cpus=4):
    return {"schema_version": 2, "name": "typeA",
            "created": datetime.now(timezone.utc).isoformat(), "allow_heterogeneous": False,
            "verdict": {"ok": True, "heterogeneous": False, "errors": [], "warnings": []},
            "aggregate": {"cpus": {"min": cpus, "max": cpus}, "cores": {"min": cpus, "max": cpus},
                          "memtotal_kb": {"min": 7705320, "max": 7706776}, "models": [],
                          "targets": {"parallel": {"path": GPFS, "fstype": "gpfs",
                                                   "shared": True, "free_kb_min": 10**12}}}}


@pytest.fixture
def genv(tmp_path):
    def run(*args, max_nodes=4, cfg_extra="", cpus=4):
        cfg = tmp_path / "cluster.yaml"
        cfg.write_text(f"cluster_name: zima\nmax_nodes: {max_nodes}\nprocs_per_node: 4\n"
                       f"batch_method: slurm\nio_targets:\n  parallel: {GPFS}\n" + cfg_extra)
        (tmp_path / "nodefacts").mkdir(exist_ok=True)
        (tmp_path / "nodefacts" / "typeA.json").write_text(json.dumps(_facts(cpus)))
        return CliRunner().invoke(cli, ["gen-jobs", "--profile", "io500", "--ident", "c1",
                                        "--run-type", "batch", "--config", str(cfg),
                                        "--cbenchtest", str(tmp_path), "--nodefacts", "typeA",
                                        *args])

    def jobs():
        return sorted((p.name for p in (tmp_path / "io500" / "c1").iterdir()),
                      key=lambda n: int(n.rsplit("-", 1)[1]))

    def script(job):
        return next((tmp_path / "io500" / "c1" / job).glob("*.slurm")).read_text()

    return SimpleNamespace(tmp=tmp_path, run=run, jobs=jobs, script=script)


def test_io500_profile_definition():
    p = profiles.get_profile("io500")
    assert profiles.select_groups(p, ()) == ["parallel"]
    assert [m.benchmark for m in p.groups["parallel"].members] == ["io500"]


def test_io500_one_job_per_node_count_at_io_threads(genv):
    res = genv.run(max_nodes=6)
    assert res.exit_code == 0, res.output
    # 1, 2, 4 nodes (powers of two) and max_nodes (6), all at 4 ppn
    assert genv.jobs() == ["io500-parallel-4ppn-4", "io500-parallel-4ppn-8",
                           "io500-parallel-4ppn-16", "io500-parallel-4ppn-24"]
    s = genv.script("io500-parallel-4ppn-8")
    assert "-N 2 --ntasks-per-node 4" in s
    assert re.search(r'CMD=".*-np 8 \$IO500 io500.ini"', s)


def test_io500_sweep_respects_maxprocs_and_thread_cap(genv):
    res = genv.run("--maxprocs", "8", cfg_extra="io_threads_max: 2\n")
    assert res.exit_code == 0, res.output
    assert genv.jobs() == ["io500-parallel-2ppn-2", "io500-parallel-2ppn-4", "io500-parallel-2ppn-8"]


def test_io500_ini_datadir_and_stonewall(genv):
    res = genv.run("--io500-stonewall", "60")
    assert res.exit_code == 0, res.output
    s = genv.script("io500-parallel-4ppn-4")
    assert f'IO_TARGET_DIR="{GPFS}"' in s and 'DATADIR="$IO_TARGET_DIR/io500.$JOBID"' in s
    assert "stonewall-time = 60\n" in s and "datadir = $DATADIR\n" in s
    assert 'rm -rf "$DATADIR"' in s
    assert not re.findall(r"\b[A-Z][A-Z0-9_]*_HERE\w*", s)


def test_io500_default_stonewall_is_rules_compliant(genv):
    res = genv.run()
    assert res.exit_code == 0, res.output
    assert "stonewall-time = 300\n" in genv.script("io500-parallel-4ppn-4")


def test_io500_without_parallel_target_is_skipped(genv, tmp_path):
    cfg = tmp_path / "cluster.yaml"
    cfg.write_text("cluster_name: zima\nmax_nodes: 2\nprocs_per_node: 4\nbatch_method: slurm\n")
    res = CliRunner().invoke(cli, ["gen-jobs", "--profile", "io500", "--ident", "c9",
                                   "--config", str(cfg), "--cbenchtest", str(tmp_path)])
    assert res.exit_code != 0 and "skipping group 'parallel'" in res.output
