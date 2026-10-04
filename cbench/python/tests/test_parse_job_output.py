"""`cbench parse` job-output selection and unfinished-job detection.

Both found while validating fio on zima: a stray empty ``fio.o1`` next to the
real ``fio-1ppn-1.o<JOBID>`` was parsed instead of it (NOTSTARTED), and a fio
job still in its random phase parsed as PASSED from partial output.
"""

from __future__ import annotations

import os
from pathlib import Path

from click.testing import CliRunner

from cbench import templates
from cbench.cli.main import _job_output_files, cli
from cbench.parsers.fio import FioParser

_FIO_DONE = """\
Cbench fio: profile=general seq_bs=4m numjobs=4 size=256m direct=1 runtime=300s
seq_rw: (groupid=0, jobs=1): err= 0: pid=1: Sat Oct  3 21:04:00 2026
  read: IOPS=16, BW=66.6MiB/s (69.8MB/s)(19.5GiB/300001msec)
  write: IOPS=16, BW=67.4MiB/s (70.7MB/s)(19.7GiB/300001msec)
rand_rw: (groupid=0, jobs=4): err= 0: pid=2: Sat Oct  3 21:09:00 2026
  read: IOPS=1460, BW=5857KiB/s (5998kB/s)(1716MiB/300003msec)
  write: IOPS=1470, BW=5867KiB/s (6008kB/s)(1719MiB/300003msec)
Cbench fio: finished
"""


def _touch(path: Path, text: str, mtime: float) -> Path:
    path.write_text(text)
    os.utime(path, (mtime, mtime))
    return path


# ---------------------------------------------------------------------------
# _job_output_files
# ---------------------------------------------------------------------------

def test_newest_stdout_wins_over_listing_order(tmp_path):
    _touch(tmp_path / "fio.o1", "", 2000)                       # stray, newer name sort
    real = _touch(tmp_path / "fio-1ppn-1.o276210", _FIO_DONE, 3000)
    assert _job_output_files(tmp_path) == (real, None)


def test_rerun_takes_latest_run_and_its_stderr(tmp_path):
    _touch(tmp_path / "x-1ppn-1.o100", "old", 1000)
    _touch(tmp_path / "x-1ppn-1.e100", "old err", 1000)
    new_out = _touch(tmp_path / "x-1ppn-1.o200", "new", 2000)
    new_err = _touch(tmp_path / "x-1ppn-1.e200", "new err", 1500)  # older than .o, still paired
    _touch(tmp_path / "x-1ppn-1.e300", "unrelated", 2500)
    assert _job_output_files(tmp_path) == (new_out, new_err)


def test_stderr_falls_back_to_newest_when_unpaired(tmp_path):
    out = _touch(tmp_path / "slurm-55.out", "o", 1000)
    _touch(tmp_path / "job.e1", "a", 1000)
    err = _touch(tmp_path / "job.e2", "b", 2000)
    assert _job_output_files(tmp_path) == (out, err)


def test_no_output_files(tmp_path):
    (tmp_path / "x-1ppn-1.sh").write_text("#!/bin/bash\n")
    assert _job_output_files(tmp_path) == (None, None)


def test_parse_cli_ignores_stale_empty_output(tmp_path):
    job = tmp_path / "iometadata" / "f1" / "fio-1ppn-1"
    job.mkdir(parents=True)
    _touch(job / "fio-1ppn-1.o276210427966654720", _FIO_DONE, 1000)
    _touch(job / "fio.o1", "", 500)   # the redirect target from the zima run
    res = CliRunner().invoke(cli, ["parse", "--testset", "iometadata", "--ident", "f1",
                                   "--no-db", "--cbenchtest", str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert "PASSED" in res.output and "NOTSTARTED" not in res.output


# ---------------------------------------------------------------------------
# unfinished fio job
# ---------------------------------------------------------------------------

def test_fio_job_without_end_marker_is_started_not_passed():
    partial = _FIO_DONE[: _FIO_DONE.index("rand_rw:")]   # killed / still running
    r = FioParser().parse(partial)
    assert r.status == "ERROR(STARTED)" and r.metrics == {}
    assert "did not finish" in r.status_detail


def test_fio_job_with_end_marker_passes():
    r = FioParser().parse(_FIO_DONE)
    assert r.status == "PASSED"
    assert r.metrics["rand_read_iops"] == 1460


def test_snb_fio_output_has_no_markers_and_still_passes():
    snb_style = _FIO_DONE.replace("Cbench fio: profile=", "x").replace("Cbench fio: finished", "")
    assert FioParser().parse(snb_style).status == "PASSED"


def test_template_ends_with_marker():
    text = (templates._templates_dir() / "iometadata_fio.in").read_text()
    assert "Cbench fio: profile=" in text
    assert text.rstrip().endswith('cbench_echo "Cbench fio: finished"')
