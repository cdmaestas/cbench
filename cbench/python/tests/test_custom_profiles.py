"""Custom IO profiles from cluster.yaml ``io_profiles`` (backlog #7): a custom
group's target decides where every member writes."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import pytest
from click.testing import CliRunner

from cbench import profiles, templates
from cbench.cli.main import cli
from cbench.config import ConfigError, load_config
from cbench.parsers import get_parser

TDIR = templates._templates_dir()


def _spec(**groups):
    return {"groups": groups or {"g": {"target": "parallel", "members": ["iometadata_fio"]}}}


# ---------------------------------------------------------------------------
# loading / validation
# ---------------------------------------------------------------------------

def test_custom_profile_defaults():
    prof = profiles.custom_profiles({"mine": _spec(
        par={"target": "parallel", "members": ["iometadata_fio", "io_ior1mNtoN"]},
        nvme={"target": "nvme", "suffix": "nv", "members": ["iometadata_fio"]},
    )}, TDIR)["mine"]
    assert prof.default_groups == ("par", "nvme")          # every group by default
    par, nvme = prof.groups["par"], prof.groups["nvme"]
    assert (par.target, par.suffix, par.route_members) == ("parallel", "par", True)
    assert nvme.suffix == "nv"
    assert [(m.home, m.benchmark) for m in par.members] == [("iometadata", "fio"), ("io", "ior1mNtoN")]
    assert profiles.job_benchmark(par.members[1], par) == "ior1mNtoN-par"


def test_builtin_groups_do_not_route_members():
    assert not any(g.route_members for p in profiles.PROFILES.values() for g in p.groups.values())


@pytest.mark.parametrize(("spec", "message"), [
    ({"io-default": _spec()}, "reuses a built-in profile name"),
    ({"mine": _spec(g={"target": "parallel", "members": ["iometadata_nosuch"]})},
     "no template iometadata_nosuch.in"),
    ({"mine": {**_spec(), "default_groups": ["other"]}}, "unknown group(s) other"),
    ({"mine": _spec(a={"target": "parallel", "suffix": "x", "members": ["iometadata_fio"]},
                    b={"target": "nvme", "suffix": "x", "members": ["iometadata_fio"]})},
     "would both be named fio-x-*"),
])
def test_custom_profile_errors(spec, message):
    with pytest.raises(profiles.ProfileError, match=re.escape(message)):
        profiles.custom_profiles(spec, TDIR)


def test_get_profile_lists_custom_and_builtin():
    io = {"mine": _spec()}
    assert profiles.get_profile("mine", io, TDIR).groups["g"].route_members
    assert profiles.get_profile("io-default", io, TDIR) is profiles.PROFILES["io-default"]
    with pytest.raises(profiles.ProfileError, match="available: io-default, io500, mine"):
        profiles.get_profile("nope", io, TDIR)


def test_config_schema(tmp_path):
    p = tmp_path / "c.yaml"
    p.write_text("io_profiles:\n  mine:\n    groups:\n      g:\n        target: parallel\n"
                 "        members: [iometadata_fio]\n")
    assert load_config(p).io_profiles["mine"]["groups"]["g"]["target"] == "parallel"
    for bad in ("        members: [fio]\n",                     # not <testset>_<benchmark>
                "        members: []\n",
                "        members: [iometadata_fio]\n        extra: 1\n"):
        p.write_text("io_profiles:\n  mine:\n    groups:\n      g:\n        target: parallel\n" + bad)
        with pytest.raises(ConfigError):
            load_config(p)
    p.write_text("io_profiles:\n  mine:\n    groups:\n      g:\n        members: [iometadata_fio]\n")
    with pytest.raises(ConfigError):                           # target is required
        load_config(p)


# ---------------------------------------------------------------------------
# gen-jobs: members write to the group's target
# ---------------------------------------------------------------------------

def _facts(nvme_free_kb=10 ** 9):
    tgt = {"parallel": {"path": "/gpfs/s", "fstype": "gpfs", "shared": True, "free_kb_min": 10 ** 12},
           "node-local": {"path": "/tmp", "fstype": "xfs", "shared": False, "free_kb_min": 10 ** 8},
           "nvme": {"path": "/local/nvme", "fstype": "xfs", "shared": False,
                    "free_kb_min": nvme_free_kb}}
    return {"schema_version": 4, "name": "t", "created": datetime.now(timezone.utc).isoformat(),
            "allow_heterogeneous": False,
            "verdict": {"ok": True, "heterogeneous": False, "errors": [], "warnings": []},
            "aggregate": {"cpus": {"min": 4, "max": 4}, "cores": {"min": 4, "max": 4},
                          "memtotal_kb": {"min": 8000000, "max": 8000000}, "models": [],
                          "targets": tgt}}


_CFG = """cluster_name: zima
max_nodes: 1
procs_per_node: 4
batch_method: slurm
io_targets:
  parallel: /gpfs/s
  node-local: /tmp
  nvme: /local/nvme
io_profiles:
  fast-local:
    description: fio and IOR on the NVMe scratch, fio on GPFS
    default_groups: [nvme]
    groups:
      nvme:
        target: nvme
        members: [iometadata_fio, io_ior1mNtoN]
      gpfs-small:
        target: parallel
        suffix: gsmall
        members: [iometadata_fio]
      missing:
        target: burstbuffer
        members: [iometadata_fio]
"""


def _gen(tmp_path, *args, facts=None):
    (tmp_path / "nodefacts").mkdir(exist_ok=True)
    (tmp_path / "nodefacts" / "t.json").write_text(json.dumps(facts or _facts()))
    cfg = tmp_path / "c.yaml"
    cfg.write_text(_CFG)
    return CliRunner().invoke(cli, ["gen-jobs", "--profile", "fast-local", "--ident", "r1",
                                    "--run-type", "batch", "--ppn", "4", "--maxprocs", "4",
                                    "--nodefacts", "t", "--config", str(cfg),
                                    "--cbenchtest", str(tmp_path), *args])


def _script(tmp_path, job):
    return next((tmp_path / "fast-local" / "r1" / job).glob("*.slurm")).read_text()


def test_default_group_writes_to_its_target(tmp_path):
    res = _gen(tmp_path)
    assert res.exit_code == 0, res.output
    jobs = sorted(p.name for p in (tmp_path / "fast-local" / "r1").iterdir())
    assert jobs == ["fio-nvme-4ppn-4", "ior1mNtoN-nvme-4ppn-1", "ior1mNtoN-nvme-4ppn-2",
                    "ior1mNtoN-nvme-4ppn-4"]
    assert 'IO_TARGET_DIR="/local/nvme"' in _script(tmp_path, "fio-nvme-4ppn-4")
    assert 'TESTDIR="/local/nvme/$JOBID"' in _script(tmp_path, "ior1mNtoN-nvme-4ppn-4")


def test_fio_on_the_parallel_target(tmp_path):
    res = _gen(tmp_path, "--group", "gpfs-small")
    assert res.exit_code == 0, res.output
    s = _script(tmp_path, "fio-gsmall-4ppn-4")
    assert 'IO_TARGET_DIR="/gpfs/s"' in s
    assert "seqbs=8m" in s                    # auto on GPFS -> hpc, from the group's target


def test_missing_target_group_is_skipped(tmp_path):
    res = _gen(tmp_path, "--group", "all")
    assert res.exit_code == 0, res.output
    assert "skipping group 'missing': io_targets.burstbuffer is not set" in res.output
    jobs = {p.name for p in (tmp_path / "fast-local" / "r1").iterdir()}
    assert {j.rsplit("-", 2)[0] for j in jobs} == {"fio-nvme", "ior1mNtoN-nvme", "fio-gsmall"}


def test_free_space_cap_comes_from_the_group_target(tmp_path):
    res = _gen(tmp_path, facts=_facts(nvme_free_kb=2 * 1024 ** 2))   # 2 GiB on the NVMe
    assert res.exit_code == 0, res.output
    assert "target 'nvme' free space" in res.output        # IOR capped against nvme, not parallel


def test_builtin_profile_unchanged(tmp_path):
    (tmp_path / "nodefacts").mkdir()
    (tmp_path / "nodefacts" / "t.json").write_text(json.dumps(_facts()))
    cfg = tmp_path / "c.yaml"
    cfg.write_text(_CFG)
    res = CliRunner().invoke(cli, ["gen-jobs", "--profile", "io-default", "--ident", "r1",
                                   "--run-type", "batch", "--match", "^fio-",
                                   "--nodefacts", "t", "--config", str(cfg),
                                   "--cbenchtest", str(tmp_path)])
    assert res.exit_code == 0, res.output
    s = next((tmp_path / "io-default" / "r1").rglob("*.slurm")).read_text()
    assert 'IO_TARGET_DIR="/tmp"' in s


def test_bad_custom_profile_is_a_usage_error(tmp_path):
    cfg = tmp_path / "c.yaml"
    cfg.write_text(_CFG.replace("members: [iometadata_fio, io_ior1mNtoN]",
                                "members: [iometadata_nosuch]"))
    res = CliRunner().invoke(cli, ["gen-jobs", "--profile", "fast-local", "--ident", "r1",
                                   "--config", str(cfg), "--cbenchtest", str(tmp_path)])
    assert res.exit_code != 0 and "no template iometadata_nosuch.in" in res.output


@pytest.mark.parametrize("bench", ["fio-nvme", "ior1mNtoN-nvme", "fio-gsmall"])
def test_parse_finds_parser_for_custom_job_names(bench):
    assert get_parser(bench) is not None
