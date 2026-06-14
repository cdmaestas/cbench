"""Tests for the 14 new hw_test parsers and mpioverhead output parser."""

import textwrap
import pytest
from cbench.hw_tests import REGISTRY, get_hw_test
from cbench.parsers import get_parser


# ---------------------------------------------------------------------------
# Registry completeness
# ---------------------------------------------------------------------------

_NEW_HW_TESTS = [
    "cachebench", "ctcs_memtst", "fpck", "ibport", "idle",
    "matmult", "mpqc", "numa_gpu", "numa_mem", "omdiag",
    "psnap", "stride", "topspin", "xhpl2",
]


@pytest.mark.parametrize("name", _NEW_HW_TESTS)
def test_hw_registry_has(name):
    assert name in REGISTRY


def test_parser_registry_has_mpioverhead():
    assert "mpioverhead" in REGISTRY or get_parser("mpioverhead") is not None


def test_parser_registry_has_ohead_alias():
    assert get_parser("ohead") is not None


# ---------------------------------------------------------------------------
# mpioverhead output parser
# ---------------------------------------------------------------------------

_MPIOVERHEAD_PASS = textwrap.dedent("""\
    Timestamp before MPI launch = 1000
    Rank 0: MPI launch timestamp = 1005
    Rank 0 (node01): mem used blah = 512 blah = 524288 kB
    Rank 1 (node01): mem used blah = 512 blah = 524288 kB
""")

_MPIOVERHEAD_NOTSTARTED = "No useful output here\n"

_MPIOVERHEAD_NOTICE = "CBENCH NOTICE: job was cancelled\n"


def test_mpioverhead_pass():
    p = get_parser("mpioverhead")
    r = p.parse(_MPIOVERHEAD_PASS)
    assert r.status == "PASSED"
    assert r.metrics["launch_time"] == 5
    assert r.metrics["ave_mpi_mem"] == pytest.approx(0.5)


def test_mpioverhead_notstarted():
    p = get_parser("mpioverhead")
    r = p.parse(_MPIOVERHEAD_NOTSTARTED)
    assert r.status.startswith("ERROR")


def test_mpioverhead_notice():
    p = get_parser("ohead")
    r = p.parse(_MPIOVERHEAD_NOTICE)
    assert r.status == "NOTICE"


# ---------------------------------------------------------------------------
# cachebench
# ---------------------------------------------------------------------------

_CACHEBENCH = textwrap.dedent("""\
    ====> read
    1000 150.5
    2000 200.3
    3000 180.0
    ====> write
    1000 90.1
    2000 95.7
""").splitlines()


def test_cachebench_parse():
    hw = get_hw_test("cachebench")
    data = hw.parse(_CACHEBENCH)
    assert data["cachebench_read"] == pytest.approx(200.3)
    assert data["cachebench_write"] == pytest.approx(95.7)


# ---------------------------------------------------------------------------
# ctcs_memtst
# ---------------------------------------------------------------------------

_CTCS_PASS = textwrap.dedent("""\
    ====> process 1/2 begin
    Ceiling test starting
    OK.
    ====> process 1/2 end
    ====> process 2/2 begin
    Ceiling test starting
    OK.
    ====> process 2/2 end
""").splitlines()

_CTCS_FAIL = textwrap.dedent("""\
    ====> process 1/1 begin
    Ceiling test starting
    Failure
    ====> process 1/1 end
""").splitlines()


def test_ctcs_memtst_pass():
    hw = get_hw_test("ctcs_memtst")
    data = hw.parse(_CTCS_PASS)
    assert data["ctcs_memtst_fail"] == 0
    assert data["ctcs_memtst_incomplete"] == 0


def test_ctcs_memtst_fail():
    hw = get_hw_test("ctcs_memtst")
    data = hw.parse(_CTCS_FAIL)
    assert data["ctcs_memtst_fail"] == 1


# ---------------------------------------------------------------------------
# fpck
# ---------------------------------------------------------------------------

_FPCK_PASS = textwrap.dedent("""\
    ====> process 1/1 begin
    All checks OK
    ====> process 1/1 end
""").splitlines()

_FPCK_FAIL = textwrap.dedent("""\
    ====> process 1/1 begin
    FAIL: result mismatch
    FAIL: another error
    ====> process 1/1 end
""").splitlines()


def test_fpck_pass():
    hw = get_hw_test("fpck")
    data = hw.parse(_FPCK_PASS)
    assert data["fpck_fail"] == 0


def test_fpck_fail():
    hw = get_hw_test("fpck")
    data = hw.parse(_FPCK_FAIL)
    assert data["fpck_fail"] == 2


# ---------------------------------------------------------------------------
# ibport
# ---------------------------------------------------------------------------

def test_ibport_pass():
    hw = get_hw_test("ibport")
    data = hw.parse(["RESULT: PASSED"])
    assert data["ibport_fail"] == 0


def test_ibport_fail():
    hw = get_hw_test("ibport")
    data = hw.parse(["RESULT: FAILED"])
    assert data["ibport_fail"] == 1


def test_ibport_no_result():
    hw = get_hw_test("ibport")
    data = hw.parse(["no diagnostic output"])
    assert data == {}


# ---------------------------------------------------------------------------
# idle
# ---------------------------------------------------------------------------

_IDLE_OUTPUT = textwrap.dedent("""\
     10:00:01 up 5 days,  2:30,  1 user,  load average: 0.10, 0.20, 0.30
     10:00:31 up 5 days,  2:30,  1 user,  load average: 0.20, 0.20, 0.30
""").splitlines()


def test_idle_parse():
    hw = get_hw_test("idle")
    data = hw.parse(_IDLE_OUTPUT)
    assert data["idle_load"] == pytest.approx(0.15)


# ---------------------------------------------------------------------------
# matmult
# ---------------------------------------------------------------------------

_MATMULT = textwrap.dedent("""\
    ==testcase==> 64x64 at 12:00:00
    Average speedup is 3.5
    Elapsed Time: 1.2 minutes
    ==testcase==> 128x128 at 12:01:00
    Average speedup is 4.1
    Elapsed Time: 2.5 minutes
""").splitlines()


def test_matmult_parse():
    hw = get_hw_test("matmult")
    data = hw.parse(_MATMULT)
    assert data["matmult_64x64_speedup"] == pytest.approx(3.5)
    assert data["matmult_128x128_elapsed"] == pytest.approx(2.5)


# ---------------------------------------------------------------------------
# mpqc
# ---------------------------------------------------------------------------

_MPQC = textwrap.dedent("""\
    ====> h2o_sto3g
    mpqc: 10.5 45.3
    ====> ch4_ccpvdz
    mpqc: 20.1 120.7
""").splitlines()


def test_mpqc_parse():
    hw = get_hw_test("mpqc")
    data = hw.parse(_MPQC)
    assert data["mpqc_fail"] == 0
    assert data["mpqc_walltime_total"] == pytest.approx(45.3 + 120.7)


def test_mpqc_with_failure():
    hw = get_hw_test("mpqc")
    data = hw.parse(["====> h2o_sto3g", "error: calculation failed"])
    assert data["mpqc_fail"] == 1


# ---------------------------------------------------------------------------
# omdiag
# ---------------------------------------------------------------------------

_OMDIAG = textwrap.dedent("""\
    ====> CPU Test1
    Result : F
    ====> Memory Test2
    Result : ok
""").splitlines()


def test_omdiag_parse():
    hw = get_hw_test("omdiag")
    data = hw.parse(_OMDIAG)
    # "F" matches character class [Failed]
    assert data["omdiag_CPU_Test1_fail"] == 1
    assert data["omdiag_Memory_Test2_fail"] == 0


def test_omdiag_notloaded():
    hw = get_hw_test("omdiag")
    data = hw.parse(["could not locate the omdiag binary"])
    assert data.get("omdiag_notloaded") == 1


# ---------------------------------------------------------------------------
# psnap
# ---------------------------------------------------------------------------

_PSNAP = textwrap.dedent("""\
    0 100 5 somedata
    1 200 3 somedata
""").splitlines()


def test_psnap_parse():
    hw = get_hw_test("psnap")
    data = hw.parse(_PSNAP)
    # weighted avg: (100*5 + 200*3) / (5+3) = (500+600)/8 = 137.5
    assert data["psnap_ave"] == pytest.approx(137.5)
    assert data["psnap_numbins"] == 2


def test_psnap_empty():
    hw = get_hw_test("psnap")
    data = hw.parse([])
    assert data["psnap_ave"] == 0
    assert data["psnap_numbins"] == 0


# ---------------------------------------------------------------------------
# stride
# ---------------------------------------------------------------------------

_STRIDE = textwrap.dedent("""\
    ==testcase==> stride128 at 12:00:00
    Elapsed Time: 3.7 minutes
    ==testcase==> stride256 at 12:04:00
    Elapsed Time: 5.1 minutes
""").splitlines()


def test_stride_parse():
    hw = get_hw_test("stride")
    data = hw.parse(_STRIDE)
    assert data["stride_stride128_elapsed"] == pytest.approx(3.7)
    assert data["stride_stride256_elapsed"] == pytest.approx(5.1)


# ---------------------------------------------------------------------------
# topspin
# ---------------------------------------------------------------------------

_TOPSPIN = textwrap.dedent("""\
    PCI Device Check                   PASS
    Host Driver RPM Check              FAIL
    HCA Firmware Check                 PASS
      port=1
      port_state=PORT_ACTIVE
    4000000 1234.56
""").splitlines()


def test_topspin_parse():
    hw = get_hw_test("topspin")
    data = hw.parse(_TOPSPIN)
    assert data["topspin_device_fail"] == 0
    assert data["topspin_rpm_fail"] == 1
    assert data["topspin_firmware_fail"] == 0
    assert data["topspin_port0_up"] == 1
    assert data["topspin_pci_loopback"] == pytest.approx(1234.56)


# ---------------------------------------------------------------------------
# xhpl2
# ---------------------------------------------------------------------------

_XHPL2_PASS = textwrap.dedent("""\
    matrix A is randomly generated
    T/V                N    NB   P   Q               Time              Gflops
    --------------------------------------------------------------------------------
    WR11C2R4       16384   512    1    1            12.34     3.210e+02
    --------------------------------------------------------------------------------
    ||Ax-b||_oo/(eps*(||A||_oo*||x||_oo+||b||_oo)*N)=   0.0023 ...... PASSED
""").splitlines()

_XHPL2_FAIL = textwrap.dedent("""\
    matrix A is randomly generated
    T/V                N    NB   P   Q               Time              Gflops
    --------------------------------------------------------------------------------
    WR11C2R4       16384   512    1    1            12.34     3.210e+02
    --------------------------------------------------------------------------------
    ||Ax-b||_oo/(eps*(||A||_oo*||x||_oo+||b||_oo)*N)=   99.999 ...... FAILED
""").splitlines()


def test_xhpl2_pass():
    hw = get_hw_test("xhpl2")
    data = hw.parse(_XHPL2_PASS)
    assert data["xhpl2_gflops"] == pytest.approx(321.0)
    assert data["xhpl2_fail"] == 0


def test_xhpl2_fail():
    hw = get_hw_test("xhpl2")
    data = hw.parse(_XHPL2_FAIL)
    assert data["xhpl2_fail"] == 1


# ---------------------------------------------------------------------------
# numa_mem
# ---------------------------------------------------------------------------

_NUMA_MEM = textwrap.dedent("""\
    CBENCH RUN_NUMA_TEST COMMAND: numactl --cpunodebind=0 --membind=0 stream-avx
    Copy:  12345
    Scale: 11000
    Add:   9800
    Triad: 10200
    Solution Validates
""").splitlines()


def test_numa_mem_parse():
    hw = get_hw_test("numa_mem")
    data = hw.parse(_NUMA_MEM)
    assert "numa_mem_stream_copy_cpunodebind=0_membind=0_stream-avx" in data
    assert data["numa_mem_stream_copy_cpunodebind=0_membind=0_stream-avx"] == pytest.approx(12345.0)


# ---------------------------------------------------------------------------
# numa_gpu
# ---------------------------------------------------------------------------

_NUMA_GPU = textwrap.dedent("""\
    CBENCH RUN_NUMA_TEST COMMAND: numactl --cpunodebind=0 --membind=0 shoc -cuda -d 0
    result for bspeed_download: 10.50 GB
    result for bspeed_readback: 9.80 GB
    result for s3d_dp_pcie: done
""").splitlines()


def test_numa_gpu_parse():
    hw = get_hw_test("numa_gpu")
    data = hw.parse(_NUMA_GPU)
    dl_key = "numa_gpu_shoc_pcie_bandwidth_BusSpeedDownload_cuda_Device_0_cpunodebind=0_membind=0"
    assert dl_key in data
    assert data[dl_key] == pytest.approx(10.50)
