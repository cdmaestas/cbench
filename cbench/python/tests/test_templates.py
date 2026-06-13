"""Tests for template substitution logic."""

import pytest

from cbench.templates import _here_to_jinja, compute_walltime, RUN_SIZES
from cbench.config import ClusterConfig


def test_here_to_jinja_basic():
    result = _here_to_jinja("echo NUM_PROCS_HERE and JOBNAME_HERE")
    assert "{{ NUM_PROCS }}" in result
    assert "{{ JOBNAME }}" in result
    assert "_HERE" not in result


def test_here_to_jinja_no_lowercase():
    # lowercase tokens should not be converted
    result = _here_to_jinja("some_var_here")
    assert "{{" not in result


def test_walltime_method_0():
    cfg = ClusterConfig(default_walltime="04:00:00", walltime_method=0)
    wt = compute_walltime(32, RUN_SIZES, cfg)
    assert wt == "04:00:00"


def test_walltime_method_1_increases():
    cfg = ClusterConfig(default_walltime="01:00:00", walltime_method=1, walltime_steptime=10)
    wt_small = compute_walltime(1, RUN_SIZES, cfg)
    wt_large = compute_walltime(128, RUN_SIZES, cfg)
    # Larger run sizes should get more walltime
    def to_minutes(t):
        h, m, s = t.split(":")
        return int(h) * 60 + int(m)
    assert to_minutes(wt_large) > to_minutes(wt_small)


def test_run_sizes_are_sorted():
    assert RUN_SIZES == sorted(RUN_SIZES)


def test_run_sizes_include_powers_of_two():
    for p in [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024]:
        assert p in RUN_SIZES
