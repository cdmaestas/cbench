"""`cbench watch` (backlog #2b): job states from the heartbeat files."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import time

import pytest
from click.testing import CliRunner

from cbench import templates, watch
from cbench.cli.main import cli

NEW = "Cbench heartbeat: fio-local-8ppn-8 (jobid 278) {state}, elapsed 0h02m00s at 2026-10-05 12:35:29, every 60s\n"
OLD = "Cbench heartbeat: fio-local-8ppn-8 (jobid 278) {state}, elapsed 0h02m00s at 2026-10-05 12:35:29\n"


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------

def test_parse_current_line():
    hb = watch.parse_heartbeat(NEW.format(state="still running"))
    assert (hb.job, hb.jobid, hb.state, hb.rc, hb.elapsed_s, hb.interval_s) == (
        "fio-local-8ppn-8", "278", "still running", None, 120, 60)


def test_parse_exit_and_older_line_without_interval():
    hb = watch.parse_heartbeat(OLD.format(state="exited rc=130"))
    assert (hb.state, hb.rc, hb.interval_s) == ("exited", 130, None)


@pytest.mark.parametrize("text", ["", "garbage\n", "Cbench heartbeat: x (jobid 1) dancing, elapsed 0h00m01s at 2026-10-05 12:00:00\n"])
def test_unparseable(text):
    assert watch.parse_heartbeat(text) is None


@pytest.mark.parametrize(("s", "out"), [(None, "-"), (5, "0m05s"), (125, "2m05s"), (3725, "1h02m05s")])
def test_hms(s, out):
    assert watch.hms(s) == out


# ---------------------------------------------------------------------------
# per-job state
# ---------------------------------------------------------------------------

def _job(base, name, line=None, age=0, output=False, now=1_000_000):
    d = base / name
    d.mkdir(parents=True)
    if line is not None:
        f = d / f"{name}.heartbeat"
        f.write_text(line)
        os.utime(f, (now - age, now - age))
    if output:
        (d / f"{name}.o123").write_text("output\n")
    return d


NOW = 1_000_000


@pytest.mark.parametrize(("line", "age", "kw", "status"), [
    (NEW.format(state="still running"), 30, {}, watch.RUNNING),
    (NEW.format(state="still running"), 179, {}, watch.RUNNING),       # within 3 x 60 s
    (NEW.format(state="still running"), 181, {}, watch.STALE),
    (NEW.format(state="started"), 500, {}, watch.STALE),
    (OLD.format(state="still running"), 200, {}, watch.STALE),         # falls back to 60 s
    (OLD.format(state="still running"), 200, {"default_interval": 120}, watch.RUNNING),
    (NEW.format(state="still running"), 100, {"stale_after": 60}, watch.STALE),
    (NEW.format(state="exited rc=0"), 9999, {}, watch.FINISHED),        # exits never go stale
    (NEW.format(state="exited rc=143"), 5, {}, watch.FAILED),
])
def test_job_status(tmp_path, line, age, kw, status):
    d = _job(tmp_path, "fio-local-8ppn-8", line, age)
    s = watch.job_status(d, **{"default_interval": 60, **kw}, now=NOW)
    assert s.status == status, s


def test_running_elapsed_counts_time_since_update(tmp_path):
    d = _job(tmp_path, "j", NEW.format(state="still running"), age=30)
    s = watch.job_status(d, default_interval=60, now=NOW)
    assert s.elapsed_s == 150 and s.age_s == 30


def test_stale_detail_and_failed_rc(tmp_path):
    s = watch.job_status(_job(tmp_path, "a", NEW.format(state="still running"), 400),
                         default_interval=60, now=NOW)
    assert "no heartbeat for 6m40s (every 60s); killed? jobid 278" in s.detail
    s = watch.job_status(_job(tmp_path, "b", NEW.format(state="exited rc=2"), 5),
                         default_interval=60, now=NOW)
    assert (s.status, s.rc) == (watch.FAILED, 2)


def test_no_heartbeat_file(tmp_path):
    assert watch.job_status(_job(tmp_path, "a"), default_interval=60).status == watch.NOT_STARTED
    s = watch.job_status(_job(tmp_path, "b", output=True), default_interval=60)
    assert s.status == watch.NO_HEARTBEAT and "without a heartbeat" in s.detail


def test_scan_done_and_success(tmp_path):
    _job(tmp_path, "a", NEW.format(state="exited rc=0"), 5, now=time.time())
    _job(tmp_path, "b", NEW.format(state="still running"), 5, now=time.time())
    st = watch.scan(tmp_path, default_interval=60)
    assert [s.status for s in st] == [watch.FINISHED, watch.RUNNING]
    assert not watch.all_done(st)
    st[1].status = watch.FINISHED
    assert watch.all_done(st) and watch.succeeded(st)
    st[1].status = watch.STALE
    assert watch.all_done(st) and not watch.succeeded(st)
    assert watch.scan(tmp_path / "missing", default_interval=60) == []


# ---------------------------------------------------------------------------
# the real job-script line parses
# ---------------------------------------------------------------------------

@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not installed")
def test_job_script_heartbeat_line_parses(tmp_path):
    text = (templates._templates_dir() / "common_header.in").read_text()
    block = re.search(r"^# Scratch data cleanup\..*?^trap 'exit 143' TERM\n", text, re.S | re.M).group(0)
    block = (block.replace("TESTSET_PATH_HERE/IDENT_HERE/JOBNAME_HERE", str(tmp_path))
                  .replace("JOBNAME_HERE", "imb-2ppn-8").replace("JOB_HEARTBEAT_S_HERE", "45"))
    script = ('cbench_echo() { echo "$@"; }\nCBENCH_RUN_TYPE=BATCH\nJOBID=42\nbegin_epoch=$(date +%s)\n'
              + block + "cbench_heartbeat_start\n"
              + 'cp "$CBENCH_HEARTBEAT_FILE" "$CBENCH_HEARTBEAT_FILE.started"\nexit 3\n')
    subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)
    started = watch.parse_heartbeat((tmp_path / "imb-2ppn-8.heartbeat.started").read_text())
    final = watch.parse_heartbeat((tmp_path / "imb-2ppn-8.heartbeat").read_text())
    assert (started.state, started.interval_s, started.jobid) == ("started", 45, "42")
    assert (final.state, final.rc, final.interval_s) == ("exited", 3, 45)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _tree(tmp_path):
    base = tmp_path / "io-default" / "r1"
    now = time.time()
    _job(base, "fio-local-8ppn-8", NEW.format(state="exited rc=0"), 5, now=now)
    _job(base, "iozone-local-8ppn-8", NEW.format(state="still running"), 5, now=now)
    _job(base, "bonnie-local-8ppn-8")
    return base


def test_cli_snapshot(tmp_path, monkeypatch):
    from cbench.cli import main as main_mod
    monkeypatch.setattr(main_mod.console, "width", 200)
    _tree(tmp_path)
    res = CliRunner().invoke(cli, ["watch", "--testset", "io-default", "--ident", "r1",
                                   "--cbenchtest", str(tmp_path)])
    assert res.exit_code == 0, res.output
    sep = r"[\s│]+"                                         # table column borders
    assert re.search(rf"fio-local-8ppn-8{sep}finished{sep}2m00s{sep}0", res.output)
    assert re.search(rf"iozone-local-8ppn-8{sep}running", res.output)
    assert re.search(rf"bonnie-local-8ppn-8{sep}not started", res.output)
    assert "1 running  1 finished  1 not started" in res.output


@pytest.mark.parametrize(("last", "code"), [("exited rc=0", 0), ("exited rc=1", 1)])
def test_cli_follow_exits_when_done(tmp_path, monkeypatch, last, code):
    base = tmp_path / "t" / "r1"
    _job(base, "a", NEW.format(state="exited rc=0"), 5, now=time.time())
    _job(base, "b", NEW.format(state=last), 5, now=time.time())
    res = CliRunner().invoke(cli, ["watch", "--testset", "t", "--ident", "r1", "--follow", "1",
                                   "--cbenchtest", str(tmp_path)])
    assert res.exit_code == code, res.output


def test_cli_follow_waits_for_running_job(tmp_path, monkeypatch):
    base = tmp_path / "t" / "r1"
    hb = _job(base, "a", NEW.format(state="still running"), 1, now=time.time()) / "a.heartbeat"
    sleeps = []

    def fake_sleep(s):          # the job finishes while watch waits
        sleeps.append(s)
        hb.write_text(NEW.format(state="exited rc=0"))
    from cbench.cli import main as main_mod
    monkeypatch.setattr(main_mod.time, "sleep", fake_sleep)
    res = CliRunner().invoke(cli, ["watch", "--testset", "t", "--ident", "r1", "--follow",
                                   "--cbenchtest", str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert sleeps == [10]                                   # default --follow interval


def test_cli_missing_ident(tmp_path):
    res = CliRunner().invoke(cli, ["watch", "--testset", "t", "--ident", "nope",
                                   "--cbenchtest", str(tmp_path)])
    assert res.exit_code != 0 and "run gen-jobs first" in res.output
