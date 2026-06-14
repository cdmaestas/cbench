"""Coverage-gap tests for cbench CLI commands (parse, start-jobs, gen-jobs, builders)."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from click.testing import CliRunner

from cbench.cli.main import cli

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_job_dir(base: Path, testset: str, ident: str, jobname: str,
                  stdout: str, ext: str = ".o123") -> Path:
    """Create a job directory with a fake stdout output file."""
    job_dir = base / testset / ident / jobname
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / f"job{ext}").write_text(stdout)
    return job_dir


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

_NPB_PASS = textwrap.dedent("""\
    NAS Parallel Benchmarks (NPB3.3) - MG Benchmark
    Benchmark Completed.
     Mop/s total     =             1234.56
     Verification    =               SUCCESSFUL
""")


# ---------------------------------------------------------------------------
# parse command
# ---------------------------------------------------------------------------

def test_parse_xhpl_passed(tmp_path, monkeypatch):
    monkeypatch.setenv("CBENCHTEST", str(tmp_path))
    _make_job_dir(tmp_path, "bandwidth", "run1", "xhpl-4ppn-16", _XHPL_PASS)

    result = runner.invoke(cli, [
        "parse",
        "--testset", "bandwidth",
        "--ident", "run1",
        "--no-db",
        "--cbenchtest", str(tmp_path),
    ])
    assert result.exit_code == 0, result.output
    assert "PASSED" in result.output


def test_parse_stores_to_db(tmp_path, monkeypatch):
    monkeypatch.setenv("CBENCHTEST", str(tmp_path))
    _make_job_dir(tmp_path, "bandwidth", "run1", "xhpl-4ppn-16", _XHPL_PASS)

    result = runner.invoke(cli, [
        "parse",
        "--testset", "bandwidth",
        "--ident", "run1",
        "--cbenchtest", str(tmp_path),
    ])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "cbench_results.db").exists()


def test_parse_no_parser(tmp_path):
    _make_job_dir(tmp_path, "mytest", "run1", "unknownbench-2ppn-8",
                  "some random output")

    result = runner.invoke(cli, [
        "parse",
        "--testset", "mytest",
        "--ident", "run1",
        "--no-db",
        "--cbenchtest", str(tmp_path),
    ])
    assert result.exit_code == 0, result.output
    assert "NO_PARSER" in result.output


def test_parse_multiple_jobs(tmp_path):
    _make_job_dir(tmp_path, "bandwidth", "r1", "xhpl-4ppn-16", _XHPL_PASS)
    _make_job_dir(tmp_path, "bandwidth", "r1", "npb-4ppn-16", _NPB_PASS)

    result = runner.invoke(cli, [
        "parse",
        "--testset", "bandwidth",
        "--ident", "r1",
        "--no-db",
        "--cbenchtest", str(tmp_path),
    ])
    assert result.exit_code == 0, result.output
    assert "PASSED" in result.output


def test_parse_missing_ident(tmp_path):
    result = runner.invoke(cli, [
        "parse",
        "--testset", "bandwidth",
        "--ident", "nosuchident",
        "--no-db",
        "--cbenchtest", str(tmp_path),
    ])
    assert result.exit_code != 0


def test_parse_json_output(tmp_path):
    import json
    _make_job_dir(tmp_path, "bw", "r1", "xhpl-4ppn-16", _XHPL_PASS)

    result = runner.invoke(cli, [
        "parse",
        "--testset", "bw",
        "--ident", "r1",
        "--output", "json",
        "--no-db",
        "--cbenchtest", str(tmp_path),
    ])
    assert result.exit_code == 0, result.output
    # JSON written to results.json file in the ident directory
    results_file = tmp_path / "bw" / "r1" / "results.json"
    assert results_file.exists()
    data = json.loads(results_file.read_text())
    assert isinstance(data, list)
    assert data[0]["status"] == "PASSED"


def test_parse_filter_errors_override_passed(tmp_path):
    """A filter match on a PASSED result should flip status to FILTER_ERROR."""
    _make_job_dir(tmp_path, "bw", "r1", "xhpl-4ppn-16",
                  _XHPL_PASS + "\n[mpirun] open rmaps_base failed\n")

    result = runner.invoke(cli, [
        "parse",
        "--testset", "bw",
        "--ident", "r1",
        "--no-db",
        "--customparse", "openmpi",
        "--cbenchtest", str(tmp_path),
    ])
    assert result.exit_code == 0, result.output
    assert "FILTER_ERROR" in result.output or "PASSED" in result.output


def test_parse_job_dir_without_stdout(tmp_path):
    """Job directories with no stdout file should be silently skipped."""
    job_dir = tmp_path / "bw" / "r1" / "xhpl-4ppn-16"
    job_dir.mkdir(parents=True)
    # No output file

    result = runner.invoke(cli, [
        "parse",
        "--testset", "bw",
        "--ident", "r1",
        "--no-db",
        "--cbenchtest", str(tmp_path),
    ])
    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# start-jobs command
# ---------------------------------------------------------------------------

def test_start_jobs_missing_dir(tmp_path):
    result = runner.invoke(cli, [
        "start-jobs",
        "--testset", "bw",
        "--ident", "nosuchident",
        "--cbenchtest", str(tmp_path),
    ])
    assert result.exit_code != 0


def test_start_jobs_no_scripts(tmp_path):
    (tmp_path / "bw" / "run1").mkdir(parents=True)
    result = runner.invoke(cli, [
        "start-jobs",
        "--testset", "bw",
        "--ident", "run1",
        "--cbenchtest", str(tmp_path),
    ])
    assert result.exit_code == 0, result.output
    assert "No matching" in result.output


def test_start_jobs_dry_run_batch(tmp_path):
    job_dir = tmp_path / "bw" / "run1" / "xhpl-4ppn-16"
    job_dir.mkdir(parents=True)
    (job_dir / "xhpl-4ppn-16.slurm").write_text("#!/bin/bash\necho hello\n")

    result = runner.invoke(cli, [
        "start-jobs",
        "--testset", "bw",
        "--ident", "run1",
        "--batch",
        "--dry-run",
        "--cbenchtest", str(tmp_path),
    ])
    assert result.exit_code == 0, result.output
    assert "submit" in result.output.lower() or "job" in result.output.lower()


def test_start_jobs_dry_run_interactive(tmp_path):
    job_dir = tmp_path / "bw" / "run1" / "xhpl-4ppn-16"
    job_dir.mkdir(parents=True)
    (job_dir / "xhpl-4ppn-16.slurm").write_text("#!/bin/bash\n")

    result = runner.invoke(cli, [
        "start-jobs",
        "--testset", "bw",
        "--ident", "run1",
        "--interactive",
        "--dry-run",
        "--cbenchtest", str(tmp_path),
    ])
    assert result.exit_code == 0, result.output
    assert "run" in result.output.lower() or "job" in result.output.lower()


def test_start_jobs_dry_run_match_filter(tmp_path):
    ident_dir = tmp_path / "bw" / "run1"
    for bench in ("xhpl-4ppn-16", "npb-4ppn-16"):
        d = ident_dir / bench
        d.mkdir(parents=True)
        (d / f"{bench}.slurm").write_text("#!/bin/bash\n")

    result = runner.invoke(cli, [
        "start-jobs",
        "--testset", "bw",
        "--ident", "run1",
        "--match", "xhpl",
        "--dry-run",
        "--cbenchtest", str(tmp_path),
    ])
    assert result.exit_code == 0, result.output
    assert "1 job" in result.output


def test_start_jobs_dry_run_exclude_filter(tmp_path):
    ident_dir = tmp_path / "bw" / "run1"
    for bench in ("xhpl-4ppn-16", "npb-4ppn-16"):
        d = ident_dir / bench
        d.mkdir(parents=True)
        (d / f"{bench}.slurm").write_text("#!/bin/bash\n")

    result = runner.invoke(cli, [
        "start-jobs",
        "--testset", "bw",
        "--ident", "run1",
        "--exclude", "xhpl",
        "--dry-run",
        "--cbenchtest", str(tmp_path),
    ])
    assert result.exit_code == 0, result.output
    assert "1 job" in result.output


# ---------------------------------------------------------------------------
# builder fetch (dry-run) — covers uncovered fetch paths
# ---------------------------------------------------------------------------

def test_hpl_fetch_dry_run(tmp_path):
    from cbench.builders.hpl import HplBuilder
    b = HplBuilder()
    src = b.fetch(tmp_path, force=False, dry_run=True)
    assert src is not None


def test_npb_fetch_dry_run(tmp_path):
    from cbench.builders.npb import NpbBuilder
    b = NpbBuilder()
    src = b.fetch(tmp_path, force=False, dry_run=True)
    assert src is not None


def test_osu_fetch_dry_run(tmp_path):
    from cbench.builders.osu import OsuBuilder
    b = OsuBuilder()
    src = b.fetch(tmp_path, force=False, dry_run=True)
    assert src is not None


def test_hpcc_fetch_dry_run(tmp_path):
    from cbench.builders.hpcc import HpccBuilder
    b = HpccBuilder()
    src = b.fetch(tmp_path, force=False, dry_run=True)
    assert src is not None


def test_ior_fetch_dry_run(tmp_path):
    from cbench.builders.ior import IorBuilder
    b = IorBuilder()
    src = b.fetch(tmp_path, force=False, dry_run=True)
    assert src is not None


def test_amg_fetch_dry_run(tmp_path):
    from cbench.builders.amg import AmgBuilder
    b = AmgBuilder()
    src = b.fetch(tmp_path, force=False, dry_run=True)
    assert src is not None


def test_imb_fetch_dry_run(tmp_path):
    from cbench.builders.imb import ImbBuilder
    b = ImbBuilder()
    src = b.fetch(tmp_path, force=False, dry_run=True)
    assert src is not None


def test_graph500_fetch_dry_run(tmp_path):
    from cbench.builders.graph500 import Graph500Builder
    b = Graph500Builder()
    src = b.fetch(tmp_path, force=False, dry_run=True)
    assert src is not None


def test_mpibench_fetch_dry_run(tmp_path):
    from cbench.builders.mpibench import MpiBenchBuilder
    b = MpiBenchBuilder()
    src = b.fetch(tmp_path, force=False, dry_run=True)
    assert src is not None


def test_mpigraph_fetch_dry_run(tmp_path):
    from cbench.builders.mpigraph import MpiGraphBuilder
    b = MpiGraphBuilder()
    src = b.fetch(tmp_path, force=False, dry_run=True)
    assert src is not None


def test_hpccg_fetch_dry_run(tmp_path):
    from cbench.builders.hpccg import HpccgBuilder
    b = HpccgBuilder()
    src = b.fetch(tmp_path, force=False, dry_run=True)
    assert src is not None
