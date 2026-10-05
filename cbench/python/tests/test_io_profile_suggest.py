"""IO profile discovery (backlog #4): nodecheck probes each target's block /
stripe size (facts v4), suggests the profile, and ``io_profile: auto`` moves
up to a whole multiple of it in gen-jobs and snb."""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from cbench import fioprofile, iosizing
from cbench import nodecheck as nc
from cbench.cli import nodecheck as nc_cli
from cbench.cli import snb
from cbench.cli.main import cli
from cbench.config import ClusterConfig

MIB = 1024


# ---------------------------------------------------------------------------
# fioprofile: sizes, alignment, auto
# ---------------------------------------------------------------------------

def test_size_helpers():
    assert [fioprofile.size_kb(s) for s in ("512k", "4m", "16M", "1g")] == [512, 4096, 16384, 1024 ** 2]
    assert [fioprofile.human_kb(k) for k in (4, 512, 4096, 16384, 1024 ** 2)] == [
        "4 KiB", "512 KiB", "4 MiB", "16 MiB", "1 GiB"]
    assert fioprofile.align_kb(None) is None and fioprofile.align_kb({}) is None
    assert fioprofile.align_kb({"block_kb": 4}) == 4
    assert fioprofile.align_kb({"block_kb": 4, "stripe_kb": 16 * MIB}) == 16 * MIB


@pytest.mark.parametrize(("fstype", "align", "profile", "moved"), [
    ("gpfs", None, "hpc", False),           # nothing known: today's choice
    ("gpfs", 4 * MIB, "hpc", False),        # 8m is a multiple of 4 MiB
    ("gpfs", 8 * MIB, "hpc", False),
    ("gpfs", 16 * MIB, "streaming", True),  # 8m would split 16 MiB blocks
    ("lustre", 16 * MIB, "streaming", True),
    ("xfs", 4, "general", False),
    ("nfs", 1 * MIB, "general", False),
    ("ext4", 8 * MIB, "hpc", True),         # general 4m -> hpc 8m
])
def test_auto_profile_moves_up_to_a_multiple(fstype, align, profile, moved):
    got, note = fioprofile.auto_profile(fstype, align)
    assert got == profile
    assert bool(note) == moved
    if moved:
        assert f"auto uses {profile}" in note


def test_auto_profile_keeps_choice_when_nothing_fits():
    profile, note = fioprofile.auto_profile("gpfs", 32 * MIB)
    assert profile == "hpc" and "no IO profile is a multiple of the 32 MiB" in note


def test_explicit_profile_and_override_never_move():
    assert fioprofile.seq_block_size("auto", "gpfs", "", 16 * MIB) == ("streaming", "16m")
    assert fioprofile.seq_block_size("hpc", "gpfs", "", 16 * MIB) == ("hpc", "8m")
    assert fioprofile.seq_block_size("auto", "gpfs", "2m", 16 * MIB) == ("streaming", "2m")


# ---------------------------------------------------------------------------
# nodecheck probe (real sh) with fake stat / findmnt / lfs
# ---------------------------------------------------------------------------

def _fake(bindir, name, body):
    p = bindir / name
    p.write_text("#!/bin/sh\n" + body)
    p.chmod(p.stat().st_mode | stat.S_IXUSR)


@pytest.mark.parametrize(("fstype", "lfs_out", "block", "stripe"), [
    ("gpfs", None, "16777216", ""),
    ("lustre", "16777216", "4096", "16777216"),
    ("lustre", "stripe_size: 1048576", "4096", "1048576"),   # older lfs prints a key
])
def test_probe_reports_block_and_stripe(tmp_path, fstype, lfs_out, block, stripe):
    target = tmp_path / "t"
    target.mkdir()
    bindir = tmp_path / "bin"
    bindir.mkdir()
    _fake(bindir, "findmnt", f"echo {fstype}\n")
    _fake(bindir, "stat", f"echo {block}\n")
    if lfs_out is not None:
        _fake(bindir, "lfs", f"echo '{lfs_out}'\n")
    script = nc.build_probe_script({"parallel": str(target)})
    lines = [ln for ln in script.splitlines() if "target." in ln or ln.startswith(("if", "  ", "else", "fi"))]
    env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}"}
    r = subprocess.run(["sh", "-c", "\n".join(lines)], capture_output=True, text=True, env=env)
    facts = nc.parse_output("".join(f"n1: {ln}\n" for ln in r.stdout.splitlines()))["n1"]
    assert facts["target.parallel.fstype"] == fstype
    assert facts["target.parallel.block_bytes"] == block
    assert facts["target.parallel.stripe_bytes"] == stripe


def test_probe_missing_target_reports_no_sizes(tmp_path):
    script = nc.build_probe_script({"parallel": str(tmp_path / "absent")})
    lines = [ln for ln in script.splitlines() if "target." in ln or ln.startswith(("if", "  ", "else", "fi"))]
    r = subprocess.run(["sh", "-c", "\n".join(lines)], capture_output=True, text=True)
    facts = nc.parse_output("".join(f"n1: {ln}\n" for ln in r.stdout.splitlines()))["n1"]
    assert facts["target.parallel.fstype"] == "MISSING"
    assert facts["target.parallel.block_bytes"] == "" and facts["target.parallel.stripe_bytes"] == ""


# ---------------------------------------------------------------------------
# analyze + report
# ---------------------------------------------------------------------------

def _host(block_par="16777216", block_loc="4096", stripe=""):
    return {"_complete": "1", "cpus": "4", "cores": "4", "memtotal_kb": "8000000", "model": "x",
            "target.parallel.fstype": "gpfs", "target.parallel.free_kb": "999999999",
            "target.parallel.block_bytes": block_par, "target.parallel.stripe_bytes": stripe,
            "target.node-local.fstype": "xfs", "target.node-local.free_kb": "9000000",
            "target.node-local.block_bytes": block_loc, "target.node-local.stripe_bytes": ""}


TARGETS = {"parallel": "/gpfs/s", "node-local": "/tmp"}


def test_analyze_records_sizes_and_suggestion():
    r = nc.analyze(["n1", "n2"], {"n1": _host(), "n2": _host(block_par="8388608")}, TARGETS)
    par, loc = r["aggregate"]["targets"]["parallel"], r["aggregate"]["targets"]["node-local"]
    assert par["block_kb"] == 16 * MIB                   # the largest any node saw
    assert par["suggested_profile"] == "streaming" and "16 MiB" in par["profile_note"]
    assert loc["block_kb"] == 4 and loc["suggested_profile"] == "general"
    assert "stripe_kb" not in par


def test_analyze_ignores_sub_kib_and_missing_sizes():
    r = nc.analyze(["n1"], {"n1": _host(block_par="", block_loc="512")}, TARGETS)
    t = r["aggregate"]["targets"]
    assert "block_kb" not in t["parallel"] and "block_kb" not in t["node-local"]
    assert t["parallel"]["suggested_profile"] == "hpc"


def _cfg(**kw):
    cfg = ClusterConfig(**kw)
    cfg.explicit_keys = frozenset(kw)
    return cfg


def test_report_lines_and_explicit_misalignment_warning():
    targets = nc.analyze(["n1"], {"n1": _host()}, TARGETS)["aggregate"]["targets"]
    lines = nc.profile_report(targets, _cfg())
    assert any(ln.startswith("parallel (/gpfs/s, gpfs, 16 MiB block): streaming (16m)") for ln in lines)
    assert any(ln.startswith("node-local (/tmp, xfs, 4 KiB block): general (4m)") for ln in lines)
    assert not any("WARNING" in ln for ln in lines)
    warn = [ln for ln in nc.profile_report(targets, _cfg(io_profile="hpc")) if "WARNING" in ln]
    assert len(warn) == 1 and "io_profile hpc (8m) is not a multiple of parallel's 16 MiB" in warn[0]
    warn = [ln for ln in nc.profile_report(targets, _cfg(io_seq_bs="2m")) if "WARNING" in ln]
    assert len(warn) == 1 and "io_seq_bs 2m" in warn[0]


def test_nodecheck_cli_prints_suggestion_and_writes_v4(tmp_path, monkeypatch):
    cfg = tmp_path / "cluster.yaml"
    cfg.write_text("cluster_name: zima\nio_targets:\n  parallel: /gpfs/s\n  node-local: /tmp\n")
    monkeypatch.setattr(nc_cli.console, "width", 300)
    monkeypatch.setattr(nc, "check_pdsh_rcmd", lambda rcmd: None)
    out = "".join(f"n{i}: {k}={v}\n" for i in (1, 2) for k, v in _host().items() if k != "_complete")
    out += "n1: cbench_probe=ok\nn2: cbench_probe=ok\n"
    monkeypatch.setattr(nc, "run_pdsh", lambda argv: (out, ""))
    res = CliRunner().invoke(cli, ["nodecheck", "--nodelist", "n[1-2]", "--cbenchtest",
                                   str(tmp_path), "--config", str(cfg)])
    assert res.exit_code == 0, res.output
    assert "IO profile per target" in res.output
    assert "parallel (/gpfs/s, gpfs, 16 MiB block): streaming (16m)" in res.output
    facts = json.loads((tmp_path / "nodefacts" / "zima.json").read_text())
    assert facts["schema_version"] == 4
    assert facts["aggregate"]["targets"]["parallel"]["suggested_profile"] == "streaming"


# ---------------------------------------------------------------------------
# gen-jobs sizing
# ---------------------------------------------------------------------------

def _nv(block_kb=16 * MIB, fstype="gpfs"):
    return iosizing.NodeValues(
        cpus=4, mem_io_kb=8 * 1024 ** 2, mem_nonio_kb=8 * 1024 ** 2,
        targets={"parallel": {"path": "/gpfs/s", "fstype": fstype, "shared": True,
                              "free_kb_min": 10 ** 12, "block_kb": block_kb}})


def test_ior_auto_moves_to_block_multiple_and_notes_it():
    nv = _nv()
    t = iosizing.ior_tokens(nv, _cfg(), ppn=4, numprocs=4, testset="io", benchmark="ior1mNtoN")
    assert (t["IOR_TRANSFER"], t["IOR_PROFILE"]) == ("16m", "streaming")
    assert int(t["IOR_BLOCKSIZE"].rstrip("m")) % 16 == 0
    assert len(nv.notes) == 1 and "target 'parallel' (/gpfs/s)" in next(iter(nv.notes))


def test_ior_explicit_profile_is_kept_without_note():
    nv = _nv()
    t = iosizing.ior_tokens(nv, _cfg(io_profile="hpc"), ppn=4, numprocs=4, testset="io",
                            benchmark="ior1mNtoN")
    assert (t["IOR_TRANSFER"], t["IOR_PROFILE"]) == ("8m", "hpc") and not nv.notes


def test_aligned_block_needs_no_note():
    nv = _nv(block_kb=4 * MIB)
    t = iosizing.ior_tokens(nv, _cfg(), ppn=4, numprocs=4, testset="io", benchmark="ior1mNtoN")
    assert t["IOR_TRANSFER"] == "8m" and not nv.notes


def test_facts_without_block_size_behave_as_before():
    nv = _nv(block_kb=None)
    del nv.targets["parallel"]["block_kb"]
    t = iosizing.ior_tokens(nv, _cfg(), ppn=4, numprocs=4, testset="io", benchmark="ior1mNtoN")
    assert t["IOR_TRANSFER"] == "8m" and not nv.notes


def test_gpfsperf_uses_block_aware_auto():
    nv = _nv()
    nv.targets["gpfs"] = nv.targets["parallel"]
    t = iosizing.gpfsperf_tokens(nv, _cfg(), testset="iogpfs", benchmark="gpfsperf")
    assert t["GPFSPERF_RECORD"] == "16m" and t["GPFSPERF_PROFILE"] == "streaming"


def test_genjobs_prints_note(tmp_path):
    from datetime import datetime, timezone
    facts = {"schema_version": 4, "name": "t", "created": datetime.now(timezone.utc).isoformat(),
             "allow_heterogeneous": False,
             "verdict": {"ok": True, "heterogeneous": False, "errors": [], "warnings": []},
             "aggregate": {"cpus": {"min": 4, "max": 4}, "cores": {"min": 4, "max": 4},
                           "memtotal_kb": {"min": 8000000, "max": 8000000}, "models": [],
                           "targets": {"parallel": {"path": "/gpfs/s", "fstype": "gpfs",
                                                    "shared": True, "free_kb_min": 10 ** 12,
                                                    "block_kb": 16 * MIB}}}}
    (tmp_path / "nodefacts").mkdir()
    (tmp_path / "nodefacts" / "t.json").write_text(json.dumps(facts))
    cfg = tmp_path / "c.yaml"
    cfg.write_text("cluster_name: zima\nmax_nodes: 1\nprocs_per_node: 4\nbatch_method: slurm\n"
                   "io_targets:\n  parallel: /gpfs/s\n")
    res = CliRunner().invoke(cli, ["gen-jobs", "--testset", "io", "--ident", "t1",
                                   "--run-type", "batch", "--ppn", "4", "--maxprocs", "4",
                                   "--match", "^ior1mNtoN-", "--nodefacts", "t",
                                   "--config", str(cfg), "--cbenchtest", str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert "NOTE: io_profile target 'parallel' (/gpfs/s): hpc (8m) is not a multiple" in res.output
    script = next((tmp_path / "io" / "t1").rglob("*.slurm")).read_text()
    assert "-t 16m" in script


# ---------------------------------------------------------------------------
# snb: local statvfs
# ---------------------------------------------------------------------------

def test_snb_local_block_kb(tmp_path, monkeypatch):
    assert snb._local_block_kb(tmp_path / "absent") is None
    for bsize, kb in ((16 * 1024 * 1024, 16 * MIB), (4096, 4), (512, None)):
        monkeypatch.setattr(os, "statvfs", lambda p, b=bsize: SimpleNamespace(f_bsize=b))
        assert snb._local_block_kb(tmp_path) == kb


def test_snb_dry_run_uses_block_aware_auto(tmp_path, monkeypatch):
    # fio need not be installed: the dry run only prints the commands
    monkeypatch.setattr(shutil, "which", lambda n: "/usr/bin/fio" if n == "fio" else None)
    monkeypatch.setattr(shutil, "disk_usage",
                        lambda p: shutil._ntuple_diskusage(2048 * 1024 ** 3, 0, 1024 * 1024 ** 3))
    monkeypatch.setattr(snb.console, "width", 10000)
    monkeypatch.setattr(snb, "_supports_odirect", lambda d: True)
    monkeypatch.setattr(snb, "_detect_fstype", lambda p, *a: "gpfs")
    monkeypatch.setattr(snb, "_local_block_kb", lambda p: 16 * MIB)
    target = tmp_path / "target"
    target.mkdir()
    res = CliRunner().invoke(cli, ["snb", "run", "--tests", "fio", "--fs-target", str(target),
                                   "--numcores", "2", "--destdir", str(tmp_path / "out"),
                                   "--ident", "x", "--dry-run"])
    assert res.exit_code == 0, res.output
    assert "--bs=16m" in res.output and "profile=streaming" in res.output
    assert "NOTE: io_profile on" in res.output and "auto uses streaming (16m)" in res.output
