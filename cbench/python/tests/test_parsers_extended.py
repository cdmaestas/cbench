"""Tests for the 16 newly-ported benchmark parsers."""

import pytest
from cbench.parsers import REGISTRY, get_parser


# ---------------------------------------------------------------------------
# Registry completeness
# ---------------------------------------------------------------------------

_EXPECTED = [
    "amg", "beff", "bonnie", "com", "fileop", "graph500", "hpccg", "irs",
    "lammps", "laten", "mdtest", "miranda", "mpibench", "mpigraph",
    "phdmesh", "rotate", "rotlat", "routecheck", "sppm", "sqmr",
    "stress", "sweep3d", "trilinos",
]

@pytest.mark.parametrize("name", _EXPECTED)
def test_registry_has(name):
    assert name in REGISTRY, f"Parser '{name}' not registered"


# ---------------------------------------------------------------------------
# AMG
# ---------------------------------------------------------------------------

_AMG_PASS = """
===== solver 3 ===
SStruct Interface
System Size * Iterations / Solve Phase Time: 1234567.89
===== solver 4 ===
SStruct Interface
System Size * Iterations / Solve Phase Time: 9876543.21
"""

def test_amg_passed():
    p = get_parser("amg")
    r = p.parse(_AMG_PASS)
    assert r.status == "PASSED"
    assert r.metrics["solver3_fom"] == pytest.approx(1234567.89)
    assert r.metrics["solver4_fom"] == pytest.approx(9876543.21)

def test_amg_partial_failure():
    p = get_parser("amg")
    r = p.parse("===== solver 3 ===\nSStruct Interface\n")
    assert "ERROR" in r.status


# ---------------------------------------------------------------------------
# beff
# ---------------------------------------------------------------------------

_BEFF_PASS = """
[00] initialization
b_eff_bcast = 4567.89 MB/s = ...
b_eff     = 4200.00 MB/s = ...
"""

def test_beff_passed():
    p = get_parser("beff")
    r = p.parse(_BEFF_PASS)
    assert r.status == "PASSED"
    assert "bidir_bw" in r.metrics

def test_beff_notice():
    p = get_parser("beff")
    r = p.parse("needs at least two parallel MPI processes")
    assert r.status == "NOTICE"


# ---------------------------------------------------------------------------
# Bonnie
# ---------------------------------------------------------------------------

_BONNIE_PASS = """
Writing with putc()...
Version 1.97      ------Sequential Output------ --Sequential Input- --Random-
tb6,16G,87042,99,128721,98,85973,97,78972,98,218669,95,156.2,0,16,1551,15,1615,31,1593,9,1923,14,1578,34,1669,6
"""

def test_bonnie_passed():
    p = get_parser("bonnie")
    r = p.parse(_BONNIE_PASS)
    assert r.status == "PASSED"
    assert r.metrics["sequential_write_char"] == pytest.approx(87042.0)
    assert r.metrics["random_seeks"] == pytest.approx(156.2)


# ---------------------------------------------------------------------------
# COM
# ---------------------------------------------------------------------------

_COM_PASS = """
Unidirectional and Bidirectional Communication Test
Max Unidirectional : 9500.0 for ...
Max  Bidirectional : 18000.0 for ...
"""

def test_com_passed():
    p = get_parser("com")
    r = p.parse(_COM_PASS)
    assert r.status == "PASSED"
    assert r.metrics["unidir_bw"] == pytest.approx(9500.0)
    assert r.metrics["bidir_bw"] == pytest.approx(18000.0)


# ---------------------------------------------------------------------------
# fileop
# ---------------------------------------------------------------------------

_FILEOP_PASS = """
Fileop: Working in /scratch A=Avg, B=Best, W=Worst
...
Worst delete 1234
"""

def test_fileop_passed():
    p = get_parser("fileop")
    r = p.parse(_FILEOP_PASS)
    assert r.status == "PASSED"


# ---------------------------------------------------------------------------
# Graph500
# ---------------------------------------------------------------------------

_GRAPH500_PASS = """
Running BFS 0
stddev_validate: 0.001
harmonic_mean_TEPS: 1.23e+09 TEPS
median_TEPS: 1.10e+09 TEPS
construction_time: 5.4 s
"""

def test_graph500_passed():
    p = get_parser("graph500")
    r = p.parse(_GRAPH500_PASS)
    assert r.status == "PASSED"
    assert r.metrics["harmonic_mean_teps"] == pytest.approx(1.23e9)
    assert r.metrics["construction_time"] == pytest.approx(5.4)


# ---------------------------------------------------------------------------
# HPCCG
# ---------------------------------------------------------------------------

_HPCCG_PASS = """
Process 0 of 4 is alive.
Total  Time/FLOPS/MFLOPS = 2.345/1.234e+09/4567.89.
Difference between computed and exact = 1.23e-14.
"""

def test_hpccg_passed():
    p = get_parser("hpccg")
    r = p.parse(_HPCCG_PASS)
    assert r.status == "PASSED"
    assert r.metrics["mflops"] == pytest.approx(4567.89)


# ---------------------------------------------------------------------------
# IRS
# ---------------------------------------------------------------------------

_IRS_PASS = """
IRS Sequoia Benchmark v1.0
BENCHMARK microseconds per zone-iteration = 1.5e-04
BENCHMARK FOM = 9876543.0
BENCHMARK CORRECTNESS : PASSED
"""

def test_irs_passed():
    p = get_parser("irs")
    r = p.parse(_IRS_PASS)
    assert r.status == "PASSED"
    assert r.metrics["fom"] == pytest.approx(9876543.0)
    assert r.metrics["zonetime"] == pytest.approx(0.15)  # us

def test_irs_failed():
    p = get_parser("irs")
    r = p.parse("IRS Sequoia Benchmark v1.0\nBENCHMARK CORRECTNESS : FAILED\n")
    assert "ERROR" in r.status


# ---------------------------------------------------------------------------
# LAMMPS
# ---------------------------------------------------------------------------

_LAMMPS_PASS = """
LAMMPS (10 Feb 2015)
Memory usage per processor = 12.34 MB
Dangerous builds = 0
"""

def test_lammps_passed():
    p = get_parser("lammps")
    r = p.parse(_LAMMPS_PASS)
    assert r.status == "PASSED"
    assert r.metrics["memory"] == pytest.approx(12.34)


# ---------------------------------------------------------------------------
# laten
# ---------------------------------------------------------------------------

_LATEN_PASS = """
MPI Bidir latency test
Processes
          4        1.234
         16        2.345
Test Parameters: ...
"""

def test_laten_passed():
    p = get_parser("laten")
    r = p.parse(_LATEN_PASS)
    assert r.status == "PASSED"
    assert r.metrics["latency"] == pytest.approx(1.234)


# ---------------------------------------------------------------------------
# mdtest
# ---------------------------------------------------------------------------

_MDTEST_PASS = """
mdtest_v1.9.3 was launched
SUMMARY: (of 50 iterations)
   Operation                  Max        Min       Mean    Std Dev
   Directory creation:   9273.825   6788.107   8343.664    668.352
   Directory stat    :   5502.662   5106.717   5300.309     77.801
   Directory removal :   6128.883   5015.467   5705.629    263.386
   File creation     :   7412.247   6136.470   6833.696    292.678
   File stat         :   5517.454   5035.605   5261.947     99.959
   File removal      :   4813.524   4207.714   4505.605    125.475
"""

def test_mdtest_passed():
    p = get_parser("mdtest")
    r = p.parse(_MDTEST_PASS)
    assert r.status == "PASSED"
    assert r.metrics["directory_create"] == pytest.approx(8343.664)
    assert r.metrics["file_create"] == pytest.approx(6833.696)


# ---------------------------------------------------------------------------
# Miranda
# ---------------------------------------------------------------------------

_MIRANDA_PASS = """
test emulating Bill Cabots code and bz4410
Overall Transfer Rate = 1234.56 MiB/s
all done
"""

def test_miranda_passed():
    p = get_parser("miranda")
    r = p.parse(_MIRANDA_PASS)
    assert r.status == "PASSED"
    assert r.metrics["rate"] == pytest.approx(1234.56)


# ---------------------------------------------------------------------------
# mpiBench
# ---------------------------------------------------------------------------

_MPIBENCH_PASS = """
START mpiBench
Barrier                 Bytes:        0        Iters:     1000 Avg:      1.2340        Min:      1.2300 Max:      1.2400        Comm: MPI_COMM_WORLD    Ranks: 4
Bcast                   Bytes:     8192        Iters:     1000 Avg:      5.6780        Min:      5.5000 Max:      5.8000        Comm: MPI_COMM_WORLD    Ranks: 4
Allreduce               Bytes:     8192        Iters:     1000 Avg:      2.3456        Min:      2.3000 Max:      2.4000        Comm: MPI_COMM_WORLD    Ranks: 4
END mpiBench
"""

def test_mpibench_passed():
    p = get_parser("mpibench")
    r = p.parse(_MPIBENCH_PASS)
    assert r.status == "PASSED"
    assert r.metrics["Barrier"] == pytest.approx(1.234)
    assert r.metrics["Allreduce"] == pytest.approx(2.3456)


# ---------------------------------------------------------------------------
# mpiGraph
# ---------------------------------------------------------------------------

_MPIGRAPH_PASS = """
START mpiGraph
Send MB/sec min: 8900.0
Send MB/sec max: 11000.0
Recv MB/sec min: 8800.0
END mpiGraph
"""

def test_mpigraph_passed():
    p = get_parser("mpigraph")
    r = p.parse(_MPIGRAPH_PASS)
    assert r.status == "PASSED"
    assert r.metrics["send_min"] == pytest.approx(8900.0)
    assert r.metrics["recv_min"] == pytest.approx(8800.0)


# ---------------------------------------------------------------------------
# phdmesh
# ---------------------------------------------------------------------------

_PHDMESH_PASS = """
GEARS meshing test
N_GEARS Performance results
Search/step = 0.0123 sec
Rebalance   = 0.0045 sec
"""

def test_phdmesh_passed():
    p = get_parser("phdmesh")
    r = p.parse(_PHDMESH_PASS)
    assert r.status == "PASSED"
    assert r.metrics["search"] == pytest.approx(0.0123)
    assert r.metrics["rebalance"] == pytest.approx(0.0045)


# ---------------------------------------------------------------------------
# rotate
# ---------------------------------------------------------------------------

_ROTATE_PASS = """
rotate 0
Min Unidirectional BW : 8900.0 MB/s
Max Unidirectional BW : 11000.0 MB/s
Average Link Unidirectional BW : 9500.0 MB/s
Average Aggregate Unidirectional BW : 75000.0 MB/s
"""

def test_rotate_passed():
    p = get_parser("rotate")
    r = p.parse(_ROTATE_PASS)
    assert r.status == "PASSED"
    assert r.metrics["min_link_bw"] == pytest.approx(8900.0)
    assert r.metrics["aggregate_bw"] == pytest.approx(75000.0)

def test_rotate_notice():
    p = get_parser("rotate")
    r = p.parse("Must use at least 2 processes")
    assert r.status == "NOTICE"


# ---------------------------------------------------------------------------
# rotlat
# ---------------------------------------------------------------------------

_ROTLAT_PASS = """
rotate 0
Min Link Latency : 1.23 us
Max Link Latency : 2.34 us
Average Link Latency : 1.56 us
"""

def test_rotlat_passed():
    p = get_parser("rotlat")
    r = p.parse(_ROTLAT_PASS)
    assert r.status == "PASSED"
    assert r.metrics["min_latency"] == pytest.approx(1.23)


# ---------------------------------------------------------------------------
# routecheck
# ---------------------------------------------------------------------------

_ROUTECHECK_PASS = """
Timing resolution ...
dealer node is now rank 0
dealer node is now rank 1
Total time = 12.34
Avg loop time = 0.0056
"""

def test_routecheck_passed():
    p = get_parser("routecheck")
    r = p.parse(_ROUTECHECK_PASS)
    assert r.status == "PASSED"
    assert r.metrics["totaltime"] == pytest.approx(12.34)
    assert r.metrics["ave_looptime"] == pytest.approx(0.0056)


# ---------------------------------------------------------------------------
# sPPM
# ---------------------------------------------------------------------------

_SPPM_PASS = """
sPPM Benchmark
TOTAL-I/O cpu, wall, ratio: 1.23 4.56 0.27
Finished Calculation
"""

def test_sppm_passed():
    p = get_parser("sppm")
    r = p.parse(_SPPM_PASS)
    assert r.status == "PASSED"
    assert r.metrics["io_cpu_time"] == pytest.approx(1.23)


# ---------------------------------------------------------------------------
# SQMR
# ---------------------------------------------------------------------------

_SQMR_PASS = """
SQMR v1 benchmark
0 10000  0.01   1781096.44    0.00   1900000.0    0.00   1600000.0    0.00
Cbench end timestamp: 12345
"""

def test_sqmr_passed():
    p = get_parser("sqmr")
    r = p.parse(_SQMR_PASS)
    assert r.status == "PASSED"
    assert r.metrics["message_rate"] == pytest.approx(1900000.0)


# ---------------------------------------------------------------------------
# stress
# ---------------------------------------------------------------------------

_STRESS_PASS = """
All to All non-blocking
stress runs 100 [9876.54 MB/s aggregate]
Stress completed
"""

def test_stress_passed():
    p = get_parser("stress")
    r = p.parse(_STRESS_PASS)
    assert r.status == "PASSED"
    assert r.metrics["ave_alltoall"] == pytest.approx(9876.54)

def test_stress_corruption():
    p = get_parser("stress")
    r = p.parse("All to All non-blocking\nMessage from node1 is corrupt\n")
    assert "ERROR" in r.status


# ---------------------------------------------------------------------------
# SWEEP3D
# ---------------------------------------------------------------------------

_SWEEP3D_PASS = """
SWEEP3D - Method 5 - Pipelined Wavefront with Line-Recursion
CPU  time was: 45.67
CPU grind time: 0.0034
Elapsed time
"""

def test_sweep3d_passed():
    p = get_parser("sweep3d")
    r = p.parse(_SWEEP3D_PASS)
    assert r.status == "PASSED"
    assert r.metrics["cpu_time"] == pytest.approx(45.67)
    assert r.metrics["cpu_grind_time"] == pytest.approx(0.0034)


# ---------------------------------------------------------------------------
# Trilinos
# ---------------------------------------------------------------------------

_TRILINOS_PASS = """
Epetra Benchmark Test Version 2.0
MFLOP/s  4  1234.5  2345.6  3456.7  4567.8  5678.9  6789.0  7890.1
"""

def test_trilinos_passed():
    p = get_parser("trilinos")
    r = p.parse(_TRILINOS_PASS)
    assert r.status == "PASSED"
    assert r.metrics["SpMV"] == pytest.approx(1234.5)
    assert r.metrics["AXPY"] == pytest.approx(7890.1)

def test_trilinos_not_started():
    p = get_parser("trilinos")
    r = p.parse("nothing here")
    assert r.status.startswith("ERROR")
