"""Tests for the MLPerf Training and Inference parser."""

import json
import pytest
from cbench.parsers import get_parser, REGISTRY


def _mllog(key, time_ms, value=None, **meta):
    entry = {"namespace": "", "time_ms": time_ms, "event_type": "POINT_IN_TIME",
             "key": key, "value": value, "metadata": meta}
    return f":::MLLOG {json.dumps(entry)}"


# ---------------------------------------------------------------------------
# MLPerf Training fixtures
# ---------------------------------------------------------------------------

_TRAINING_PASS = "\n".join([
    _mllog("run_start", 1000000),
    _mllog("epoch_stop", 1010000, epoch_num=1.0),
    _mllog("eval_accuracy", 1010500, value=0.65),
    _mllog("epoch_stop", 1020000, epoch_num=2.0),
    _mllog("eval_accuracy", 1020500, value=0.72),
    _mllog("epoch_stop", 1030000, epoch_num=3.0),
    _mllog("eval_accuracy", 1030500, value=0.758),
    _mllog("run_stop", 1031000, status="success", epoch_num=3.0),
])

_TRAINING_ABORT = "\n".join([
    _mllog("run_start", 2000000),
    _mllog("eval_accuracy", 2010000, value=0.45),
    _mllog("run_stop", 2020000, status="aborted"),
])

_TRAINING_INCOMPLETE = "\n".join([
    _mllog("run_start", 3000000),
    _mllog("eval_accuracy", 3010000, value=0.55),
])

_TRAINING_NO_MLLOG = "Starting training run...\nLoss: 0.345\n"


# ---------------------------------------------------------------------------
# MLPerf Inference fixtures
# ---------------------------------------------------------------------------

_INF_OFFLINE_VALID = """\
================================================
MLPerf Results Summary
================================================
SUT name : ResNet50_Offline
Scenario : Offline
Mode     : PerformanceOnly
Samples per second: 12345.67
Result is : VALID
  Min duration satisfied : Yes
  Min queries satisfied : Yes
"""

_INF_SINGLESTREAM_VALID = """\
================================================
MLPerf Results Summary
================================================
SUT name : BERT_SingleStream
Scenario : SingleStream
Mode     : PerformanceOnly
90th percentile latency (ns) : 9876543
Mean latency (ns) : 8765432
99th percentile latency (ns) : 11234567
Result is : VALID
"""

_INF_INVALID = """\
================================================
MLPerf Results Summary
================================================
Scenario : Offline
Samples per second: 99.99
Result is : INVALID
"""

_INF_INCOMPLETE = """\
================================================
MLPerf Results Summary
================================================
Scenario : Offline
"""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def test_mlperf_registered():
    assert "mlperf" in REGISTRY
    assert "mlperf-training" in REGISTRY
    assert "mlperf-inference" in REGISTRY


# ---------------------------------------------------------------------------
# Training tests
# ---------------------------------------------------------------------------

def test_training_passed():
    r = get_parser("mlperf").parse(_TRAINING_PASS)
    assert r.status == "PASSED"


def test_training_time_to_train():
    r = get_parser("mlperf").parse(_TRAINING_PASS)
    # run_stop(1031000) - run_start(1000000) = 31000 ms = 31.0 s
    assert r.metrics["time_to_train_s"] == pytest.approx(31.0)


def test_training_accuracy():
    r = get_parser("mlperf").parse(_TRAINING_PASS)
    assert r.metrics["final_accuracy"] == pytest.approx(0.758)
    assert r.metrics["max_accuracy"] == pytest.approx(0.758)


def test_training_epochs():
    r = get_parser("mlperf").parse(_TRAINING_PASS)
    assert r.metrics["epochs"] == pytest.approx(3.0)


def test_training_aborted():
    r = get_parser("mlperf").parse(_TRAINING_ABORT)
    assert r.status.startswith("ERROR(ABORTED)")


def test_training_incomplete():
    r = get_parser("mlperf").parse(_TRAINING_INCOMPLETE)
    assert r.status.startswith("ERROR(INCOMPLETE)")
    assert r.metrics["final_accuracy"] == pytest.approx(0.55)


def test_training_not_started():
    r = get_parser("mlperf").parse(_TRAINING_NO_MLLOG)
    assert r.status == "NOTSTARTED"


# ---------------------------------------------------------------------------
# Inference tests
# ---------------------------------------------------------------------------

def test_inference_offline_passed():
    r = get_parser("mlperf").parse(_INF_OFFLINE_VALID)
    assert r.status == "PASSED"
    assert r.metrics["samples_per_second"] == pytest.approx(12345.67)


def test_inference_singlestream_passed():
    r = get_parser("mlperf").parse(_INF_SINGLESTREAM_VALID)
    assert r.status == "PASSED"
    assert r.metrics["latency_p90_ns"] == pytest.approx(9876543.0)
    assert r.metrics["latency_mean_ns"] == pytest.approx(8765432.0)
    assert r.metrics["latency_p99_ns"] == pytest.approx(11234567.0)


def test_inference_invalid_result():
    r = get_parser("mlperf").parse(_INF_INVALID)
    assert r.status.startswith("ERROR(INVALID)")
    assert r.metrics["samples_per_second"] == pytest.approx(99.99)


def test_inference_incomplete():
    r = get_parser("mlperf").parse(_INF_INCOMPLETE)
    assert r.status.startswith("ERROR(INCOMPLETE)")


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

def test_notice():
    r = get_parser("mlperf").parse("CBENCH NOTICE something\n")
    assert r.status == "NOTICE"


def test_metric_units():
    units = get_parser("mlperf").metric_units()
    assert units["time_to_train_s"] == "seconds"
    assert units["samples_per_second"] == "samples/s"
    assert units["latency_p90_ns"] == "ns"
