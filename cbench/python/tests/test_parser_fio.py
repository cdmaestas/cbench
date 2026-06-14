"""Tests for the fio Flexible I/O Tester parser."""

import pytest
from cbench.parsers import get_parser, REGISTRY

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_READ_ONLY = """\
fio-3.33
Starting 4 processes
read: IOPS=316k, BW=1234MiB/s (1294MB/s)(72.3GiB/60001msec)
   clat (usec): min=2, avg=12.34, stdev=5.67, max=1234
  clat percentiles (usec):
   |  1.00th=[    4],  5.00th=[    5], 10.00th=[    6], 20.00th=[    8],
   | 50.00th=[   10], 75.00th=[   15], 90.00th=[   20], 95.00th=[   25],
   | 99.00th=[   50], 99.50th=[   75], 99.90th=[  100], 99.99th=[  200]

Run status group 0 (all jobs):
   READ: bw=1234MiB/s (1294MB/s), 308MiB/s-309MiB/s (323MB/s-324MB/s), io=72.3GiB (77.6GB), run=60001-60001msec
"""

_WRITE_ONLY = """\
write: IOPS=100k, BW=400MiB/s (419MB/s)(24.0GiB/60001msec)
   clat (usec): min=3, avg=20.00, stdev=8.00, max=2000
  clat percentiles (usec):
   |  1.00th=[    5], 50.00th=[   18], 99.00th=[   80], 99.99th=[  500]

Run status group 0 (all jobs):
  WRITE: bw=400MiB/s (419MB/s), 100MiB/s-100MiB/s, io=24.0GiB, run=60001-60001msec
"""

_MIXED_RW = """\
read: IOPS=200k, BW=800MiB/s (839MB/s)(48.0GiB/60001msec)
   clat (usec): min=2, avg=10.00, stdev=4.00, max=500
  clat percentiles (usec):
   |  1.00th=[    3], 99.00th=[   30], 99.99th=[  100]
write: IOPS=50k, BW=200MiB/s (209MB/s)(12.0GiB/60001msec)
   clat (usec): min=5, avg=25.00, stdev=10.00, max=1000
  clat percentiles (usec):
   |  1.00th=[    8], 99.00th=[  100], 99.99th=[  500]

Run status group 0 (all jobs):
   READ: bw=800MiB/s (839MB/s), io=48.0GiB, run=60001-60001msec
  WRITE: bw=200MiB/s (209MB/s), io=12.0GiB, run=60001-60001msec
"""

_MSEC_LATENCY = """\
read: IOPS=500, BW=500MiB/s (524MB/s)(29.3GiB/60001msec)
   clat (msec): min=1, avg=5.23, stdev=2.00, max=50
  clat percentiles (msec):
   |  1.00th=[    2], 50.00th=[    5], 99.00th=[   20], 99.99th=[   45]

Run status group 0 (all jobs):
   READ: bw=500MiB/s (524MB/s), io=29.3GiB, run=60001-60001msec
"""

_GIB_BW = """\
read: IOPS=500k, BW=2.00GiB/s (2.15GB/s)(120GiB/60001msec)
   clat (usec): min=1, avg=8.00, stdev=2.00, max=200
  clat percentiles (usec):
   |  1.00th=[    2], 99.00th=[   20], 99.99th=[   80]

Run status group 0 (all jobs):
   READ: bw=2.00GiB/s (2.15GB/s), io=120GiB, run=60001-60001msec
"""

_EMPTY = "fio-3.33\nStarting 1 process\n"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def test_fio_registered():
    assert "fio" in REGISTRY


# ---------------------------------------------------------------------------
# Read-only run
# ---------------------------------------------------------------------------

def test_read_passed():
    r = get_parser("fio").parse(_READ_ONLY)
    assert r.status == "PASSED"


def test_read_iops():
    r = get_parser("fio").parse(_READ_ONLY)
    assert r.metrics["read_iops"] == pytest.approx(316e3)


def test_read_bw():
    r = get_parser("fio").parse(_READ_ONLY)
    assert r.metrics["read_bw_MiB_s"] == pytest.approx(1234.0)


def test_read_lat_avg():
    r = get_parser("fio").parse(_READ_ONLY)
    assert r.metrics["read_lat_avg_us"] == pytest.approx(12.34)


def test_read_lat_p99():
    r = get_parser("fio").parse(_READ_ONLY)
    assert r.metrics["read_lat_p99_us"] == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# Write-only run
# ---------------------------------------------------------------------------

def test_write_passed():
    r = get_parser("fio").parse(_WRITE_ONLY)
    assert r.status == "PASSED"


def test_write_iops():
    r = get_parser("fio").parse(_WRITE_ONLY)
    assert r.metrics["write_iops"] == pytest.approx(100e3)


def test_write_bw():
    r = get_parser("fio").parse(_WRITE_ONLY)
    assert r.metrics["write_bw_MiB_s"] == pytest.approx(400.0)


def test_write_lat_p99():
    r = get_parser("fio").parse(_WRITE_ONLY)
    assert r.metrics["write_lat_p99_us"] == pytest.approx(80.0)


# ---------------------------------------------------------------------------
# Mixed read/write
# ---------------------------------------------------------------------------

def test_mixed_rw_passed():
    r = get_parser("fio").parse(_MIXED_RW)
    assert r.status == "PASSED"


def test_mixed_read_and_write_metrics():
    r = get_parser("fio").parse(_MIXED_RW)
    assert r.metrics["read_bw_MiB_s"] == pytest.approx(800.0)
    assert r.metrics["write_bw_MiB_s"] == pytest.approx(200.0)
    assert r.metrics["read_lat_p99_us"] == pytest.approx(30.0)
    assert r.metrics["write_lat_p99_us"] == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Latency unit conversion
# ---------------------------------------------------------------------------

def test_msec_latency_converted_to_us():
    r = get_parser("fio").parse(_MSEC_LATENCY)
    # avg=5.23ms → 5230 us
    assert r.metrics["read_lat_avg_us"] == pytest.approx(5230.0)


# ---------------------------------------------------------------------------
# GiB/s bandwidth
# ---------------------------------------------------------------------------

def test_gib_bw_converted_to_mib():
    r = get_parser("fio").parse(_GIB_BW)
    # Run status: 2.00GiB/s = 2048 MiB/s
    assert r.metrics["read_bw_MiB_s"] == pytest.approx(2048.0)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_not_started():
    r = get_parser("fio").parse(_EMPTY)
    assert r.status == "NOTSTARTED"


def test_notice():
    r = get_parser("fio").parse("CBENCH NOTICE something\n")
    assert r.status == "NOTICE"


def test_metric_units():
    units = get_parser("fio").metric_units()
    assert units["read_iops"] == "IOPS"
    assert units["write_bw_MiB_s"] == "MiB/s"
    assert units["read_lat_p99_us"] == "us"
