"""Tests for cbench snb command."""

import textwrap
from pathlib import Path

import pytest
from click.testing import CliRunner

from cbench.cli.main import cli
from cbench.cli.snb import (
    _parse_streams_out,
    _parse_cachebench_out,
    _parse_dgemm_out,
    _parse_mpistreams_out,
    _parse_fio_out,
    _parse_hpcc_out,
)

runner = CliRunner()

# ---------------------------------------------------------------------------
# unit tests for output parsers
# ---------------------------------------------------------------------------

STREAMS_OUTPUT = textwrap.dedent("""\
    Function      Rate (MB/s)   Avg time     Min time     Max time
    Copy:       12345.6789       0.0010       0.0009       0.0011
    Scale:      11234.5678       0.0011       0.0011       0.0012
    Add:        13456.7890       0.0015       0.0015       0.0016
    Triad:      12000.0000       0.0016       0.0015       0.0017
""")


def test_parse_streams_out(tmp_path):
    f = tmp_path / "streams.out"
    f.write_text(STREAMS_OUTPUT)
    result = _parse_streams_out(f)
    assert "copy" in result
    assert abs(result["copy"] - 12345.6789) < 0.1
    assert "triad" in result


def test_parse_streams_out_missing(tmp_path):
    assert _parse_streams_out(tmp_path / "nonexistent.out") == {}


CACHEBENCH_OUTPUT = textwrap.dedent("""\
    ====> RDONLY
    1024 1234.56
    2048 2345.67
    ====> RDWR
    1024 3456.78
""")


def test_parse_cachebench_out(tmp_path):
    f = tmp_path / "cachebench.out"
    f.write_text(CACHEBENCH_OUTPUT)
    result = _parse_cachebench_out(f)
    assert "RDONLY" in result
    assert "RDWR" in result
    assert abs(result["RDONLY"] - (1234.56 + 2345.67) / 2) < 0.1


DGEMM_OUTPUT = textwrap.dedent("""\
    some header line
      DGEMM: NN lda=100 ldb=  100 ldc=100 1 2 3 1234.56 mem=10 MB
      DGEMM: NN lda=100 ldb=  100 ldc=100 1 2 3 1300.00 mem=10 MB
      DGEMM: NN lda=200 ldb=  200 ldc=200 1 2 3 2000.00 mem=40 MB
""")


def test_parse_dgemm_out(tmp_path):
    f = tmp_path / "nodeperf2.out"
    f.write_text(DGEMM_OUTPUT)
    result = _parse_dgemm_out(f)
    assert 10 in result
    assert abs(result[10] - (1234.56 + 1300.00) / 2) < 0.1
    assert 40 in result


MPISTREAMS_OUTPUT = textwrap.dedent("""\
    ====> 1 processes
    Copy:       10000.00       0.0010       0.0009       0.0011
    Triad:       9000.00       0.0010       0.0009       0.0011
    ====> 2 processes
    Copy:       18000.00       0.0010       0.0009       0.0011
    Triad:      16000.00       0.0010       0.0009       0.0011
""")


def test_parse_mpistreams_out(tmp_path):
    f = tmp_path / "mpistreams.out"
    f.write_text(MPISTREAMS_OUTPUT)
    result = _parse_mpistreams_out(f)
    assert 1 in result
    assert 2 in result
    assert abs(result[1]["copy"] - 10000.0) < 0.1
    assert abs(result[2]["triad"] - 16000.0) < 0.1


FIO_OUTPUT = textwrap.dedent("""\
    fio-3.33
    Starting 1 processes
    read: IOPS=316k, BW=1234MiB/s (1294MB/s)(72.3GiB/60001msec)
       clat (usec): min=2, avg=12.34, stdev=5.67, max=1234
      clat percentiles (usec):
       |  1.00th=[    4], 50.00th=[   10], 99.00th=[   50], 99.99th=[  200]
    write: IOPS=100k, BW=400MiB/s (419MB/s)(24.0GiB/60001msec)
       clat (usec): min=3, avg=20.00, stdev=8.00, max=2000
      clat percentiles (usec):
       |  1.00th=[    5], 99.00th=[   80], 99.99th=[  500]

    Run status group 0 (all jobs):
       READ: bw=1234MiB/s (1294MB/s), io=72.3GiB, run=60001-60001msec
      WRITE: bw=400MiB/s (419MB/s), io=24.0GiB, run=60001-60001msec
""")

HPCC_OUTPUT = textwrap.dedent("""\
    This is the DARPA/DOE HPC Challenge Benchmark version 1.5.0 October 2012
    Produced by Jack Dongarra and Piotr Luszczek

    ====== B E G I N N I N G   O F   T E S T S ======

    Begin of Summary section.
    SomeKernelOnNode=0
    StarDGEMM_Gflops=2.34567
    SingleDGEMM_Gflops=2.50000
    PTRANS_GBs=0.56789
    StarSTREAM_Triad=34567.89
    MPIRandomAccess_GUPs=0.00123
    StarFFT_Gflops=1.11111
    HPL_Tflops=0.00123456
    End of Summary section.
""")


def test_parse_fio_out(tmp_path):
    f = tmp_path / "fio.out"
    f.write_text(FIO_OUTPUT)
    result = _parse_fio_out(f)
    assert "read_bw_MiB_s" in result
    assert abs(result["read_bw_MiB_s"] - 1234.0) < 1.0
    assert "write_bw_MiB_s" in result
    assert abs(result["write_bw_MiB_s"] - 400.0) < 1.0


def test_parse_fio_out_missing(tmp_path):
    assert _parse_fio_out(tmp_path / "nonexistent.out") == {}


def test_parse_hpcc_out(tmp_path):
    f = tmp_path / "hpcc.out"
    f.write_text(HPCC_OUTPUT)
    result = _parse_hpcc_out(f)
    assert len(result) > 0
    assert "hpl" in result or "ep_dgemm" in result or "stream_triad" in result


def test_parse_hpcc_out_missing(tmp_path):
    assert _parse_hpcc_out(tmp_path / "nonexistent.out") == {}


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

def test_snb_help():
    result = runner.invoke(cli, ["snb", "--help"])
    assert result.exit_code == 0
    assert "run" in result.output
    assert "report" in result.output


def test_snb_run_help():
    result = runner.invoke(cli, ["snb", "run", "--help"])
    assert result.exit_code == 0
    assert "--ident" in result.output
    assert "--tests" in result.output


def test_snb_report_help():
    result = runner.invoke(cli, ["snb", "report", "--help"])
    assert result.exit_code == 0
    assert "--ident" in result.output


def test_snb_run_rejects_bad_node(tmp_path):
    """run_cmd must reject hostnames containing path separators."""
    result = runner.invoke(cli, [
        "snb", "run",
        "--ident", "run1",
        "--destdir", str(tmp_path),
        "--node", "../../evil",
        "--dry-run",
    ])
    assert result.exit_code != 0
    assert "Invalid" in result.output


def test_snb_run_dry_run(tmp_path):
    result = runner.invoke(cli, [
        "snb", "run",
        "--ident", "test1",
        "--destdir", str(tmp_path),
        "--tests", "stream",
        "--dry-run",
    ])
    assert result.exit_code == 0
    # ident directory should be created
    assert (tmp_path / "test1").is_dir()
    # log file should be created
    logs = list(tmp_path.glob("snb.*.test1.log"))
    assert logs


def test_snb_run_dry_run_no_binaries(tmp_path):
    """dry-run with no CBENCHOME binaries should still complete without error."""
    result = runner.invoke(cli, [
        "snb", "run",
        "--ident", "run1",
        "--destdir", str(tmp_path),
        "--tests", "stream|cachebench|dgemm|mpistreams|fio|hpcc",
        "--binpath", str(tmp_path / "nonexistent"),
        "--dry-run",
    ])
    assert result.exit_code == 0


def test_snb_report_no_data(tmp_path):
    (tmp_path / "run1").mkdir()
    result = runner.invoke(cli, [
        "snb", "report",
        "--ident", "run1",
        "--destdir", str(tmp_path),
        "--node", "testnode",
    ])
    assert result.exit_code == 0
    assert "No parsed results" in result.output


def test_snb_report_with_streams_data(tmp_path):
    ident_dir = tmp_path / "run1"
    ident_dir.mkdir()
    out = ident_dir / "testnode.snb.streams.out"
    out.write_text(STREAMS_OUTPUT)

    result = runner.invoke(cli, [
        "snb", "report",
        "--ident", "run1",
        "--destdir", str(tmp_path),
        "--node", "testnode",
    ])
    assert result.exit_code == 0
    assert "STREAM" in result.output


def test_snb_report_missing_ident(tmp_path):
    result = runner.invoke(cli, [
        "snb", "report",
        "--ident", "nosuchident",
        "--destdir", str(tmp_path),
    ])
    assert result.exit_code != 0


def test_snb_store_cmd(tmp_path, monkeypatch):
    monkeypatch.setenv("CBENCHTEST", str(tmp_path))
    ident_dir = tmp_path / "run1"
    ident_dir.mkdir()
    hostname = "n001"
    (ident_dir / f"{hostname}.snb.streams.out").write_text(STREAMS_OUTPUT)
    (ident_dir / f"{hostname}.snb.fio.out").write_text(FIO_OUTPUT)

    result = runner.invoke(cli, [
        "snb", "store",
        "--ident", "run1",
        "--destdir", str(tmp_path),
        "--node", hostname,
        "--numcores", "8",
    ])
    assert result.exit_code == 0, result.output
    assert "Stored" in result.output
    assert (tmp_path / "cbench_results.db").exists()


def test_snb_report_json(tmp_path):
    ident_dir = tmp_path / "run1"
    ident_dir.mkdir()
    hostname = "n001"
    (ident_dir / f"{hostname}.snb.streams.out").write_text(STREAMS_OUTPUT)
    (ident_dir / f"{hostname}.snb.fio.out").write_text(FIO_OUTPUT)

    result = runner.invoke(cli, [
        "snb", "report",
        "--ident", "run1",
        "--destdir", str(tmp_path),
        "--node", hostname,
        "--output", "json",
    ])
    import json
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["node"] == hostname
    assert "snb_streams" in data["benchmarks"]
    assert "snb_fio" in data["benchmarks"]


def test_snb_compare_cmd(tmp_path, monkeypatch):
    monkeypatch.setenv("CBENCHTEST", str(tmp_path))
    hostname = "n001"

    # Store baseline and current using the DB directly
    from cbench.db import ResultsDB, ParseResult as DBResult
    db = ResultsDB(tmp_path / "cbench_results.db")

    db.store(DBResult(
        cluster="test", testset="snb", ident="base", jobname=hostname,
        benchmark="snb_streams", numprocs=8, ppn=8, numnodes=1, status="PASSED",
        metrics={"copy": 10000.0, "triad": 9000.0},
    ))
    db.store(DBResult(
        cluster="test", testset="snb", ident="run2", jobname=hostname,
        benchmark="snb_streams", numprocs=8, ppn=8, numnodes=1, status="PASSED",
        metrics={"copy": 10100.0, "triad": 9100.0},  # slight improvement
    ))

    result = runner.invoke(cli, [
        "snb", "compare",
        "--ident", "run2",
        "--baseline", "base",
        "--node", hostname,
        "--threshold", "5.0",
    ])
    assert result.exit_code == 0, result.output
    assert "No regressions" in result.output


def test_snb_compare_detects_regression(tmp_path, monkeypatch):
    monkeypatch.setenv("CBENCHTEST", str(tmp_path))
    hostname = "n001"

    from cbench.db import ResultsDB, ParseResult as DBResult
    db = ResultsDB(tmp_path / "cbench_results.db")

    db.store(DBResult(
        cluster="test", testset="snb", ident="base2", jobname=hostname,
        benchmark="snb_streams", numprocs=8, ppn=8, numnodes=1, status="PASSED",
        metrics={"copy": 10000.0},
    ))
    db.store(DBResult(
        cluster="test", testset="snb", ident="run3", jobname=hostname,
        benchmark="snb_streams", numprocs=8, ppn=8, numnodes=1, status="PASSED",
        metrics={"copy": 8000.0},  # 20% drop → regression
    ))

    result = runner.invoke(cli, [
        "snb", "compare",
        "--ident", "run3",
        "--baseline", "base2",
        "--node", hostname,
        "--threshold", "5.0",
    ])
    assert result.exit_code != 0
    assert "REGRESSED" in result.output


def test_snb_report_all_metrics(tmp_path):
    """Report command handles all output file types without error."""
    ident_dir = tmp_path / "run1"
    ident_dir.mkdir()
    hostname = "n001"

    (ident_dir / f"{hostname}.snb.streams.out").write_text(STREAMS_OUTPUT)
    (ident_dir / f"{hostname}.snb.mpistreams.out").write_text(MPISTREAMS_OUTPUT)
    (ident_dir / f"{hostname}.snb.nodeperf2.out").write_text(DGEMM_OUTPUT)
    (ident_dir / f"{hostname}.snb.cachebench.out").write_text(CACHEBENCH_OUTPUT)
    (ident_dir / f"{hostname}.snb.fio.out").write_text(FIO_OUTPUT)
    (ident_dir / f"{hostname}.snb.hpcc.out").write_text(HPCC_OUTPUT)

    result = runner.invoke(cli, [
        "snb", "report",
        "--ident", "run1",
        "--destdir", str(tmp_path),
        "--node", hostname,
    ])
    assert result.exit_code == 0
    assert "STREAM" in result.output
    assert "DGEMM" in result.output
    assert "Multi-Process" in result.output
    assert "Cachebench" in result.output
    assert "FIO" in result.output
    assert "HPCC" in result.output
