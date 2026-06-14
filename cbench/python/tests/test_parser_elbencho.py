"""Tests for the elbencho distributed storage benchmark parser."""

import pytest
from cbench.parsers import get_parser, REGISTRY

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_WRITE_READ = """\
OPERATION RESULT TYPE        FIRST DONE  LAST DONE
=========== ================    ==========  =========
WRITE     Elapsed time     :    2m3.241s    2m5.755s
          IOPS             :       33395       33352
          Throughput MiB/s :       33395       33352
          Total MiB        :     4115703     4194304
---
READ      Elapsed time     :   1m58.012s   1m59.001s
          IOPS             :       31000       30500
          Throughput MiB/s :       31000       30500
          Total MiB        :     3900000     3950000
---
"""

_WITH_LATENCY = """\
OPERATION RESULT TYPE        FIRST DONE  LAST DONE
=========== ================    ==========  =========
WRITE     Elapsed time     :      30.500s     30.800s
          IOPS             :        1024        1000
          Throughput MiB/s :        1024        1000
          FILE latency     : [ min=123us avg=456us max=1.23ms ]
---
READ      Elapsed time     :      28.100s     28.500s
          IOPS             :        2048        2000
          Throughput MiB/s :        2048        2000
          FILE latency     : [ min=100us avg=300us max=900us ]
---
"""

_METADATA_ONLY = """\
OPERATION RESULT TYPE        FIRST DONE  LAST DONE
=========== ================    ==========  =========
MKDIRS    Elapsed time     :       5.123s      5.234s
          FILES/s          :       65000       64000
---
STAT      Elapsed time     :       3.456s      3.789s
          FILES/s          :      120000      118000
---
"""

_MIXED_RW = """\
OPERATION RESULT TYPE        FIRST DONE  LAST DONE
=========== ================    ==========  =========
WRITE     Elapsed time     :    500ms        510ms
          IOPS write       :         500         490
          IOPS read        :         400         390
          IOPS total       :         900         880
          MiB/s write      :         500         490
          MiB/s read       :         400         390
          MiB/s total      :         900         880
---
"""

_ERROR_OUTPUT = """\
ERROR: Could not connect to worker service on host node02
"""

_NO_HEADER = """\
Starting elbencho run...
Some other output without the results table.
"""

_HOURS_ELAPSED = """\
OPERATION RESULT TYPE        FIRST DONE  LAST DONE
=========== ================    ==========  =========
WRITE     Elapsed time     :   1h2m3.000s  1h2m5.000s
          Throughput MiB/s :        5000        4990
---
"""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def test_elbencho_registered():
    assert "elbencho" in REGISTRY


# ---------------------------------------------------------------------------
# Basic write/read run
# ---------------------------------------------------------------------------

def test_write_read_passed():
    r = get_parser("elbencho").parse(_WRITE_READ)
    assert r.status == "PASSED"


def test_write_throughput():
    r = get_parser("elbencho").parse(_WRITE_READ)
    assert r.metrics["write_throughput_MiB_s"] == pytest.approx(33352.0)


def test_read_throughput():
    r = get_parser("elbencho").parse(_WRITE_READ)
    assert r.metrics["read_throughput_MiB_s"] == pytest.approx(30500.0)


def test_write_iops():
    r = get_parser("elbencho").parse(_WRITE_READ)
    assert r.metrics["write_iops"] == pytest.approx(33352.0)


def test_read_iops():
    r = get_parser("elbencho").parse(_WRITE_READ)
    assert r.metrics["read_iops"] == pytest.approx(30500.0)


def test_write_elapsed():
    r = get_parser("elbencho").parse(_WRITE_READ)
    # 2m5.755s = 125.755s
    assert r.metrics["write_elapsed_s"] == pytest.approx(125.755)


def test_read_elapsed():
    r = get_parser("elbencho").parse(_WRITE_READ)
    # 1m59.001s = 119.001s
    assert r.metrics["read_elapsed_s"] == pytest.approx(119.001)


def test_total_mib():
    r = get_parser("elbencho").parse(_WRITE_READ)
    assert r.metrics["write_total_MiB"] == pytest.approx(4194304.0)
    assert r.metrics["read_total_MiB"] == pytest.approx(3950000.0)


# ---------------------------------------------------------------------------
# Latency metrics
# ---------------------------------------------------------------------------

def test_latency_parsed():
    r = get_parser("elbencho").parse(_WITH_LATENCY)
    assert r.status == "PASSED"
    assert r.metrics["write_lat_min_us"] == pytest.approx(123.0)
    assert r.metrics["write_lat_avg_us"] == pytest.approx(456.0)
    assert r.metrics["write_lat_max_us"] == pytest.approx(1230.0)   # 1.23ms → 1230us
    assert r.metrics["read_lat_min_us"] == pytest.approx(100.0)
    assert r.metrics["read_lat_avg_us"] == pytest.approx(300.0)
    assert r.metrics["read_lat_max_us"] == pytest.approx(900.0)


# ---------------------------------------------------------------------------
# Metadata-only run (MKDIRS, STAT)
# ---------------------------------------------------------------------------

def test_metadata_phases():
    r = get_parser("elbencho").parse(_METADATA_ONLY)
    assert r.status == "PASSED"
    assert r.metrics["mkdirs_ops_per_s"] == pytest.approx(64000.0)
    assert r.metrics["stat_ops_per_s"] == pytest.approx(118000.0)


# ---------------------------------------------------------------------------
# Mixed read/write totals
# ---------------------------------------------------------------------------

def test_mixed_rw_totals():
    r = get_parser("elbencho").parse(_MIXED_RW)
    assert r.status == "PASSED"
    assert r.metrics["write_iops_total"] == pytest.approx(880.0)
    assert r.metrics["write_throughput_total_MiB_s"] == pytest.approx(880.0)


# ---------------------------------------------------------------------------
# Elapsed time edge cases
# ---------------------------------------------------------------------------

def test_hours_elapsed():
    r = get_parser("elbencho").parse(_HOURS_ELAPSED)
    # 1h2m5.000s = 3600 + 120 + 5 = 3725s
    assert r.metrics["write_elapsed_s"] == pytest.approx(3725.0)


# ---------------------------------------------------------------------------
# Error and edge cases
# ---------------------------------------------------------------------------

def test_error_line():
    r = get_parser("elbencho").parse(_ERROR_OUTPUT)
    assert r.status.startswith("ERROR(RUNTIME)")
    assert "node02" in r.status_detail


def test_not_started():
    r = get_parser("elbencho").parse(_NO_HEADER)
    assert r.status == "NOTSTARTED"


def test_notice():
    r = get_parser("elbencho").parse("CBENCH NOTICE something\n")
    assert r.status == "NOTICE"


# ---------------------------------------------------------------------------
# metric_units
# ---------------------------------------------------------------------------

def test_metric_units():
    units = get_parser("elbencho").metric_units()
    assert units["write_throughput_MiB_s"] == "MiB/s"
    assert units["read_iops"] == "IOPS"
    assert units["write_lat_avg_us"] == "us"
    assert units["write_elapsed_s"] == "seconds"
