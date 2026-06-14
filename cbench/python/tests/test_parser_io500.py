"""Tests for the IO500 benchmark parser."""

import pytest
from cbench.parsers import get_parser, REGISTRY

_FULL_OUTPUT = """\
[RESULT]          ior-easy-write        1.234 GiB/s : time 60.01 seconds
[RESULT]          ior-easy-read         2.345 GiB/s : time 60.01 seconds
[RESULT]      mdtest-easy-write        123456.78 kIOPS : time 60.00 seconds
[RESULT]       mdtest-easy-read        234567.89 kIOPS : time 60.00 seconds
[RESULT]     mdtest-easy-delete        134567.89 kIOPS : time 60.00 seconds
[RESULT]          ior-hard-write        0.123 GiB/s : time 60.01 seconds
[RESULT]          ior-hard-read         0.234 GiB/s : time 60.01 seconds
[RESULT]      mdtest-hard-write         12345.67 kIOPS : time 60.00 seconds
[RESULT]       mdtest-hard-read         23456.78 kIOPS : time 60.00 seconds
[RESULT]     mdtest-hard-delete         13456.78 kIOPS : time 60.00 seconds
[RESULT]                   find         34567.89 kIOPS : time 60.00 seconds
[SCORE] Bandwidth 1.234 GiB/s : IOPS 12345.67 kIOPS : TOTAL 123.456
"""

_PARTIAL_OUTPUT = """\
[RESULT]          ior-easy-write        1.234 GiB/s : time 60.01 seconds
[RESULT]          ior-easy-read         2.345 GiB/s : time 60.01 seconds
"""

_EMPTY_OUTPUT = "IO500 benchmark starting...\n"


def test_io500_registered():
    assert "io500" in REGISTRY


def test_io500_passed():
    p = get_parser("io500")
    r = p.parse(_FULL_OUTPUT)
    assert r.status == "PASSED"


def test_io500_score_metrics():
    p = get_parser("io500")
    r = p.parse(_FULL_OUTPUT)
    assert r.metrics["score"] == pytest.approx(123.456)
    assert r.metrics["bandwidth_GiB_s"] == pytest.approx(1.234)
    assert r.metrics["iops_kIOPS"] == pytest.approx(12345.67)


def test_io500_per_phase_metrics():
    p = get_parser("io500")
    r = p.parse(_FULL_OUTPUT)
    assert r.metrics["ior_easy_write_GiB_s"] == pytest.approx(1.234)
    assert r.metrics["ior_easy_read_GiB_s"] == pytest.approx(2.345)
    assert r.metrics["mdtest_easy_write_kIOPS"] == pytest.approx(123456.78)
    assert r.metrics["mdtest_hard_delete_kIOPS"] == pytest.approx(13456.78)
    assert r.metrics["find_kIOPS"] == pytest.approx(34567.89)


def test_io500_partial_run():
    p = get_parser("io500")
    r = p.parse(_PARTIAL_OUTPUT)
    assert r.status.startswith("ERROR(INCOMPLETE)")
    assert r.metrics["ior_easy_write_GiB_s"] == pytest.approx(1.234)


def test_io500_not_started():
    p = get_parser("io500")
    r = p.parse(_EMPTY_OUTPUT)
    assert r.status == "NOTSTARTED"


def test_io500_notice():
    p = get_parser("io500")
    r = p.parse("CBENCH NOTICE something happened\n")
    assert r.status == "NOTICE"


def test_io500_metric_units():
    p = get_parser("io500")
    units = p.metric_units()
    assert units["score"] == "IO500_score"
    assert units["bandwidth_GiB_s"] == "GiB/s"
    assert units["iops_kIOPS"] == "kIOPS"
    assert units["ior_easy_write_GiB_s"] == "GiB/s"
    assert units["find_kIOPS"] == "kIOPS"
