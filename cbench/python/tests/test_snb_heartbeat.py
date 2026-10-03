"""Tests for the _runcmd progress heartbeat in cbench snb."""

import io

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


def test_runcmd_emits_heartbeat_for_long_command(tmp_path):
    out = tmp_path / "o.out"
    log = io.StringIO()
    # ~1s command with a 0.2s heartbeat → several "still running" lines
    snb._runcmd("sleep 1", out, overwrite=True, log_fh=log, heartbeat=0.2)
    contents = log.getvalue()
    assert "still running" in contents
    assert "RUNCMD: sleep 1" in contents


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
