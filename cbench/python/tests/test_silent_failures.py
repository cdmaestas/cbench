"""Failures that used to be swallowed now surface (secure-modernize sweep, Pass 2)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from cbench import schedulers
from cbench.cli import main as main_mod
from cbench.cli import nodehwtest as nhwt
from cbench.cli.main import cli
from cbench.config import ClusterConfig


def _jobs(tmp_path: Path, ext: str, names=("a-1ppn-1", "b-1ppn-1"), body="#!/bin/bash\n") -> None:
    for n in names:
        d = tmp_path / "ts" / "r1" / n
        d.mkdir(parents=True)
        (d / f"{n}{ext}").write_text(body)


def _start(tmp_path, *extra):
    return CliRunner().invoke(cli, ["start-jobs", "--testset", "ts", "--ident", "r1", "--delay", "0",
                                    "--cbenchtest", str(tmp_path), *extra])


# S1 -------------------------------------------------------------------------

def test_failed_batch_submission_is_an_error(tmp_path, monkeypatch):
    _jobs(tmp_path, ".slurm")
    monkeypatch.setattr(main_mod.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(returncode=1))
    res = _start(tmp_path)
    assert res.exit_code != 0
    assert isinstance(res.exception, AssertionError) and "exited 1" in str(res.exception)
    assert "Submitted" not in res.output


def test_unrunnable_batch_command_is_an_error(tmp_path, monkeypatch):
    _jobs(tmp_path, ".slurm")

    def boom(*a, **k):
        raise FileNotFoundError("sbatch")

    monkeypatch.setattr(main_mod.subprocess, "run", boom)
    res = _start(tmp_path)
    assert isinstance(res.exception, AssertionError) and "Failed to run batch submit" in str(res.exception)


def test_successful_batch_submission_counts(tmp_path, monkeypatch):
    _jobs(tmp_path, ".slurm")
    monkeypatch.setattr(main_mod.subprocess, "run",
                        lambda *a, **k: SimpleNamespace(returncode=0))
    res = _start(tmp_path)
    assert res.exit_code == 0 and "Submitted 2 job(s)" in res.output


# S2 -------------------------------------------------------------------------

def test_interactive_failures_reported_and_rest_still_run(tmp_path):
    _jobs(tmp_path, ".sh", names=("a-1ppn-1",), body="#!/bin/bash\nexit 3\n")
    marker = tmp_path / "b-ran"
    _jobs(tmp_path, ".sh", names=("b-1ppn-1",), body=f"#!/bin/bash\ntouch {marker}\n")
    res = _start(tmp_path, "--interactive")
    assert res.exit_code == 1
    assert "a-1ppn-1 (exit 3)" in res.output and "1 of 2 interactive job(s)" in res.output
    assert marker.exists()                      # the failing job did not stop the run


# S3 / S7 --------------------------------------------------------------------

@pytest.mark.parametrize("method", ["slurm", "torque"])
def test_queue_query_failure_is_an_error(monkeypatch, method):
    def boom(*a, **k):
        raise subprocess.CalledProcessError(1, "squeue")

    monkeypatch.setattr(schedulers.subprocess, "check_output", boom)
    with pytest.raises(AssertionError, match="queue query"):
        schedulers.query("r1", ClusterConfig(batch_method=method))


def test_lsf_query_refuses_instead_of_reporting_zero():
    with pytest.raises(AssertionError, match="LSF queue query is not implemented"):
        schedulers.query("r1", ClusterConfig(batch_method="lsf"))


def test_local_query_is_zero_by_design():
    assert schedulers.query("r1", ClusterConfig(batch_method="local"))["TOTAL"] == 0


# S4 -------------------------------------------------------------------------

def test_crashing_hw_test_parser_is_an_error(monkeypatch):
    class Boom:
        def parse(self, lines):
            raise ZeroDivisionError("bad math")

    monkeypatch.setattr(nhwt, "get_hw_test", lambda name: Boom())
    with pytest.raises(AssertionError, match="hw_test parser 'stream' failed: bad math"):
        nhwt._dispatch("stream", ["x"], {}, {})


# S5 -------------------------------------------------------------------------

def test_remote_pdsh_failure_exits_nonzero(tmp_path, monkeypatch):
    monkeypatch.setattr(nhwt.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1))
    res = CliRunner().invoke(cli, ["nodehwtest", "start-jobs", "--ident", "r1", "--remote",
                                   "--nodelist", "n[1-2]", "--cbenchtest", str(tmp_path)])
    assert res.exit_code != 0, res.output
    assert "remote pdsh command exited 1" in res.output


# S6 -------------------------------------------------------------------------

def test_snb_physical_basis_without_core_ids_warns(tmp_path, monkeypatch):
    import shutil
    from cbench.cli import snb
    monkeypatch.setattr(shutil, "which", lambda n: "/usr/bin/fio" if n == "fio" else None)
    monkeypatch.setattr(snb.console, "width", 10000)
    monkeypatch.setattr(snb, "_supports_odirect", lambda d: True)
    monkeypatch.setattr(snb, "_detect_physical_cores", lambda *a: 0)
    monkeypatch.setattr(snb, "_detect_cores", lambda: 6)
    monkeypatch.setattr(shutil, "disk_usage", lambda p: shutil._ntuple_diskusage(2**40, 0, 2**40))
    cfg = tmp_path / "cluster.yaml"
    cfg.write_text("io_threads_basis: physical\n")
    (tmp_path / "t").mkdir()
    res = CliRunner().invoke(cli, ["snb", "run", "--tests", "fio", "--fs-target", str(tmp_path / "t"),
                                   "--destdir", str(tmp_path / "out"), "--ident", "x", "--dry-run",
                                   "--config", str(cfg)])
    assert res.exit_code == 0, res.output
    assert "physical cores are unknown" in res.output and "--numjobs=6" in res.output


# B5: common_header cd -------------------------------------------------------

def test_job_stops_when_job_dir_is_missing(tmp_path):
    import shutil as _sh
    if _sh.which("bash") is None:
        pytest.skip("bash not installed")
    from cbench import templates
    header = (templates._templates_dir() / "common_header.in").read_text()
    head = header[: header.index("# Fail fast if an IO test")]
    script = ('cbench_echo() { echo "$@"; }\n'
              + head.replace("TESTSET_PATH_HERE/IDENT_HERE/JOBNAME_HERE", str(tmp_path / "gone"))
                    .replace("IDENT_HERE", "r1").replace("CBENCHTEST_HERE", str(tmp_path))
                    .replace("JOBSCRIPT_HERE", "x.sh")
              + "echo BENCHMARK-RAN\n")
    r = subprocess.run(["bash", "-c", script], capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 1
    assert "CBENCH NOTICE: cannot cd to job directory" in r.stdout and "BENCHMARK-RAN" not in r.stdout


def test_no_parser_rows_store_empty_detail_not_null(tmp_path):
    import sqlite3
    d = tmp_path / "mytest" / "r1" / "unknownbench-2ppn-8"
    d.mkdir(parents=True)
    (d / "job.o1").write_text("some output\n")
    res = CliRunner().invoke(cli, ["parse", "--testset", "mytest", "--ident", "r1",
                                   "--cbenchtest", str(tmp_path)])
    assert res.exit_code == 0, res.output
    from contextlib import closing
    with closing(sqlite3.connect(tmp_path / "cbench_results.db")) as con:
        row = con.execute("SELECT status, status_detail FROM runs").fetchone()
    assert row == ("NO_PARSER", "")
