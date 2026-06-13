"""Tests for cbench.parse_filters."""

import pytest
from cbench.parse_filters import build_filter_set, apply_filters, AVAILABLE


def test_available_modules():
    assert set(AVAILABLE) == {"cray", "misc", "mpiexec", "mvapich", "openmpi", "slurm", "torque"}


def test_build_filter_set_unknown():
    with pytest.raises(ValueError, match="Unknown parse filter module"):
        build_filter_set(["bogus"])


def test_build_filter_set_merged():
    filters = build_filter_set(["slurm", "torque"])
    assert any("WALLTIME" in v for v in filters.values())
    assert any("PBS" in v for v in filters.values())


# --- slurm ---

def test_slurm_walltime():
    filters = build_filter_set(["slurm"])
    errors = apply_filters(filters, "slurmd[n1]: *** JOB 12 CANCELLED AT 2024-01-01 DUE TO TIME LIMIT ***")
    assert errors == ["SLURM JOB WALLTIME EXCEEDED"]


def test_slurm_node_failure():
    filters = build_filter_set(["slurm"])
    errors = apply_filters(filters, "*** JOB 100532 CANCELLED AT 2010-01-27 DUE TO NODE FAILURE ***")
    assert errors and "NODE FAILURE" in errors[0]


def test_slurm_cancelled():
    filters = build_filter_set(["slurm"])
    errors = apply_filters(filters, "*** JOB 1666 CANCELLED AT 04/03-08:41:23 ***")
    assert errors == ["SLURM JOB CANCELLED"]


# --- torque ---

def test_torque_walltime():
    filters = build_filter_set(["torque"])
    errors = apply_filters(filters, "PBS: job killed: walltime 04:00:01 exceeded limit 04:00:00")
    assert errors == ["PBS JOB WALLTIME EXCEEDED"]


def test_torque_die_request():
    filters = build_filter_set(["torque"])
    line = "PBS: job killed: node 3 (n003) requested job die, code 9"
    errors = apply_filters(filters, line)
    assert errors and "n003" in errors[0] and "code=9" in errors[0]


# --- mpiexec ---

def test_mpiexec_task_died():
    filters = build_filter_set(["mpiexec"])
    line = "mpiexec: Warning: task 7 died with signal 11 (Segmentation fault)"
    errors = apply_filters(filters, line)
    assert errors and "TASK DIED" in errors[0] and "Segmentation fault" in errors[0]


def test_mpiexec_killall():
    filters = build_filter_set(["mpiexec"])
    line = "mpiexec: killall: caught signal 15 (Terminated)"
    errors = apply_filters(filters, line)
    assert errors and "KILLALL" in errors[0] and "Terminated" in errors[0]


# --- mvapich ---

def test_mvapich_vapi_retry():
    filters = build_filter_set(["mvapich"])
    line = "Abort: something code=VAPI_RETRY_EXC_ERR,blah dest rank=[n001:0]"
    errors = apply_filters(filters, line)
    assert errors and "VAPI_RETRY_EXC_ERR" in errors[0]


# --- openmpi ---

def test_openmpi_mpi_init():
    filters = build_filter_set(["openmpi"])
    errors = apply_filters(filters, "An error occurred in MPI_Init")
    assert errors == ["OMPI says MPI_INIT failed"]


def test_openmpi_orterun_rank():
    filters = build_filter_set(["openmpi"])
    line = "orterun noticed that job rank 0 with PID 4696 on node slot1 exited on signal 4 (Illegal instruction)."
    errors = apply_filters(filters, line)
    assert errors and "rank 0" in errors[0] and "slot1" in errors[0]


def test_openmpi_not_enough_slots():
    filters = build_filter_set(["openmpi"])
    errors = apply_filters(filters, "There are not enough slots on the nodes")
    assert errors and "not enough slots" in errors[0]


def test_openmpi_mpi_abort():
    filters = build_filter_set(["openmpi"])
    line = "[n001:12345] MPI_ABORT invoked on rank 3 in communicator MPI_COMM_WORLD with errorcode 1"
    errors = apply_filters(filters, line)
    assert errors and "MPI_ABORT" in errors[0] and "rank 3" in errors[0]


# --- cray ---

def test_cray_oom():
    filters = build_filter_set(["cray"])
    line = "[NID 00146] 2011-05-01 19:00:18 Apid 15379: OOM killer terminated this process."
    errors = apply_filters(filters, line)
    assert errors and "NID" in errors[0] and "OOM" in errors[0]


def test_cray_aprun_unexpected_close():
    filters = build_filter_set(["cray"])
    errors = apply_filters(filters, "aprun: Unexpected close of something")
    assert errors and "APRUN" in errors[0]


def test_cray_segfault():
    filters = build_filter_set(["cray"])
    errors = apply_filters(filters, "PE 5 exit signal Segmentation fault")
    assert errors == ["application segmentation fault"]


# --- misc ---

def test_misc_cbench_warning():
    filters = build_filter_set(["misc"])
    line = "CBENCH WARNING: something went wrong"
    errors = apply_filters(filters, line)
    assert errors == ["CBENCH WARNING: something went wrong"]


def test_misc_hpl_error():
    filters = build_filter_set(["misc"])
    line = "HPL ERROR from process # 5, on line 42"
    errors = apply_filters(filters, line)
    assert errors and "HPL ERROR from process #5" in errors[0]


def test_misc_forrtl():
    filters = build_filter_set(["misc"])
    line = "forrtl: error (78): process killed (SIGTERM)"
    errors = apply_filters(filters, line)
    assert errors and "FORRTL" in errors[0] and "SIGTERM" in errors[0]


def test_misc_shared_lib():
    filters = build_filter_set(["misc"])
    line = "/path/to/bin: error while loading shared libraries: libfoo.so.0: cannot open shared object file: No such file"
    errors = apply_filters(filters, line)
    assert errors and "libfoo.so.0" in errors[0]


def test_no_match_clean_output():
    filters = build_filter_set(AVAILABLE)
    clean = "HPL run completed successfully.\nGflops: 1234.5\n"
    errors = apply_filters(filters, clean)
    assert errors == []


def test_multiple_errors():
    filters = build_filter_set(["slurm", "misc"])
    text = (
        "CBENCH WARNING: disk nearly full\n"
        "*** JOB 99 CANCELLED AT 2024-01-01 DUE TO TIME LIMIT ***\n"
    )
    errors = apply_filters(filters, text)
    assert len(errors) == 2
