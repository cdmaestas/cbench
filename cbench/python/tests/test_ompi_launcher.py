"""Open MPI launcher: works on Open MPI 5 (no orterun) as well as <= 4."""
from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess

import pytest
from click.testing import CliRunner

from cbench import launchers, templates
from cbench.cli.main import cli
from cbench.config import ClusterConfig
from cbench.parse_filters import apply_filters, build_filter_set

needs_bash = pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")


# ---------------------------------------------------------------------------
# launch command
# ---------------------------------------------------------------------------

def test_default_openmpi_cmd_resolves_at_runtime_and_maps_by_ppr():
    cfg = ClusterConfig(joblaunch_method="openmpi")
    cmd = launchers.build_launch_cmd(16, 4, 4, cfg)
    assert cmd == "${CBENCH_OMPI_RUN:-orterun} --map-by ppr:4:node -np 16"
    assert "-npernode" not in cmd


def test_explicit_joblaunch_cmd_is_used_verbatim():
    cfg = ClusterConfig(joblaunch_method="openmpi", joblaunch_cmd="/opt/ompi5/bin/mpirun",
                        joblaunch_extraargs="--bind-to core")
    assert (launchers.build_launch_cmd(8, 2, 4, cfg)
            == "/opt/ompi5/bin/mpirun --map-by ppr:2:node -np 8 --bind-to core")


# ---------------------------------------------------------------------------
# common_header.in resolution (bash, fake launchers on PATH)
# ---------------------------------------------------------------------------

def _resolve_block() -> str:
    text = (templates._templates_dir() / "common_header.in").read_text()
    m = re.search(r"^# Open MPI launcher\..*?^fi\nif \[ -n \"\$CBENCH_OMPI_RUN\" \]; then\n.*?^fi\n",
                  text, re.S | re.M)
    assert m, "Open MPI launcher block not found in common_header.in"
    return m.group(0)


def _fake(bindir, name, version_text=""):
    p = bindir / name
    p.write_text(f"#!/bin/sh\necho '{version_text}'\n")
    p.chmod(p.stat().st_mode | stat.S_IXUSR)


def _resolve(tmp_path, method="openmpi", env_run=None, **fakes):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    for name, version in fakes.items():
        _fake(bindir, name, version)
    # only the fakes plus what the block itself needs (grep)
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "grep").symlink_to(shutil.which("grep"))
    env = {"PATH": f"{bindir}:{tools}"}
    if env_run is not None:
        env["CBENCH_OMPI_RUN"] = env_run
    script = ('cbench_echo() { echo "$@"; }\n'
              + _resolve_block().replace("JOBLAUNCHMETHOD_HERE", method)
              + 'echo "RUN=[${CBENCH_OMPI_RUN:-orterun}]"\n')
    return subprocess.run([shutil.which("bash"), "-c", script], capture_output=True,
                          text=True, env=env)


@needs_bash
def test_prefers_orterun_on_open_mpi_4(tmp_path):
    r = _resolve(tmp_path, orterun="", mpirun="mpirun (Open MPI) 4.1.1")
    assert "RUN=[orterun]" in r.stdout and "Cbench Open MPI launcher: orterun" in r.stdout


@needs_bash
def test_uses_mpirun_on_open_mpi_5(tmp_path):
    r = _resolve(tmp_path, mpirun="mpirun (Open MPI) 5.0.5")
    assert "RUN=[mpirun]" in r.stdout and "CAVEAT" not in r.stdout


@needs_bash
def test_caveat_when_mpirun_is_not_open_mpi(tmp_path):
    r = _resolve(tmp_path, mpirun="HYDRA build details: Version: 4.1.2")
    assert "RUN=[mpirun]" in r.stdout
    assert "CBENCH CAVEAT: no orterun on PATH" in r.stdout


@needs_bash
def test_no_launcher_falls_back_to_orterun_and_fails_visibly(tmp_path):
    r = _resolve(tmp_path)
    assert "RUN=[orterun]" in r.stdout and "Cbench Open MPI launcher" not in r.stdout


@needs_bash
def test_environment_override_wins(tmp_path):
    r = _resolve(tmp_path, env_run="/opt/ompi5/bin/mpirun", orterun="")
    assert "RUN=[/opt/ompi5/bin/mpirun]" in r.stdout


@needs_bash
def test_other_launch_methods_do_not_probe(tmp_path):
    r = _resolve(tmp_path, method="slurm", mpirun="HYDRA")
    assert "RUN=[orterun]" in r.stdout and "CAVEAT" not in r.stdout


# ---------------------------------------------------------------------------
# gen-jobs output
# ---------------------------------------------------------------------------

def test_genjobs_batch_script_uses_resolved_launcher(tmp_path):
    cfg = tmp_path / "cluster.yaml"
    cfg.write_text("cluster_name: zima\nmax_nodes: 1\nprocs_per_node: 2\n"
                   "batch_method: slurm\njoblaunch_method: openmpi\n")
    res = CliRunner().invoke(cli, ["gen-jobs", "--testset", "latency", "--ident", "t1",
                                   "--run-type", "batch", "--ppn", "2", "--maxprocs", "2",
                                   "--match", "^imb-", "--config", str(cfg),
                                   "--cbenchtest", str(tmp_path)])
    assert res.exit_code == 0, res.output
    scripts = list((tmp_path / "latency" / "t1").glob("imb-2ppn-2/*.slurm"))
    assert scripts, os.listdir(tmp_path / "latency" / "t1")
    s = scripts[0].read_text()
    assert 'CBENCH_JOBLAUNCH_METHOD="openmpi"' in s
    assert 'CMD="${CBENCH_OMPI_RUN:-orterun} --map-by ppr:2:node -np 2' in s


# ---------------------------------------------------------------------------
# parse filters: Open MPI 5 / mpirun messages
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("launcher", ["orterun", "mpirun", "prterun"])
def test_rank_exit_filter_matches_any_launcher_name(launcher):
    line = (f"{launcher} noticed that process rank 3 with PID 77 on node n01 "
            "exited on signal 11 (Segmentation fault).")
    errs = apply_filters(build_filter_set(["openmpi"]), line)
    assert any("rank 3 on node n01" in e for e in errs), errs


@pytest.mark.parametrize("launcher", ["orterun", "mpirun", "prterun"])
def test_killing_job_filter_matches_any_launcher_name(launcher):
    errs = apply_filters(build_filter_set(["openmpi"]), f"{launcher}: killing job...")
    assert errs, launcher
