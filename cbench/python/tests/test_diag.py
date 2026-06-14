"""Tests for cbench diag command."""

import json
import textwrap
from pathlib import Path

import pytest
from click.testing import CliRunner

from cbench.cli.main import cli

runner = CliRunner()


def make_file(tmp_path: Path, name: str, content: str) -> Path:
    f = tmp_path / name
    f.write_text(textwrap.dedent(content))
    return f


# ---------------------------------------------------------------------------
# basic filter matching
# ---------------------------------------------------------------------------

def test_diag_slurm_walltime(tmp_path):
    f = make_file(tmp_path, "job.out", """\
        Starting benchmark...
        *** JOB 12345 CANCELLED AT 2024-01-01 DUE TO TIME LIMIT ***
        Done.
    """)
    result = runner.invoke(cli, ["diag", str(f), "--filters", "slurm"])
    assert result.exit_code == 0
    assert "WALLTIME" in result.output


def test_diag_no_matches(tmp_path):
    f = make_file(tmp_path, "clean.out", """\
        HPL run completed successfully.
        Gflops = 1234.5
    """)
    result = runner.invoke(cli, ["diag", str(f), "--filters", "slurm"])
    assert result.exit_code == 0
    assert "No filter matches" in result.output


def test_diag_multiple_files(tmp_path):
    f1 = make_file(tmp_path, "job1.out",
                   "*** JOB 1 CANCELLED AT 2024-01-01 DUE TO TIME LIMIT ***\n")
    f2 = make_file(tmp_path, "job2.out",
                   "*** JOB 2 CANCELLED AT 2024-01-02 DUE TO TIME LIMIT ***\n")
    result = runner.invoke(cli, ["diag", str(f1), str(f2), "--filters", "slurm"])
    assert result.exit_code == 0
    assert "WALLTIME" in result.output


# ---------------------------------------------------------------------------
# OMPI src/dst aggregation
# ---------------------------------------------------------------------------

OMPI_OUTPUT = textwrap.dedent("""\
    [n001:1234] [n002:5678] from n001 to: n002 error polling something with status RETRY EXCEEDED ERRORstatus number 12
    orterun noticed that job rank 0 with PID 999 on node n003 exited on signal 11 (Segmentation fault).
""")


def test_diag_ompi_errors(tmp_path):
    f = make_file(tmp_path, "ompi.out", OMPI_OUTPUT)
    result = runner.invoke(cli, ["diag", str(f), "--filters", "openmpi"])
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# threshold filtering
# ---------------------------------------------------------------------------

def test_diag_threshold(tmp_path):
    # Two different files hit the same slurm error — count should be 2
    f1 = make_file(tmp_path, "j1.out",
                   "*** JOB 1 CANCELLED AT 2024-01-01 DUE TO TIME LIMIT ***\n")
    f2 = make_file(tmp_path, "j2.out",
                   "*** JOB 2 CANCELLED AT 2024-01-02 DUE TO TIME LIMIT ***\n")
    # threshold=3 should suppress output (only 2 hits)
    result = runner.invoke(cli, [
        "diag", str(f1), str(f2),
        "--filters", "slurm", "--threshold", "3",
    ])
    assert result.exit_code == 0
    # no table rows printed at threshold 3
    assert "WALLTIME" in result.output  # error type header still appears
    # but no node/count rows visible — the table is empty so no count shown
    assert "2" not in result.output


# ---------------------------------------------------------------------------
# JSON output
# ---------------------------------------------------------------------------

def test_diag_json_output(tmp_path):
    f = make_file(tmp_path, "job.out",
                  "*** JOB 1 CANCELLED AT 2024-01-01 DUE TO TIME LIMIT ***\n")
    result = runner.invoke(cli, ["diag", str(f), "--filters", "slurm", "--output", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert any("WALLTIME" in entry["error_type"] for entry in data)


# ---------------------------------------------------------------------------
# testset scanning
# ---------------------------------------------------------------------------

def test_diag_testset_scan(tmp_path):
    # Build a minimal ident directory structure
    job_dir = tmp_path / "bandwidth" / "run1" / "xhpl-4ppn-16"
    job_dir.mkdir(parents=True)
    out_file = job_dir / "xhpl-4ppn-16.o12345"
    out_file.write_text("*** JOB 12345 CANCELLED AT 2024-01-01 DUE TO TIME LIMIT ***\n")

    result = runner.invoke(cli, [
        "diag",
        "--testset", "bandwidth",
        "--ident", "run1",
        "--cbenchtest", str(tmp_path),
        "--filters", "slurm",
    ])
    assert result.exit_code == 0
    assert "WALLTIME" in result.output


def test_diag_testset_missing(tmp_path):
    result = runner.invoke(cli, [
        "diag",
        "--testset", "nosuchtest",
        "--ident", "run1",
        "--cbenchtest", str(tmp_path),
    ])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# misc filter modules
# ---------------------------------------------------------------------------

def test_diag_misc_hpl_error(tmp_path):
    f = make_file(tmp_path, "hpl.out",
                  "HPL ERROR from process # 3, on line 42 of function HPL_pdtest:\n")
    result = runner.invoke(cli, ["diag", str(f), "--filters", "misc"])
    assert result.exit_code == 0
    assert "HPL ERROR" in result.output


def test_diag_all_filters_no_crash(tmp_path):
    f = make_file(tmp_path, "clean.out", "normal output line\n")
    result = runner.invoke(cli, ["diag", str(f)])
    assert result.exit_code == 0
