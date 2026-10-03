"""Tests for the _runcmd progress heartbeat in cbench snb."""

import io
import subprocess
from unittest.mock import Mock

from cbench.cli import snb


def test_fmt_elapsed():
    assert snb._fmt_elapsed(5) == "5s"
    assert snb._fmt_elapsed(65) == "1m05s"
    assert snb._fmt_elapsed(600) == "10m00s"


def test_cmd_label_string():
    assert snb._cmd_label("cat /proc/meminfo") == "cat"


def test_cmd_label_list_with_fio_name():
    label = snb._cmd_label(["/usr/bin/fio", "--name=rand_rw", "--rw=randrw"])
    assert label == "fio rand_rw"


def test_cmd_label_list_plain():
    assert snb._cmd_label(["/usr/bin/nodeperf2-nompi", "-n", "1000"]) == "nodeperf2-nompi"


def test_runcmd_emits_heartbeat_for_long_command(tmp_path, monkeypatch):
    out = tmp_path / "o.out"
    log = io.StringIO()
    # Simulate two elapsed intervals without racing sleep against wait's timeout.
    proc = Mock(returncode=0)
    proc.wait.side_effect = [
        subprocess.TimeoutExpired("benchmark", 1),
        subprocess.TimeoutExpired("benchmark", 1),
        0,
    ]
    monkeypatch.setattr(snb.subprocess, "Popen", Mock(return_value=proc))
    monkeypatch.setattr(snb.time, "monotonic", Mock(side_effect=[0.0, 30.0, 60.0]))
    snb._runcmd(["benchmark"], out, overwrite=True, log_fh=log, heartbeat=30)
    contents = log.getvalue()
    assert contents.count("still running") == 2
    assert "still running (30s): benchmark" in contents
    assert "still running (1m00s): benchmark" in contents
    assert "RUNCMD: benchmark" in contents


def test_runcmd_no_heartbeat_for_fast_command(tmp_path):
    out = tmp_path / "o.out"
    log = io.StringIO()
    # finishes well before the first beat → no heartbeat line
    snb._runcmd("true", out, overwrite=True, log_fh=log, heartbeat=30)
    assert "still running" not in log.getvalue()


def test_runcmd_heartbeat_disabled(tmp_path):
    out = tmp_path / "o.out"
    log = io.StringIO()
    snb._runcmd("sleep 1", out, overwrite=True, log_fh=log, heartbeat=0)
    assert "still running" not in log.getvalue()


def test_runcmd_still_reports_nonzero_exit(tmp_path):
    out = tmp_path / "o.out"
    log = io.StringIO()
    snb._runcmd("exit 3", out, overwrite=True, log_fh=log, heartbeat=0.2)
    assert "exited 3" in log.getvalue()


def test_heartbeat_flag_exposed_with_default():
    default = next(p.default for p in snb.run_cmd.params if p.name == "heartbeat")
    assert default == snb._HEARTBEAT_SECS


def test_heartbeat_flag_forwarded_to_remote():
    # remote dispatch must carry --heartbeat so the remote run honors it
    cmd = snb._build_remote_cmd(
        type("C", (), {"remotecmd_method": "ssh", "remotecmd_extraargs": ""})(),
        remote_node="n1", ident="i", destdir="/d", numcores=4,
        tests="fio", binpath=None, mpi_cmd="mpirun",
        dry_run=True, store=False, config=None, heartbeat=5.0,
    )
    joined = " ".join(cmd)
    assert "--heartbeat 5.0" in joined
