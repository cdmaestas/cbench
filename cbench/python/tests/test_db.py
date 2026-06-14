"""Tests for the SQLite results store."""

import tempfile
from pathlib import Path

import pytest

from cbench.db import ParseResult, ResultsDB


@pytest.fixture
def db(tmp_path):
    return ResultsDB(tmp_path / "results.db")


def _make_result(**kwargs) -> ParseResult:
    defaults = dict(
        cluster="test", testset="bandwidth", ident="run1",
        jobname="osubw-2ppn-16", benchmark="osubw",
        numprocs=16, ppn=2, numnodes=8,
        status="PASSED",
        metrics={"unidir_bw": 9500.0},
        metric_units={"unidir_bw": "MB/s"},
    )
    defaults.update(kwargs)
    return ParseResult(**defaults)


def test_store_and_retrieve(db):
    run_id = db.store(_make_result())
    assert run_id == 1
    rows = db.query()
    assert len(rows) == 1
    assert rows[0]["status"] == "PASSED"
    assert rows[0]["metrics"]["unidir_bw"]["value"] == 9500.0
    assert rows[0]["metrics"]["unidir_bw"]["units"] == "MB/s"


def test_filter_by_benchmark(db):
    db.store(_make_result(benchmark="osubw"))
    db.store(_make_result(benchmark="xhpl", jobname="xhpl-4ppn-32",
                          metrics={"gflops": 100.0}, metric_units={"gflops": "GigaFlops"}))
    rows = db.query(benchmark="xhpl")
    assert len(rows) == 1
    assert rows[0]["benchmark"] == "xhpl"


def test_filter_by_status(db):
    db.store(_make_result(status="PASSED"))
    db.store(_make_result(status="ERROR(NOTSTARTED)", jobname="fail-2ppn-8"))
    rows = db.query(status="PASSED")
    assert len(rows) == 1


def test_export_json(db):
    import json
    db.store(_make_result())
    j = db.export_json()
    data = json.loads(j)
    assert len(data) == 1


def test_summary(db):
    db.store(_make_result(status="PASSED"))
    db.store(_make_result(status="PASSED", jobname="job2"))
    db.store(_make_result(status="ERROR(NOTSTARTED)", jobname="job3"))
    s = db.summary()
    assert s["PASSED"] == 2
    assert s["ERROR(NOTSTARTED)"] == 1


def test_cascade_delete(db):
    """Metrics are deleted when their run is deleted (FK cascade)."""
    import sqlite3
    run_id = db.store(_make_result())
    with db._conn() as con:
        con.execute("DELETE FROM runs WHERE id = ?", (run_id,))
    with db._conn() as con:
        rows = con.execute("SELECT * FROM metrics WHERE run_id = ?", (run_id,)).fetchall()
    assert rows == []


def test_filter_by_until(db):
    db.store(_make_result(jobname="job1"))
    rows = db.query(until="2020-01-01")
    assert len(rows) == 0  # stored now is after 2020-01-01


def test_filter_by_since_and_until(db):
    db.store(_make_result(jobname="job1"))
    rows = db.query(since="2020-01-01", until="2099-12-31")
    assert len(rows) == 1
