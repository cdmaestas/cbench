"""gen-jobs job heartbeat (common_header.in): a status file, plus the terminal
for interactive runs, never the job's stdout. Runs the real bash."""
from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import time

import pytest
from click.testing import CliRunner

from cbench import templates
from cbench.cli.main import cli

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")


def _header_block() -> str:
    # the scratch-cleanup block (EXIT trap) contains the heartbeat functions
    text = (templates._templates_dir() / "common_header.in").read_text()
    m = re.search(r"^# Scratch data cleanup\..*?^trap 'exit 143' TERM\n", text, re.S | re.M)
    assert m, "cleanup/heartbeat block not found in common_header.in"
    return m.group(0)


def _script(jobdir, body, *, interval="1", run_type="INTERACTIVE"):
    block = (_header_block()
             .replace("TESTSET_PATH_HERE/IDENT_HERE/JOBNAME_HERE", str(jobdir))
             .replace("JOBNAME_HERE", "imb-2ppn-8")
             .replace("JOB_HEARTBEAT_S_HERE", interval))
    return ('cbench_echo() { echo "$@"; }\n'
            f"CBENCH_RUN_TYPE={run_type}\nJOBID=42\nbegin_epoch=$(date +%s)\n"
            + block + "cbench_heartbeat_start\n" + body)


def _run(tmp_path, body, timeout=20, env=None, **kw):
    return subprocess.run(["bash", "-c", _script(tmp_path, body, **kw)], capture_output=True,
                          text=True, timeout=timeout, env={**os.environ, **(env or {})})


def _hb(tmp_path):
    return (tmp_path / "imb-2ppn-8.heartbeat").read_text()


def test_interactive_heartbeat_on_terminal_and_file_not_stdout(tmp_path):
    r = _run(tmp_path, "sleep 2.5\necho BENCH-OUTPUT\n")
    assert r.returncode == 0
    beats = [ln for ln in r.stderr.splitlines() if "still running" in ln]
    assert len(beats) >= 2, r.stderr
    assert re.match(r"Cbench heartbeat: imb-2ppn-8 \(jobid 42\) still running, "
                    r"elapsed 0h00m0\ds at \d{4}-", beats[0])
    assert "heartbeat" not in r.stdout and "BENCH-OUTPUT" in r.stdout
    assert "exited rc=0" in _hb(tmp_path)


def test_batch_heartbeat_only_in_file(tmp_path):
    # schedulers often merge a batch job's stderr into its stdout file
    r = _run(tmp_path, "sleep 1.5\n", run_type="BATCH")
    assert "heartbeat" not in r.stderr + r.stdout
    assert "exited rc=0" in _hb(tmp_path)


def test_file_shows_running_while_job_runs(tmp_path):
    p = subprocess.Popen(["bash", "-c", _script(tmp_path, "sleep 5\n", run_type="BATCH")],
                         start_new_session=True)
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            f = tmp_path / "imb-2ppn-8.heartbeat"
            if f.exists() and "still running" in f.read_text():
                break
            time.sleep(0.1)
        assert "still running" in _hb(tmp_path)
    finally:
        os.killpg(p.pid, signal.SIGTERM)
        p.wait(timeout=10)
    assert "exited rc=143" in _hb(tmp_path)


def test_exit_status_recorded_and_preserved(tmp_path):
    r = _run(tmp_path, "exit 3\n")
    assert r.returncode == 3 and "exited rc=3" in _hb(tmp_path)


def test_bare_wait_does_not_wait_for_heartbeat(tmp_path):
    # bonnie++ runs instances with `&` then a bare `wait`
    t0 = time.monotonic()
    r = _run(tmp_path, "sleep 0.2 &\nwait\necho DONE\n", interval="30", timeout=15)
    assert r.returncode == 0 and "DONE" in r.stdout
    assert time.monotonic() - t0 < 10


def test_heartbeat_stops_with_the_job(tmp_path):
    # nothing lingers after a normal exit (the loop holds the terminal's stderr)
    t0 = time.monotonic()
    r = subprocess.run(["bash", "-c", _script(tmp_path, "echo HB=$CBENCH_HEARTBEAT_PID\n",
                                              interval="30")],
                       capture_output=True, text=True, timeout=15)
    assert time.monotonic() - t0 < 10     # communicate() saw stderr close
    pid = int(re.search(r"HB=(\d+)", r.stdout).group(1))
    time.sleep(0.2)
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_heartbeat_exits_when_job_shell_is_killed_outright(tmp_path):
    p = subprocess.Popen(["bash", "-c", _script(tmp_path, "echo HB=$CBENCH_HEARTBEAT_PID\nsleep 30\n")],
                         stdout=subprocess.PIPE, text=True, start_new_session=True)
    try:
        pid = int(re.search(r"HB=(\d+)", p.stdout.readline()).group(1))
        os.kill(p.pid, signal.SIGKILL)     # no trap runs
        p.wait(timeout=5)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.1)
        else:
            pytest.fail("heartbeat outlived the job shell")
    finally:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    assert "exited" not in _hb(tmp_path)     # a killed job's file never says it exited


def test_zero_interval_disables(tmp_path):
    r = _run(tmp_path, "sleep 1.2\n", interval="0")
    assert "heartbeat" not in r.stderr
    assert not (tmp_path / "imb-2ppn-8.heartbeat").exists()


def test_environment_overrides_interval(tmp_path):
    r = _run(tmp_path, "sleep 1.2\n", interval="300", env={"CBENCH_HEARTBEAT": "0"})
    assert not (tmp_path / "imb-2ppn-8.heartbeat").exists() and r.returncode == 0


def test_bad_interval_is_reported_not_ignored(tmp_path):
    r = _run(tmp_path, "true\n", interval="JOB_HEARTBEAT_S_HERE")  # e.g. a Perl-rendered job
    assert "CBENCH NOTICE: heartbeat interval 'JOB_HEARTBEAT_S_HERE' is not a number" in r.stdout
    assert r.returncode == 0


# ---------------------------------------------------------------------------
# gen-jobs wiring
# ---------------------------------------------------------------------------

def _genjobs(tmp_path, *args, cfg_extra=""):
    cfg = tmp_path / "cluster.yaml"
    cfg.write_text("cluster_name: zima\nmax_nodes: 1\nprocs_per_node: 2\nbatch_method: slurm\n"
                   + cfg_extra)
    res = CliRunner().invoke(cli, ["gen-jobs", "--testset", "latency", "--ident", "t1",
                                   "--run-type", "batch", "--ppn", "2", "--maxprocs", "2",
                                   "--match", "^imb-", "--config", str(cfg),
                                   "--cbenchtest", str(tmp_path), *args])
    assert res.exit_code == 0, res.output
    return (tmp_path / "latency" / "t1" / "imb-2ppn-2" / "imb-2ppn-2.slurm").read_text()


@pytest.mark.parametrize(("args", "cfg_extra", "secs"), [
    ((), "", "60"),
    ((), "job_heartbeat_s: 120\n", "120"),
    (("--heartbeat", "0"), "job_heartbeat_s: 120\n", "0"),
])
def test_genjobs_interval(tmp_path, args, cfg_extra, secs):
    s = _genjobs(tmp_path, *args, cfg_extra=cfg_extra)
    assert f'local secs="${{CBENCH_HEARTBEAT:-{secs}}}"' in s
    assert f'CBENCH_HEARTBEAT_FILE="{tmp_path}/latency/t1/imb-2ppn-2/imb-2ppn-2.heartbeat"' in s
    assert s.rstrip().endswith("cbench_heartbeat_start") or "\ncbench_heartbeat_start\n" in s
