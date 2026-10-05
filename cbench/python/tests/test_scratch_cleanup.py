"""Job scratch-dir cleanup: common_header.in's cbench_scratch_dir + EXIT/signal trap.

A killed IO job used to leave its data on the target, eating the space later
jobs' preflights budget for. These run the real bash from common_header.in.
"""
from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import sys
import time

import pytest

from cbench import templates

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")

# templates whose job data lives in a per-job scratch dir
IO_TEMPLATES = [
    "iometadata_fio.in", "iolocal_iozone.in", "iometadata_bonnie.in",
    "iometadata_mdtest.in", "iogpfs_gpfsperf.in", "io500_io500.in",
    "io_ior1mNtoN.in", "iosanity_ior1mNto1.in", "iosanity_ior1mNtoN.in",
    "shakedown_iostress.in", "shakedown_iosanity.in", "shakedown_mdtest.in",
    "io_miranda.in", "shakedown_miranda.in", "iometadata_fileop.in",
]


def _cleanup_block() -> str:
    text = (templates._templates_dir() / "common_header.in").read_text()
    m = re.search(r"^# Scratch data cleanup\..*?^trap 'exit 143' TERM\n", text, re.S | re.M)
    assert m, "scratch cleanup block not found in common_header.in"
    return m.group(0)


def _script(body: str) -> str:
    return 'cbench_echo() { echo "$@"; }\n' + _cleanup_block() + body


def _run(body: str, cwd):
    return subprocess.run(["bash", "-c", _script(body)], capture_output=True, text=True,
                          cwd=cwd, timeout=30)


def test_scratch_dir_removed_on_normal_end_and_cd(tmp_path):
    scratch = tmp_path / "target" / "job42"
    r = _run(f'cbench_scratch_dir "{scratch}" cd\necho "PWD=$PWD"\ntouch data\n', tmp_path)
    assert r.returncode == 0, r.stderr
    assert f"PWD={scratch.resolve()}" in r.stdout
    assert "Cbench scratch cleanup: removed" in r.stdout
    assert not scratch.exists() and (tmp_path / "target").is_dir()


def test_exit_status_is_preserved(tmp_path):
    scratch = tmp_path / "job1"
    r = _run(f'cbench_scratch_dir "{scratch}"\ntouch "{scratch}/f"\nexit 3\n', tmp_path)
    assert r.returncode == 3
    assert not scratch.exists()


def test_without_cd_stays_in_place(tmp_path):
    scratch = tmp_path / "data"
    r = _run(f'cbench_scratch_dir "{scratch}"\necho "PWD=$PWD"\n', tmp_path)
    assert f"PWD={tmp_path}" in r.stdout or f"PWD={tmp_path.resolve()}" in r.stdout
    assert not scratch.exists()


@pytest.mark.parametrize("bad", ["", "/", ".", ".."])
def test_refuses_dangerous_dirs(tmp_path, bad):
    keep = tmp_path / "keep"
    keep.write_text("x")
    r = _run(f'cbench_scratch_dir "{bad}"\necho AFTER\n', tmp_path)
    assert r.returncode == 1
    assert "refusing to use" in r.stdout and "AFTER" not in r.stdout
    assert keep.exists()


def test_no_dirs_registered_is_a_noop(tmp_path):
    r = _run("echo HI\n", tmp_path)
    assert r.returncode == 0 and "HI" in r.stdout and "removed" not in r.stdout


def _wait_for_child(pid: int) -> None:
    # signal only once the "benchmark" is running: a signal landing while bash
    # is still forking it can be missed by the child
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        r = subprocess.run(["pgrep", "-P", str(pid), "sleep"], capture_output=True)
        if r.returncode == 0:
            return
        time.sleep(0.05)
    pytest.fail("benchmark stand-in never started")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX signals")
@pytest.mark.skipif(shutil.which("pgrep") is None, reason="pgrep not installed")
@pytest.mark.parametrize(("sig", "rc"), [(signal.SIGTERM, 143), (signal.SIGINT, 130),
                                         (signal.SIGHUP, 129)])
@pytest.mark.parametrize("background", [False, True], ids=["foreground", "background"])
def test_killed_job_removes_scratch(tmp_path, sig, rc, background):
    # the scheduler (scancel, time limit) and Ctrl-C signal the whole job, so
    # signal the process group: the benchmark and the job shell both get it
    scratch = tmp_path / "job7"
    run = "sleep 60 &\nwait\n" if background else "sleep 60\n"
    body = (f'cbench_scratch_dir "{scratch}" cd\nhead -c 4096 /dev/zero > data\n'
            f"echo READY\n{run}echo NOT-REACHED\n")
    p = subprocess.Popen(["bash", "-c", _script(body)], stdout=subprocess.PIPE, text=True,
                         cwd=tmp_path, start_new_session=True)
    try:
        assert p.stdout.readline().strip() == "READY"
        assert (scratch / "data").exists()
        _wait_for_child(p.pid)
        os.killpg(p.pid, sig)
        out, _ = p.communicate(timeout=20)
    finally:
        if p.poll() is None:
            os.killpg(p.pid, signal.SIGKILL)
            p.wait()
    assert p.returncode == rc
    assert "NOT-REACHED" not in out
    assert not scratch.exists()


@pytest.mark.parametrize("name", IO_TEMPLATES)
def test_io_templates_use_scratch_dir(name):
    text = (templates._templates_dir() / name).read_text()
    assert "cbench_scratch_dir " in text
    assert "cbench_runin_tempdir" not in text
    assert not re.search(r"^mkdir -p \$TESTDIR$", text, re.M)
