"""Tests for node-aware IO sizing (cbench.iosizing) and its gen-jobs wiring.

Numbers are zima's real type-A nodes (zima[1-4]): 4 CPUs, MemTotal
7705320-7706776 kB, /tmp xfs with 7606080 kB free, GPFS with ~5.4 PB free.
"""

import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from cbench import iosizing
from cbench.cli.main import cli
from cbench.config import ClusterConfig

GPFS = "/gpfs/zimafs1/cdmaestas"


def _facts(*, mem_min=7705320, mem_max=7706776, cpus=4, local_free=7606080,
           hetero=False, targets=None):
    return {
        "schema_version": 1,
        "name": "typeA",
        "created": datetime.now(timezone.utc).isoformat(),
        "allow_heterogeneous": hetero,
        "verdict": {"ok": True, "heterogeneous": hetero, "errors": [], "warnings": []},
        "aggregate": {
            "cpus": {"min": cpus, "max": cpus},
            "memtotal_kb": {"min": mem_min, "max": mem_max},
            "models": ["Intel(R) Celeron(R) CPU N3450 @ 1.10GHz"],
            "targets": targets if targets is not None else {
                "parallel": {"path": GPFS, "fstype": "gpfs", "shared": True,
                             "free_kb_min": 5852028928},
                "node-local": {"path": "/tmp", "fstype": "xfs", "shared": False,
                               "free_kb_min": local_free},
            },
        },
    }


def _cfg(**kw):
    cfg = ClusterConfig(io_targets={"parallel": GPFS, "node-local": "/tmp"}, **kw)
    return cfg


# ---------------------------------------------------------------------------
# resolve_node_values
# ---------------------------------------------------------------------------

def test_facts_give_max_mem_for_io_and_min_for_nonio():
    nv = iosizing.resolve_node_values(_cfg(), _facts())
    assert nv.mem_io_kb == 7706776 and nv.mem_nonio_kb == 7705320 and nv.cpus == 4
    assert nv.source == "nodefacts:typeA"
    assert nv.targets["parallel"]["shared"] is True


def test_without_facts_only_explicit_config_counts():
    assert iosizing.resolve_node_values(_cfg()).mem_io_kb is None  # 2048 MB is just a default
    cfg = _cfg(memory_per_node_mb=7524, procs_per_node=4)
    cfg.explicit_keys = frozenset({"memory_per_node_mb", "procs_per_node"})
    nv = iosizing.resolve_node_values(cfg)
    assert nv.mem_io_kb == 7524 * 1024 and nv.cpus == 4 and nv.source == "cluster.yaml"
    assert nv.targets["node-local"]["free_kb_min"] is None  # no cap without facts


def test_config_decides_target_paths_and_stale_facts_paths_warn():
    cfg = ClusterConfig(io_targets={"parallel": "/gpfs/other", "node-local": "/tmp", "x": "/x"})
    nv = iosizing.resolve_node_values(cfg, _facts())
    assert nv.targets["parallel"] == {"path": "/gpfs/other", "free_kb_min": None,
                                      "shared": None, "fstype": None}
    assert nv.targets["node-local"]["free_kb_min"] == 7606080
    assert any("probed /gpfs/zimafs1" in w for w in nv.warnings)
    assert any("'x' was not probed" in w for w in nv.warnings)


def test_heterogeneous_facts_warn_about_conservative_values():
    nv = iosizing.resolve_node_values(_cfg(), _facts(mem_max=15991676, hetero=True))
    assert nv.mem_io_kb == 15991676
    assert any("heterogeneous" in w for w in nv.warnings)


# ---------------------------------------------------------------------------
# IOR
# ---------------------------------------------------------------------------

def _ior(nv, ppn, np_):
    return iosizing.ior_tokens(nv, ppn=ppn, numprocs=np_, testset="io", benchmark="ior1mNtoN")


def test_ior_blocksize_rounds_up_to_multiple_of_transfer():
    nv = iosizing.resolve_node_values(_cfg(), _facts())
    t = _ior(nv, 4, 4)
    # 2 * 7526.1 MiB / 4 ranks = 3763.1 -> next multiple of 128m = 3840m
    assert t["IOR_BLOCKSIZE"] == "3840m"
    assert t["IO_CAVEAT"] == ""
    assert t["TESTDIR"] == GPFS and t["IO_TARGET_DIR"] == GPFS
    assert int(t["IO_REQUIRED_KB"]) == 3840 * 4 * 1024  # shared fs: whole job


def test_ior_each_node_writes_at_least_twice_ram():
    nv = iosizing.resolve_node_values(_cfg(), _facts())
    for ppn in (1, 2, 3, 4):
        b = int(_ior(nv, ppn, ppn)["IOR_BLOCKSIZE"][:-1])
        assert b % 128 == 0
        assert b * ppn * 1024 >= 2 * 7706776


def test_ior_capped_to_free_space_with_caveat():
    targets = {"parallel": {"path": GPFS, "fstype": "gpfs", "shared": True, "free_kb_min": 10_000_000}}
    nv = iosizing.resolve_node_values(ClusterConfig(io_targets={"parallel": GPFS}),
                                      _facts(targets=targets))
    t = _ior(nv, 4, 8)  # 2 nodes x 4 ppn on a shared fs
    b = int(t["IOR_BLOCKSIZE"][:-1])
    assert b % 128 == 0 and int(t["IO_REQUIRED_KB"]) <= 9_000_000
    assert "capped" in t["IO_CAVEAT"] and "cache-influenced" in t["IO_CAVEAT"]


def test_ior_requires_memory():
    with pytest.raises(iosizing.IOSizingError, match="--nodefacts"):
        _ior(iosizing.resolve_node_values(_cfg()), 4, 4)


# ---------------------------------------------------------------------------
# bonnie
# ---------------------------------------------------------------------------

def test_bonnie_uncapped_splits_2x_ram_over_three_instances():
    nv = iosizing.resolve_node_values(_cfg(), _facts(local_free=100_000_000))
    t = iosizing.bonnie_tokens(nv, testset="iometadata", benchmark="bonnie")
    assert t["BONNIE_SIZE_MB"] == "5018"   # ceil(2 * 7526.1 / 3): IO rounds up
    assert t["BONNIE_RAM_MB"] == "2508"    # floor(7526.1 / 3): memory rounds down
    assert int(t["BONNIE_SIZE_MB"]) >= 2 * int(t["BONNIE_RAM_MB"])  # bonnie++ requires it
    assert t["IO_CAVEAT"] == "" and t["IO_TARGET_DIR"] == "/tmp"


def test_bonnie_capped_on_zima_type_a_tmp():
    # zima's real case: /tmp has 7.25 GiB free, 2x RAM needs 14.7 GiB
    nv = iosizing.resolve_node_values(_cfg(), _facts())
    t = iosizing.bonnie_tokens(nv, testset="iometadata", benchmark="bonnie")
    size, ram = int(t["BONNIE_SIZE_MB"]), int(t["BONNIE_RAM_MB"])
    assert int(t["IO_REQUIRED_KB"]) <= 0.9 * 7606080
    assert size >= 2 * ram
    assert "capped" in t["IO_CAVEAT"]
    assert not set('"$`\\') & set(t["IO_CAVEAT"])  # safe inside a double-quoted bash string


# ---------------------------------------------------------------------------
# misc rules
# ---------------------------------------------------------------------------

def test_which_benchmarks_are_sized():
    assert iosizing.needs_io_sizing("io", "ior1mNtoN")
    assert iosizing.needs_io_sizing("iometadata", "bonnie")
    assert not iosizing.needs_io_sizing("iosanity", "ior1mNtoN")  # sanity stays small
    assert not iosizing.needs_io_sizing("iometadata", "mdtest")
    assert not iosizing.needs_io_sizing("iometadata", "fileop")


@pytest.mark.parametrize("configured,ppn_cfg,cpus,expected", [
    ([1, 2, 4, 8], 8, 4, [1, 2, 4]),      # drop levels above the real CPU count
    ([1, 2, 4, 8], 8, 6, [1, 2, 4, 6]),   # measured count replaces procs_per_node
    ([1, 2, 4, 16], 16, 32, [1, 2, 4, 32]),
])
def test_metadata_ppn_levels(configured, ppn_cfg, cpus, expected):
    assert iosizing.ppn_levels_for_metadata(configured, ppn_cfg, cpus) == expected


# ---------------------------------------------------------------------------
# runtime preflight (bash)
# ---------------------------------------------------------------------------

def _preflight_fn() -> str:
    from cbench import templates
    text = (templates._templates_dir() / "common_header.in").read_text()
    m = re.search(r"^cbench_io_preflight\(\)\n\{.*?^\}", text, re.S | re.M)
    assert m, "cbench_io_preflight not found in common_header.in"
    return m.group(0)


def _run_preflight(tmp_path, need_kb, caveat=""):
    script = (
        'cbench_echo() { echo "$@"; }\n'
        + _preflight_fn()
        + f'\ncbench_io_preflight "{tmp_path}" "{need_kb}" "{caveat}"\necho AFTER\n'
    )
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True)


needs_bash = pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")


@needs_bash
def test_preflight_passes_when_space_available(tmp_path):
    r = _run_preflight(tmp_path, 1)
    assert r.returncode == 0 and "Cbench IO preflight" in r.stdout and "AFTER" in r.stdout


@needs_bash
def test_preflight_fails_fast_when_space_short(tmp_path):
    r = _run_preflight(tmp_path, 10**15)  # an exabyte
    assert r.returncode == 1
    assert "CBENCH NOTICE: insufficient space" in r.stdout and "AFTER" not in r.stdout


@needs_bash
def test_preflight_prints_caveat_and_skips_check_without_requirement(tmp_path):
    r = _run_preflight(tmp_path, "", caveat="capped to fit")
    assert r.returncode == 0 and "CBENCH CAVEAT: capped to fit" in r.stdout and "AFTER" in r.stdout


# ---------------------------------------------------------------------------
# gen-jobs end to end
# ---------------------------------------------------------------------------

@pytest.fixture
def genv(tmp_path):
    cfg = tmp_path / "cluster.yaml"
    cfg.write_text(
        "cluster_name: zima\nmax_nodes: 4\nprocs_per_node: 8\nbatch_method: slurm\n"
        f"io_targets:\n  parallel: {GPFS}\n  node-local: /tmp\n"
    )
    facts_dir = tmp_path / "nodefacts"
    facts_dir.mkdir()
    (facts_dir / "typeA.json").write_text(json.dumps(_facts()))

    def run(*args):
        return CliRunner().invoke(cli, ["gen-jobs", "--ident", "t1", "--run-type", "batch",
                                        "--config", str(cfg), "--cbenchtest", str(tmp_path), *args])

    def script(testset, jobname):
        files = list((tmp_path / testset / "t1" / jobname).glob(f"{jobname}.*"))
        assert files, f"no script for {jobname}"
        return files[0].read_text()

    return SimpleNamespace(tmp=tmp_path, run=run, script=script)


def test_genjobs_io_without_facts_or_explicit_memory_fails_before_rendering(genv):
    res = genv.run("--testset", "io", "--ppn", "4", "--maxprocs", "4")
    assert res.exit_code != 0 and "--nodefacts" in res.output
    assert not (genv.tmp / "io").exists()  # nothing half-generated


def test_genjobs_io_ior_sized_from_facts(genv):
    res = genv.run("--testset", "io", "--ppn", "4", "--maxprocs", "4", "--nodefacts", "typeA")
    assert res.exit_code == 0, res.output
    s = genv.script("io", "ior1mNtoN-4ppn-4")
    assert "-b 3840m " in s
    assert f'TESTDIR="{GPFS}/$JOBID"' in s
    assert f'cbench_io_preflight "{GPFS}" "{3840 * 4 * 1024}" ""' in s
    assert "_HERE" not in s


def test_genjobs_bonnie_capped_and_warned(genv):
    res = genv.run("--testset", "iometadata", "--ppn", "1", "--maxprocs", "1",
                   "--nodefacts", "typeA")
    assert res.exit_code == 0, res.output
    assert "capacity cap" in res.output
    s = genv.script("iometadata", "bonnie-1ppn-1")
    m = re.search(r'opts="-d \. -s (\d+) -r (\d+)"', s)
    assert m and int(m.group(1)) >= 2 * int(m.group(2))
    assert 'IO_TARGET_DIR="/tmp"' in s
    assert re.search(r'cbench_io_preflight "\$PWD" "\d+" "bonnie\+\+ size capped', s)
    # bonnie++ 2.x: -y takes an argument (s = semaphore); a bare -y exits immediately
    assert s.count("-y s") == 3 and not re.search(r"-y\s*\"", s)


def test_genjobs_metadata_ppn_from_facts(genv):
    res = genv.run("--testset", "iometadata", "--nodefacts", "typeA")
    assert res.exit_code == 0, res.output
    assert "Metadata ppn levels" in res.output and "[1, 2, 4]" in res.output
    jobdirs = {p.name for p in (genv.tmp / "iometadata" / "t1").iterdir()}
    assert not any("-8ppn-" in d for d in jobdirs)  # config's 8 ppn > zima's 4 CPUs
    assert any(d.startswith("mdtest-4ppn-") for d in jobdirs)


@needs_bash
def test_generated_io_scripts_are_valid_bash(genv):
    for ts, ppn in (("io", "4"), ("iometadata", "1")):
        assert genv.run("--testset", ts, "--ppn", ppn, "--maxprocs", ppn,
                        "--nodefacts", "typeA").exit_code == 0
    for f in genv.tmp.glob("io*/t1/*/*.*"):
        r = subprocess.run(["bash", "-n", str(f)], capture_output=True, text=True)
        assert r.returncode == 0, f"{f.name}: {r.stderr}"


def test_genjobs_iosanity_keeps_small_size_but_uses_target(genv):
    res = genv.run("--testset", "iosanity", "--ppn", "4", "--maxprocs", "4")
    assert res.exit_code == 0, res.output  # no facts needed for sanity tests
    s = next(genv.tmp.glob("iosanity/t1/*/*.*")).read_text()
    assert "-b 2m" in s and GPFS in s


def test_find_n_uses_min_memtotal_from_facts(genv):
    res = CliRunner().invoke(cli, ["utils", "find-n", "--nprocs", "4", "--ppn", "4",
                                   "--util", "0.5", "--nodefacts", "typeA",
                                   "--cbenchtest", str(genv.tmp)])
    assert res.exit_code == 0, res.output
    assert "memory per node = 7524 MB" in res.output  # floor(7705320 / 1024)


@needs_bash
@pytest.mark.parametrize("present,expected", [
    (["ior", "IOR.posix"], "ior"),   # unified hpc/ior build wins
    (["IOR.posix"], "IOR.posix"),    # legacy install still works
])
def test_ior_templates_prefer_unified_binary(genv, tmp_path, present, expected):
    assert genv.run("--testset", "iosanity", "--ppn", "4", "--maxprocs", "4").exit_code == 0
    script = next(genv.tmp.glob("iosanity/t1/*/*.*")).read_text()
    block = re.search(r"^IOR_BIN=.*\n\[ -x .*\n", script, re.M).group(0)
    bindir = tmp_path / "fakebin"
    bindir.mkdir()
    for name in present:
        (bindir / name).write_text("#!/bin/sh\n")
        (bindir / name).chmod(0o755)
    block = block.replace(str(genv.tmp / "bin"), str(bindir))
    r = subprocess.run(["bash", "-c", block + 'basename "$IOR_BIN"'], capture_output=True, text=True)
    assert r.stdout.strip() == expected
    assert "$IOR_BIN -a POSIX" in script and "/IOR.posix -a" not in script
