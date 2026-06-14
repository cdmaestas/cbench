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


# ---------------------------------------------------------------------------
# trend()
# ---------------------------------------------------------------------------

def test_trend_returns_ordered_series(db):
    for i, bw in enumerate([9000.0, 10000.0, 11000.0]):
        db.store(_make_result(
            ident=f"run{i}", jobname=f"job{i}",
            metrics={"unidir_bw": bw}, metric_units={"unidir_bw": "MB/s"},
        ))
    rows = db.trend(benchmark="osubw", metric="unidir_bw")
    assert len(rows) == 3
    # ordered chronologically — values should ascend
    assert rows[0]["value"] < rows[-1]["value"]
    assert rows[0]["units"] == "MB/s"
    assert rows[0]["count"] == 1


def test_trend_averages_multiple_runs_per_ident(db):
    for bw in [8000.0, 12000.0]:
        db.store(_make_result(ident="run1", jobname=f"job-{bw}",
                              metrics={"unidir_bw": bw}))
    rows = db.trend(benchmark="osubw", metric="unidir_bw")
    assert len(rows) == 1
    assert abs(rows[0]["value"] - 10000.0) < 1.0
    assert rows[0]["count"] == 2


def test_trend_empty_when_no_match(db):
    db.store(_make_result())
    rows = db.trend(benchmark="osubw", metric="nonexistent_metric")
    assert rows == []


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def test_store_is_idempotent(db):
    """Storing the same natural key twice must not create a duplicate row."""
    db.store(_make_result(metrics={"unidir_bw": 9000.0}))
    db.store(_make_result(metrics={"unidir_bw": 9500.0}))  # same key, updated value
    rows = db.query()
    assert len(rows) == 1
    assert rows[0]["metrics"]["unidir_bw"]["value"] == 9500.0


def test_store_idempotent_different_benchmark(db):
    """Two stores with different benchmarks are separate rows, not duplicates."""
    db.store(_make_result(benchmark="osubw", jobname="osubw-2ppn-16",
                          metrics={"bw": 9500.0}))
    db.store(_make_result(benchmark="xhpl", jobname="xhpl-2ppn-16",
                          metrics={"gflops": 100.0}))
    rows = db.query()
    assert len(rows) == 2


def test_store_idempotent_metrics_replaced(db):
    """Re-storing replaces metrics, not accumulates them."""
    db.store(_make_result(metrics={"bw": 9000.0, "lat": 1.5}))
    # Second store with fewer metrics — old metrics must be gone
    db.store(_make_result(metrics={"bw": 9500.0}))
    rows = db.query()
    assert len(rows) == 1
    assert "bw" in rows[0]["metrics"]
    assert "lat" not in rows[0]["metrics"]


def test_deduplicate_removes_older_rows(tmp_path):
    """deduplicate() keeps most-recent row per natural key."""
    import sqlite3 as _sqlite3
    from cbench.db import _DDL

    db_path = tmp_path / "legacy.db"
    r = _make_result()

    # Simulate a pre-dedup DB: create schema without the unique index,
    # then insert two rows sharing the same natural key.
    with _sqlite3.connect(db_path) as con:
        con.executescript(_DDL)
        for ts in ("2025-01-01T00:00:00", "2025-06-01T00:00:00"):
            con.execute(
                "INSERT INTO runs (cluster,testset,ident,jobname,benchmark,"
                "numprocs,ppn,numnodes,status,status_detail,parsed_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (r.cluster, r.testset, r.ident, r.jobname, r.benchmark,
                 r.numprocs, r.ppn, r.numnodes, r.status, r.status_detail, ts),
            )

    # Opening ResultsDB will warn (can't add unique index over duplicates)
    import warnings
    with warnings.catch_warnings(record=True):
        db = ResultsDB(db_path)

    assert len(db.query(limit=100)) == 2
    deleted = db.deduplicate()
    assert deleted == 1
    rows = db.query(limit=100)
    assert len(rows) == 1
    assert rows[0]["parsed_at"].startswith("2025-06-01")
