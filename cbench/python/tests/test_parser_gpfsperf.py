"""Tests for the gpfsperf IBM GPFS/Spectrum Scale benchmark parser."""

import pytest
from cbench.parsers import get_parser, REGISTRY

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Newer Spectrum Scale 4.x/5.x format — full result line
_FULL_OUTPUT = """\
/usr/lpp/mmfs/samples/perf/gpfsperf create seq myfilefoo1
  recSize 8M nBytes 200G fileSize 200G
  nProcesses 1 nThreadsPerProcess 12
  file cache flushed before test
  not using direct I/O
  offsets accessed will cycle through the same file segment
  not using shared memory buffer
  not releasing byte-range token after open
  no fsync at end of test
    Data rate was 5089216.97 Kbytes/sec, Op Rate was 606.68 Ops/sec, Avg Latency was 19.350 milliseconds, thread utilization 0.978, bytesTransferred 214748364800
"""

# Older GPFS 3.x / early 4.x format — "iops was" with CPU line
_IOPS_OUTPUT = """\
/usr/lpp/mmfs/samples/perf/gpfsperf write seq /gpfs/testfile
  recSize 8M nBytes 10G fileSize 10G
  nProcesses 1 nThreadsPerProcess 1
    Data rate was 2330376.56 Kbytes/sec, iops was 284.47, thread utilization 1.000
    CPU utilization: user 3.01%, sys 3.24%, idle 93.75%, wait 0.00%
"""

# Minimal format — no IOPS or latency
_MINIMAL_OUTPUT = """\
/usr/lpp/mmfs/samples/perf/gpfsperf read seq /gpfs/testfile
  recSize 1M nBytes 16G fileSize 16G
  nProcesses 1 nThreadsPerProcess 1
  file cache flushed before test
    Data rate was 83583.30 Kbytes/sec, thread utilization 1.000
"""

# MPI variant
_MPI_OUTPUT = """\
/u/herbertm/gpfsperf/gpfsperf-mpi read strided /fsB/testfile
  recSize 256K nBytes 999M fileSize 999M
  nProcesses 5 nThreadsPerProcess 1
  file cache flushed before test
  not using data shipping
    Data rate was 107625.91 Kbytes/sec, thread utilization 0.911
"""

_NO_RESULT = """\
/usr/lpp/mmfs/samples/perf/gpfsperf create seq /gpfs/testfile
  recSize 1M nBytes 1G fileSize 1G
  nProcesses 1 nThreadsPerProcess 1
gpfsperf: open /gpfs/testfile: Permission denied
"""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def test_gpfsperf_registered():
    assert "gpfsperf" in REGISTRY


# ---------------------------------------------------------------------------
# Full (Spectrum Scale) format
# ---------------------------------------------------------------------------

def test_full_passed():
    r = get_parser("gpfsperf").parse(_FULL_OUTPUT)
    assert r.status == "PASSED"


def test_full_throughput():
    r = get_parser("gpfsperf").parse(_FULL_OUTPUT)
    # 5089216.97 Kbytes/sec / 1024 = 4970.72... MB/s
    assert r.metrics["throughput_MB_s"] == pytest.approx(5089216.97 / 1024.0)


def test_full_iops():
    r = get_parser("gpfsperf").parse(_FULL_OUTPUT)
    assert r.metrics["iops"] == pytest.approx(606.68)


def test_full_latency():
    r = get_parser("gpfsperf").parse(_FULL_OUTPUT)
    assert r.metrics["latency_avg_ms"] == pytest.approx(19.350)


def test_full_thread_utilization():
    r = get_parser("gpfsperf").parse(_FULL_OUTPUT)
    assert r.metrics["thread_utilization"] == pytest.approx(0.978)


def test_full_bytes_transferred():
    r = get_parser("gpfsperf").parse(_FULL_OUTPUT)
    assert r.metrics["bytes_transferred"] == pytest.approx(214748364800.0)


def test_full_nthreads():
    r = get_parser("gpfsperf").parse(_FULL_OUTPUT)
    assert r.metrics["nprocesses"] == pytest.approx(1.0)
    assert r.metrics["nthreads_per_process"] == pytest.approx(12.0)


def test_full_operation_in_detail():
    r = get_parser("gpfsperf").parse(_FULL_OUTPUT)
    assert "create" in r.status_detail
    assert "seq" in r.status_detail


# ---------------------------------------------------------------------------
# Older "iops was" format with CPU line
# ---------------------------------------------------------------------------

def test_iops_format_passed():
    r = get_parser("gpfsperf").parse(_IOPS_OUTPUT)
    assert r.status == "PASSED"


def test_iops_format_throughput():
    r = get_parser("gpfsperf").parse(_IOPS_OUTPUT)
    assert r.metrics["throughput_MB_s"] == pytest.approx(2330376.56 / 1024.0)


def test_iops_format_iops():
    r = get_parser("gpfsperf").parse(_IOPS_OUTPUT)
    assert r.metrics["iops"] == pytest.approx(284.47)


def test_iops_format_no_latency():
    r = get_parser("gpfsperf").parse(_IOPS_OUTPUT)
    assert "latency_avg_ms" not in r.metrics


def test_cpu_utilization():
    r = get_parser("gpfsperf").parse(_IOPS_OUTPUT)
    assert r.metrics["cpu_user_pct"] == pytest.approx(3.01)
    assert r.metrics["cpu_sys_pct"] == pytest.approx(3.24)
    assert r.metrics["cpu_idle_pct"] == pytest.approx(93.75)
    assert r.metrics["cpu_wait_pct"] == pytest.approx(0.00)


# ---------------------------------------------------------------------------
# Minimal format
# ---------------------------------------------------------------------------

def test_minimal_passed():
    r = get_parser("gpfsperf").parse(_MINIMAL_OUTPUT)
    assert r.status == "PASSED"


def test_minimal_throughput():
    r = get_parser("gpfsperf").parse(_MINIMAL_OUTPUT)
    assert r.metrics["throughput_MB_s"] == pytest.approx(83583.30 / 1024.0)


def test_minimal_no_iops():
    r = get_parser("gpfsperf").parse(_MINIMAL_OUTPUT)
    assert "iops" not in r.metrics


# ---------------------------------------------------------------------------
# MPI variant
# ---------------------------------------------------------------------------

def test_mpi_passed():
    r = get_parser("gpfsperf").parse(_MPI_OUTPUT)
    assert r.status == "PASSED"


def test_mpi_nprocesses():
    r = get_parser("gpfsperf").parse(_MPI_OUTPUT)
    assert r.metrics["nprocesses"] == pytest.approx(5.0)


def test_mpi_throughput():
    r = get_parser("gpfsperf").parse(_MPI_OUTPUT)
    assert r.metrics["throughput_MB_s"] == pytest.approx(107625.91 / 1024.0)


# ---------------------------------------------------------------------------
# Error / edge cases
# ---------------------------------------------------------------------------

def test_not_started():
    r = get_parser("gpfsperf").parse(_NO_RESULT)
    assert r.status == "NOTSTARTED"


def test_empty_output():
    r = get_parser("gpfsperf").parse("")
    assert r.status == "NOTSTARTED"


def test_notice():
    r = get_parser("gpfsperf").parse("CBENCH NOTICE something\n")
    assert r.status == "NOTICE"


# ---------------------------------------------------------------------------
# metric_units
# ---------------------------------------------------------------------------

def test_metric_units():
    units = get_parser("gpfsperf").metric_units()
    assert units["throughput_MB_s"] == "MB/s"
    assert units["iops"] == "ops/s"
    assert units["latency_avg_ms"] == "ms"
    assert units["thread_utilization"] == "fraction"
    assert units["cpu_user_pct"] == "%"
