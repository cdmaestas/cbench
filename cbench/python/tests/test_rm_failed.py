"""Tests for cbench rm-failed command."""

import textwrap
from pathlib import Path

import pytest
from click.testing import CliRunner

from cbench.cli.main import cli

runner = CliRunner()

_XHPL_PASS = textwrap.dedent("""\
    matrix A is randomly generated
    T/V                N    NB     P     Q               Time                 Gflops
    --------------------------------------------------------------------------------
    WR11C2R4       16384   512     4     4              12.34              5.678e+02

    PASSED
    PASSED
    PASSED

    Finished       1 tests with the following results:
                   1 tests completed and passed residual checks,
                   0 tests completed and failed residual checks,
                   0 tests skipped because of illegal input values.
""")

_XHPL_FAIL = textwrap.dedent("""\
    matrix A is randomly generated
    T/V                N    NB     P     Q               Time                 Gflops
    --------------------------------------------------------------------------------
    WR11C2R4       16384   512     4     4              12.34              5.678e+02

    FAILED
    FAILED
    FAILED

    Finished       1 tests with the following results:
                   0 tests completed and passed residual checks,
                   1 tests completed and failed residual checks,
                   0 tests skipped because of illegal input values.
""")


def _make_job(ident_dir: Path, jobname: str, content: str) -> Path:
    job_dir = ident_dir / jobname
    job_dir.mkdir(parents=True)
    (job_dir / f"{jobname}.o12345").write_text(content)
    return job_dir


def test_rm_failed_help():
    result = runner.invoke(cli, ["rm-failed", "--help"])
    assert result.exit_code == 0
    assert "--force" in result.output


def test_rm_failed_no_errors(tmp_path):
    ident_dir = tmp_path / "bandwidth" / "run1"
    _make_job(ident_dir, "xhpl-4ppn-16", _XHPL_PASS)

    result = runner.invoke(cli, [
        "rm-failed", "--testset", "bandwidth", "--ident", "run1",
        "--cbenchtest", str(tmp_path),
    ])
    assert result.exit_code == 0
    assert "No jobs" in result.output
    assert (ident_dir / "xhpl-4ppn-16").exists()


def test_rm_failed_preview(tmp_path):
    ident_dir = tmp_path / "bandwidth" / "run1"
    pass_dir = _make_job(ident_dir, "xhpl-4ppn-16", _XHPL_PASS)
    fail_dir = _make_job(ident_dir, "xhpl-4ppn-32", _XHPL_FAIL)

    result = runner.invoke(cli, [
        "rm-failed", "--testset", "bandwidth", "--ident", "run1",
        "--cbenchtest", str(tmp_path),
    ])
    assert result.exit_code == 0
    assert "Would remove" in result.output
    assert "xhpl-4ppn-32" in result.output
    assert "xhpl-4ppn-16" not in result.output
    # preview should NOT delete anything
    assert pass_dir.exists()
    assert fail_dir.exists()


def test_rm_failed_force(tmp_path):
    ident_dir = tmp_path / "bandwidth" / "run1"
    pass_dir = _make_job(ident_dir, "xhpl-4ppn-16", _XHPL_PASS)
    fail_dir = _make_job(ident_dir, "xhpl-4ppn-32", _XHPL_FAIL)

    result = runner.invoke(cli, [
        "rm-failed", "--testset", "bandwidth", "--ident", "run1",
        "--cbenchtest", str(tmp_path), "--force",
    ])
    assert result.exit_code == 0
    assert "Removing" in result.output
    assert pass_dir.exists()
    assert not fail_dir.exists()


def test_rm_failed_match_filter(tmp_path):
    ident_dir = tmp_path / "bandwidth" / "run1"
    fail32 = _make_job(ident_dir, "xhpl-4ppn-32", _XHPL_FAIL)
    fail64 = _make_job(ident_dir, "xhpl-8ppn-64", _XHPL_FAIL)

    # only remove jobs matching "4ppn"
    result = runner.invoke(cli, [
        "rm-failed", "--testset", "bandwidth", "--ident", "run1",
        "--cbenchtest", str(tmp_path), "--match", "4ppn",
    ])
    assert result.exit_code == 0
    assert "xhpl-4ppn-32" in result.output
    assert "xhpl-8ppn-64" not in result.output
    # neither deleted (no --force)
    assert fail32.exists()
    assert fail64.exists()


def test_rm_failed_missing_ident(tmp_path):
    result = runner.invoke(cli, [
        "rm-failed", "--testset", "bandwidth", "--ident", "nosuch",
        "--cbenchtest", str(tmp_path),
    ])
    assert result.exit_code != 0
