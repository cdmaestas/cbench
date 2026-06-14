"""Tests for benchmark output parsers."""

import pytest

from cbench.parsers.xhpl import XhplParser
from cbench.parsers.npb import NpbParser
from cbench.parsers.hpcc import HpccParser
from cbench.parsers.ior import IorParser
from cbench.parsers.osu import OsuParser
from cbench.parsers.imb import ImbParser
from cbench.parsers import REGISTRY


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def test_registry_populated():
    assert "xhpl" in REGISTRY
    assert "hpcc" in REGISTRY
    assert "npb" in REGISTRY
    assert "ior" in REGISTRY
    assert "osu" in REGISTRY
    assert "imb" in REGISTRY


# ---------------------------------------------------------------------------
# XHPL
# ---------------------------------------------------------------------------

_XHPL_PASS = """
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
"""

_XHPL_FAIL = """
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
"""

_XHPL_ALLOC = """
matrix A is randomly generated
Memory allocation failed for A, x and b. Skip.
"""

def test_xhpl_passed():
    p = XhplParser()
    r = p.parse(_XHPL_PASS)
    assert r.status == "PASSED"
    assert r.metrics["gflops"] > 0

def test_xhpl_failed_residuals():
    p = XhplParser()
    r = p.parse(_XHPL_FAIL)
    assert "ERROR" in r.status

def test_xhpl_alloc_failure():
    p = XhplParser()
    r = p.parse(_XHPL_ALLOC)
    assert "ERROR" in r.status or "ALLOC" in r.status

def test_xhpl_notstarted():
    p = XhplParser()
    r = p.parse("")
    assert r.status.startswith("ERROR")

def test_xhpl_notice():
    p = XhplParser()
    r = p.parse("CBENCH NOTICE: binary not found\n")
    assert r.status == "NOTICE"


# ---------------------------------------------------------------------------
# NPB
# ---------------------------------------------------------------------------

_NPB_PASS = """
NAS Parallel Benchmarks (NPB3.3) - MG Benchmark
Benchmark Completed.
 Mop/s total     =             1234.56
 Verification    =               SUCCESSFUL
"""

_NPB_FAIL = """
NAS Parallel Benchmarks (NPB3.3) - MG Benchmark
Benchmark Completed.
 Mop/s total     =              500.00
 Verification    =             UNSUCCESSFUL
"""

def test_npb_passed():
    p = NpbParser()
    r = p.parse(_NPB_PASS)
    assert r.status == "PASSED"
    assert abs(r.metrics["mops"] - 1234.56) < 0.01

def test_npb_failed_verification():
    p = NpbParser()
    r = p.parse(_NPB_FAIL)
    assert "ERROR" in r.status

def test_npb_notstarted():
    p = NpbParser()
    r = p.parse("some random output")
    assert r.status.startswith("ERROR")


# ---------------------------------------------------------------------------
# HPCC
# ---------------------------------------------------------------------------

_HPCC_PASS = """
DARPA/DOE HPC Challenge Benchmark version 1.5.0
Begin of Summary section:
HPL_Tflops=0.00234
StarDGEMM_Gflops=12.5
PTRANS_GBs=8.3
StarSTREAM_Triad=15.2
MPIRandomAccess_GUPs=0.001
StarFFT_Gflops=4.2
"""

def test_hpcc_passed():
    p = HpccParser()
    r = p.parse(_HPCC_PASS)
    assert r.status == "PASSED"
    assert abs(r.metrics["hpl"] - 2.34) < 0.01   # Tflops * 1000 = Gflops
    assert r.metrics["ep_dgemm"] == 12.5

def test_hpcc_not_started():
    p = HpccParser()
    r = p.parse("nothing here")
    assert r.status.startswith("ERROR")


# ---------------------------------------------------------------------------
# IOR
# ---------------------------------------------------------------------------

_IOR_PASS = """
Run began: Fri Jan  1 00:00:00 2021
Max Write: 457.22 MiB/sec (479.43 MB/sec)
Max Read:  1028.59 MiB/sec (1078.55 MB/sec)
Run finished: Fri Jan  1 00:01:00 2021
"""

_IOR_OLD = """
Run began: Fri Jan  1 00:00:00 2021
write     200.00    100.00    150.00
read      400.00    200.00    300.00
Run finished: Fri Jan  1 00:01:00 2021
"""

def test_ior_passed():
    p = IorParser()
    r = p.parse(_IOR_PASS)
    assert r.status == "PASSED"
    assert abs(r.metrics["write"] - 479.43) < 0.01
    assert abs(r.metrics["read"] - 1078.55) < 0.01

def test_ior_old_format():
    p = IorParser()
    r = p.parse(_IOR_OLD)
    assert r.status == "PASSED"
    assert r.metrics["write"] == 200.0
    assert r.metrics["read"] == 400.0

def test_ior_not_started():
    p = IorParser()
    r = p.parse("")
    assert r.status.startswith("ERROR")


# ---------------------------------------------------------------------------
# OSU
# ---------------------------------------------------------------------------

_OSU_BW = """
OSU MPI Bandwidth Test
# Size      Bandwidth (MB/s)
4           100.00
65536       9500.25
4194304     11234.56
"""

_OSU_LAT = """
OSU MPI Latency Test
# Size          Latency (us)
0               0.52
4               0.60
65536           10.3
"""

def test_osu_bandwidth():
    p = OsuParser()
    r = p.parse(_OSU_BW)
    assert r.status == "PASSED"
    assert r.metrics["unidir_bw"] == pytest.approx(11234.56)

def test_osu_latency():
    p = OsuParser()
    r = p.parse(_OSU_LAT)
    assert r.status == "PASSED"
    assert r.metrics["latency"] == pytest.approx(0.52)


# ---------------------------------------------------------------------------
# IMB
# ---------------------------------------------------------------------------

_IMB_OUTPUT = """
#---------------------------------------------------
# Benchmarking PingPong
#---------------------------------------------------
       0          1        0.52      9500.25     9400.12
    4096          1        1.20      8200.34     8100.00
"""

def test_imb_parsed():
    p = ImbParser()
    r = p.parse(_IMB_OUTPUT)
    assert r.status == "PASSED"
    assert "PingPong_lat_us" in r.metrics
