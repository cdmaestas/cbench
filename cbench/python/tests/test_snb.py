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
    _parse_linpack_out,
    _parse_npb_out,
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


LINPACK_OUTPUT = """\
matrix A is randomly generated
T/V                N    NB     P     Q               Time                 Gflops
--------------------------------------------------------------------------------
WR11C2R4        1024   192     1     4               0.09             7.9022e+00

PASSED
PASSED
PASSED

Finished      1 tests with the following results:
              1 tests completed and passed residual checks,
              0 tests completed and failed residual checks,
              0 tests skipped because of illegal input values.
"""

NPB_EP_OUTPUT = """\
NAS Parallel Benchmarks (NPB3.4.2) - EP Benchmark
Benchmark Completed.
 Mop/s total     =               12345.67
 Verification    =               SUCCESSFUL
"""

NPB_CG_OUTPUT = """\
NAS Parallel Benchmarks (NPB3.4.2) - CG Benchmark
Benchmark Completed.
 Mop/s total     =                5678.90
 Verification    =               SUCCESSFUL
"""


def test_parse_linpack_out(tmp_path):
    f = tmp_path / "linpack.out"
    f.write_text(LINPACK_OUTPUT)
    result = _parse_linpack_out(f)
    assert "gflops" in result
    assert abs(result["gflops"] - 7.9022) < 0.01


def test_parse_linpack_out_missing(tmp_path):
    assert _parse_linpack_out(tmp_path / "nonexistent.out") == {}


def test_parse_npb_out_single(tmp_path):
    f = tmp_path / "npb.out"
    f.write_text(NPB_EP_OUTPUT)
    result = _parse_npb_out(f)
    assert "ep_mops" in result
    assert abs(result["ep_mops"] - 12345.67) < 1.0


def test_parse_npb_out_multi(tmp_path):
    f = tmp_path / "npb.out"
    f.write_text(NPB_EP_OUTPUT + "\n" + NPB_CG_OUTPUT)
    result = _parse_npb_out(f)
    assert "ep_mops" in result
    assert "cg_mops" in result
    assert abs(result["ep_mops"] - 12345.67) < 1.0
    assert abs(result["cg_mops"] - 5678.90) < 1.0


def test_parse_npb_out_missing(tmp_path):
    assert _parse_npb_out(tmp_path / "nonexistent.out") == {}


def test_snb_report_linpack_and_npb(tmp_path):
    """report command shows Linpack and NPB sections when output files exist."""
    ident_dir = tmp_path / "run1"
    ident_dir.mkdir()
    hostname = "n001"
    (ident_dir / f"{hostname}.snb.linpack.out").write_text(LINPACK_OUTPUT)
    (ident_dir / f"{hostname}.snb.npb.out").write_text(NPB_EP_OUTPUT + "\n" + NPB_CG_OUTPUT)

    result = runner.invoke(cli, [
        "snb", "report",
        "--ident", "run1",
        "--destdir", str(tmp_path),
        "--node", hostname,
    ])
    assert result.exit_code == 0, result.output
    assert "Linpack" in result.output
    assert "NAS Parallel" in result.output


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


# ---------------------------------------------------------------------------
# query command
# ---------------------------------------------------------------------------

def test_query_csv(tmp_path, monkeypatch):
    monkeypatch.setenv("CBENCHTEST", str(tmp_path))
    from cbench.db import ResultsDB, ParseResult as DBResult
    db = ResultsDB(tmp_path / "cbench_results.db")
    db.store(DBResult(
        cluster="test", testset="bandwidth", ident="run1", jobname="osubw-2ppn-16",
        benchmark="osubw", numprocs=16, ppn=2, numnodes=8, status="PASSED",
        metrics={"bw": 9500.0}, metric_units={"bw": "MB/s"},
    ))

    result = runner.invoke(cli, [
        "query", "--output", "csv", "--cbenchtest", str(tmp_path),
    ])
    assert result.exit_code == 0, result.output
    assert "benchmark" in result.output  # header row
    assert "osubw" in result.output


def test_query_aggregate(tmp_path, monkeypatch):
    monkeypatch.setenv("CBENCHTEST", str(tmp_path))
    from cbench.db import ResultsDB, ParseResult as DBResult
    db = ResultsDB(tmp_path / "cbench_results.db")
    for bw in [9000.0, 10000.0, 11000.0]:
        db.store(DBResult(
            cluster="test", testset="bandwidth", ident="run1", jobname=f"job-{bw}",
            benchmark="osubw", numprocs=16, ppn=2, numnodes=8, status="PASSED",
            metrics={"bw": bw}, metric_units={"bw": "MB/s"},
        ))

    result = runner.invoke(cli, [
        "query", "--aggregate", "--cbenchtest", str(tmp_path),
    ])
    assert result.exit_code == 0, result.output
    assert "Mean" in result.output or "mean" in result.output


def test_query_aggregate_json(tmp_path, monkeypatch):
    monkeypatch.setenv("CBENCHTEST", str(tmp_path))
    import json
    from cbench.db import ResultsDB, ParseResult as DBResult
    db = ResultsDB(tmp_path / "cbench_results.db")
    for bw in [9000.0, 11000.0]:
        db.store(DBResult(
            cluster="test", testset="bandwidth", ident="run1", jobname=f"job-{bw}",
            benchmark="osubw", numprocs=16, ppn=2, numnodes=8, status="PASSED",
            metrics={"bw": bw}, metric_units={"bw": "MB/s"},
        ))

    result = runner.invoke(cli, [
        "query", "--aggregate", "--output", "json", "--cbenchtest", str(tmp_path),
    ])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert len(data) == 1
    assert data[0]["benchmark"] == "osubw"
    assert data[0]["metric"] == "bw"
    assert abs(data[0]["mean"] - 10000.0) < 1.0
    assert data[0]["count"] == 2


def test_query_until_filter(tmp_path, monkeypatch):
    monkeypatch.setenv("CBENCHTEST", str(tmp_path))
    from cbench.db import ResultsDB, ParseResult as DBResult
    db = ResultsDB(tmp_path / "cbench_results.db")
    db.store(DBResult(
        cluster="test", testset="bandwidth", ident="run1", jobname="job1",
        benchmark="osubw", numprocs=16, ppn=2, numnodes=8, status="PASSED",
        metrics={"bw": 9500.0},
    ))

    # until a past date should return nothing
    result = runner.invoke(cli, [
        "query", "--until", "2020-01-01", "--cbenchtest", str(tmp_path),
    ])
    assert result.exit_code == 0
    assert "0 result" in result.output


def test_query_aggregate_csv(tmp_path, monkeypatch):
    monkeypatch.setenv("CBENCHTEST", str(tmp_path))
    from cbench.db import ResultsDB, ParseResult as DBResult
    db = ResultsDB(tmp_path / "cbench_results.db")
    db.store(DBResult(
        cluster="test", testset="bandwidth", ident="run1", jobname="job1",
        benchmark="osubw", numprocs=16, ppn=2, numnodes=8, status="PASSED",
        metrics={"bw": 9500.0},
    ))

    result = runner.invoke(cli, [
        "query", "--aggregate", "--output", "csv", "--cbenchtest", str(tmp_path),
    ])
    assert result.exit_code == 0, result.output
    assert "benchmark" in result.output
    assert "mean" in result.output
    assert "osubw" in result.output


# ---------------------------------------------------------------------------
# query --trend
# ---------------------------------------------------------------------------

def test_query_trend_table(tmp_path, monkeypatch):
    monkeypatch.setenv("CBENCHTEST", str(tmp_path))
    from cbench.db import ResultsDB, ParseResult as DBResult
    db = ResultsDB(tmp_path / "cbench_results.db")
    for i, bw in enumerate([9000.0, 10000.0, 11000.0]):
        db.store(DBResult(
            cluster="test", testset="bw", ident=f"run{i}", jobname=f"job{i}",
            benchmark="osubw", numprocs=16, ppn=2, numnodes=8, status="PASSED",
            metrics={"bw": bw}, metric_units={"bw": "MB/s"},
        ))

    result = runner.invoke(cli, [
        "query", "--trend", "--benchmark", "osubw", "--metric", "bw",
        "--cbenchtest", str(tmp_path),
    ])
    assert result.exit_code == 0, result.output
    assert "run0" in result.output
    assert "run2" in result.output


def test_query_trend_json(tmp_path, monkeypatch):
    import json as _json
    monkeypatch.setenv("CBENCHTEST", str(tmp_path))
    from cbench.db import ResultsDB, ParseResult as DBResult
    db = ResultsDB(tmp_path / "cbench_results.db")
    for i, bw in enumerate([9000.0, 11000.0]):
        db.store(DBResult(
            cluster="test", testset="bw", ident=f"run{i}", jobname=f"job{i}",
            benchmark="osubw", numprocs=16, ppn=2, numnodes=8, status="PASSED",
            metrics={"bw": bw},
        ))

    result = runner.invoke(cli, [
        "query", "--trend", "--benchmark", "osubw", "--metric", "bw",
        "--output", "json", "--cbenchtest", str(tmp_path),
    ])
    assert result.exit_code == 0, result.output
    data = _json.loads(result.output)
    assert len(data) == 2
    assert "ident" in data[0]
    assert "value" in data[0]


def test_query_trend_requires_benchmark_and_metric(tmp_path, monkeypatch):
    monkeypatch.setenv("CBENCHTEST", str(tmp_path))
    from cbench.db import ResultsDB, ParseResult as DBResult
    db = ResultsDB(tmp_path / "cbench_results.db")
    db.store(DBResult(
        cluster="test", testset="bw", ident="run1", jobname="job1",
        benchmark="osubw", numprocs=16, ppn=2, numnodes=8, status="PASSED",
        metrics={"bw": 9000.0},
    ))
    result = runner.invoke(cli, [
        "query", "--trend", "--benchmark", "osubw",
        "--cbenchtest", str(tmp_path),
    ])
    assert result.exit_code != 0


def test_query_prometheus_output(tmp_path, monkeypatch):
    monkeypatch.setenv("CBENCHTEST", str(tmp_path))
    from cbench.db import ResultsDB, ParseResult as DBResult
    db = ResultsDB(tmp_path / "cbench_results.db")
    db.store(DBResult(
        cluster="mycluster", testset="bandwidth", ident="run1", jobname="job1",
        benchmark="osubw", numprocs=16, ppn=2, numnodes=8, status="PASSED",
        metrics={"bw": 9500.0}, metric_units={"bw": "MB/s"},
    ))
    result = runner.invoke(cli, [
        "query", "--output", "prometheus", "--cbenchtest", str(tmp_path),
    ])
    assert result.exit_code == 0, result.output
    assert "# HELP cbench_metric_value" in result.output
    assert "# TYPE cbench_metric_value gauge" in result.output
    assert 'benchmark="osubw"' in result.output
    assert "9500.0" in result.output


# ---------------------------------------------------------------------------
# build check
# ---------------------------------------------------------------------------

def test_build_check_no_cache(tmp_path):
    result = runner.invoke(cli, [
        "build", "check", "--prefix", str(tmp_path),
    ])
    assert result.exit_code == 0, result.output
    assert "not built" in result.output


def test_build_check_missing_binary(tmp_path):
    from cbench.cli.build import BuildLock
    from cbench.builders import BuildConfig
    lock = BuildLock(tmp_path)
    lock.record("stream", "https://example.com/stream.c", BuildConfig(), ["missing_bin"])

    result = runner.invoke(cli, [
        "build", "check", "--prefix", str(tmp_path),
    ])
    assert result.exit_code != 0
    assert "MISSING" in result.output


def test_build_check_present_binary(tmp_path):
    from cbench.cli.build import BuildLock
    from cbench.builders import BuildConfig

    prefix_bin = tmp_path / "bin"
    prefix_bin.mkdir()
    bin_path = prefix_bin / "myecho"
    bin_path.write_text("#!/bin/sh\necho 'myecho v1.0'\n")
    bin_path.chmod(0o755)

    lock = BuildLock(tmp_path)
    lock.record("stream", "https://example.com/stream.c", BuildConfig(), ["myecho"])

    result = runner.invoke(cli, [
        "build", "check", "--prefix", str(tmp_path),
    ])
    assert result.exit_code == 0, result.output
    assert "OK" in result.output


# ---------------------------------------------------------------------------
# --remote dispatch
# ---------------------------------------------------------------------------

def test_snb_run_remote_dry_run(tmp_path):
    """--remote with --dry-run prints the dispatch command without executing."""
    result = runner.invoke(cli, [
        "snb", "run",
        "--ident", "run1",
        "--destdir", str(tmp_path),
        "--remote", "n001",
        "--dry-run",
    ])
    assert result.exit_code == 0, result.output
    assert "n001" in result.output
    assert "cbench snb run" in result.output


def test_snb_run_remote_rejects_bad_node(tmp_path):
    """--remote must reject node names containing path separators or spaces."""
    for bad in ["../evil", "n001 n002", "n001/evil"]:
        result = runner.invoke(cli, [
            "snb", "run",
            "--ident", "run1",
            "--destdir", str(tmp_path),
            "--remote", bad,
            "--dry-run",
        ])
        assert result.exit_code != 0, f"Expected failure for --remote '{bad}'"
        assert "Invalid" in result.output


def test_snb_run_remote_builds_ssh_cmd(tmp_path, monkeypatch):
    """When remotecmd_method=ssh, dispatch uses ssh."""
    import yaml
    cfg_path = tmp_path / "cluster.yaml"
    cfg_path.write_text(yaml.dump({"cluster_name": "test", "remotecmd_method": "ssh",
                                    "remotecmd_extraargs": ""}))
    result = runner.invoke(cli, [
        "snb", "run",
        "--ident", "run1",
        "--destdir", str(tmp_path),
        "--remote", "n002",
        "--dry-run",
        "--config", str(cfg_path),
    ])
    assert result.exit_code == 0, result.output
    assert "ssh" in result.output
    assert "n002" in result.output


def test_snb_run_remote_cbench_custom_path(tmp_path):
    """--remote-cbench replaces 'cbench' in the dispatched command."""
    result = runner.invoke(cli, [
        "snb", "run",
        "--ident", "run1",
        "--destdir", str(tmp_path),
        "--remote", "n001",
        "--remote-cbench", "/opt/cbench/bin/cbench",
        "--dry-run",
    ])
    assert result.exit_code == 0, result.output
    assert "/opt/cbench/bin/cbench" in result.output


def test_snb_run_remote_builds_pdsh_cmd(tmp_path):
    """When remotecmd_method=pdsh (default), dispatch uses pdsh."""
    import yaml
    cfg_path = tmp_path / "cluster.yaml"
    cfg_path.write_text(yaml.dump({"cluster_name": "test", "remotecmd_method": "pdsh",
                                    "remotecmd_extraargs": "-f 700"}))
    result = runner.invoke(cli, [
        "snb", "run",
        "--ident", "run1",
        "--destdir", str(tmp_path),
        "--remote", "n003",
        "--dry-run",
        "--config", str(cfg_path),
    ])
    assert result.exit_code == 0, result.output
    assert "pdsh" in result.output
    assert "n003" in result.output
    assert "-f" in result.output or "700" in result.output


# ---------------------------------------------------------------------------
# serve command (Flask not installed in test env → graceful error)
# ---------------------------------------------------------------------------

def test_serve_no_flask(tmp_path, monkeypatch):
    """serve command raises ClickException if Flask is not installed."""
    import sys
    # Hide flask from imports
    monkeypatch.setitem(sys.modules, "flask", None)
    result = runner.invoke(cli, [
        "serve", "--port", "19999", "--cbenchtest", str(tmp_path),
    ])
    # Should fail with a helpful message, not a traceback
    assert "Traceback" not in (result.output or "")
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# air-gapped dashboard (--no-cdn)
# ---------------------------------------------------------------------------

def test_build_html_cdn_uses_cdn_urls():
    """Default HTML includes CDN links."""
    from cbench.cli.serve import _build_html
    html = _build_html(no_cdn=False, assets_dir=None)
    assert "cdn.jsdelivr.net" in html


def test_build_html_no_cdn_no_assets_uses_minimal_css():
    """--no-cdn without assets falls back to minimal inline CSS."""
    from cbench.cli.serve import _build_html
    html = _build_html(no_cdn=True, assets_dir=None)
    assert "cdn.jsdelivr.net" not in html
    assert "<style>" in html
    assert "air-gapped" in html or "no-cdn-notice" in html


def test_build_html_no_cdn_with_assets_uses_local_paths(tmp_path):
    """--no-cdn with assets dir serving the files uses /static/ URLs."""
    from cbench.cli.serve import _build_html
    (tmp_path / "bootstrap.min.css").write_text("/* bootstrap */")
    (tmp_path / "chart.umd.min.js").write_text("/* chartjs */")
    html = _build_html(no_cdn=True, assets_dir=tmp_path)
    assert "cdn.jsdelivr.net" not in html
    assert "/static/bootstrap.min.css" in html
    assert "/static/chart.umd.min.js" in html


def test_build_html_no_cdn_missing_one_asset_uses_minimal(tmp_path):
    """If only one asset is present, fall back to minimal CSS (not partial CDN)."""
    from cbench.cli.serve import _build_html
    (tmp_path / "bootstrap.min.css").write_text("/* bootstrap */")
    # chart.umd.min.js intentionally absent
    html = _build_html(no_cdn=True, assets_dir=tmp_path)
    assert "cdn.jsdelivr.net" not in html
    assert "/static/chart.umd.min.js" not in html


# ---------------------------------------------------------------------------
# Security: XSS escaping in dashboard JS
# ---------------------------------------------------------------------------

def test_dashboard_html_contains_esc_helper():
    """The esc() helper must be present in the dashboard HTML."""
    from cbench.cli.serve import _build_html
    html = _build_html(no_cdn=False, assets_dir=None)
    assert "function esc(" in html
    assert "replace(/&/g" in html


def test_dashboard_results_table_uses_esc():
    """All DB-sourced fields in the results table must be wrapped with esc()."""
    from cbench.cli.serve import _build_html
    html = _build_html(no_cdn=False, assets_dir=None)
    # Each of these fields must appear as esc(...) not bare ${...}
    for field in ("benchmark", "cluster", "testset", "ident", "jobname", "numprocs"):
        assert f"esc(row.{field})" in html, f"Field {field!r} not wrapped with esc()"


# ---------------------------------------------------------------------------
# Security: Prometheus label escaping
# ---------------------------------------------------------------------------

def test_prometheus_label_escaping():
    """_prom_label must escape backslashes, double-quotes, and newlines."""
    from cbench.cli.serve import _prom_label
    assert _prom_label('a"b') == 'a\\"b'
    assert _prom_label("a\nb") == "a\\nb"
    assert _prom_label("a\\b") == "a\\\\b"
    assert _prom_label("normal") == "normal"


def test_prometheus_text_escapes_labels(tmp_path):
    """Metric names with double-quotes are escaped in /metrics output."""
    from cbench.cli.serve import _prometheus_text
    from cbench.db import ResultsDB, ParseResult

    db = ResultsDB(tmp_path / "test.db")
    pr = ParseResult(
        cluster="c1", testset="ts", ident="i1", jobname="xhpl-1ppn-1",
        benchmark="xhpl", numprocs=1, ppn=1, numnodes=1,
        status="PASSED",
        metrics={'gfl"ops': 1.0},
        metric_units={'gfl"ops': "GFlop/s"},
    )
    db.store(pr)
    text = _prometheus_text(db)
    # The double-quote in the metric name must be escaped
    assert '\\"' in text
    assert 'metric="gfl\\"ops"' in text
