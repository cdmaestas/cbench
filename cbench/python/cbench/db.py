"""SQLite results store for Cbench benchmark data."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Optional


@dataclass
class ParseResult:
    cluster: str
    testset: str
    ident: str
    jobname: str
    benchmark: str
    numprocs: int
    ppn: int
    numnodes: int
    status: str
    status_detail: str = ""
    metrics: dict[str, float] = field(default_factory=dict)
    metric_units: dict[str, str] = field(default_factory=dict)
    parsed_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.parsed_at is None:
            self.parsed_at = datetime.now(timezone.utc)


_DDL = """
CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    cluster     TEXT    NOT NULL,
    testset     TEXT    NOT NULL,
    ident       TEXT    NOT NULL,
    jobname     TEXT    NOT NULL,
    benchmark   TEXT    NOT NULL,
    numprocs    INTEGER NOT NULL,
    ppn         INTEGER NOT NULL,
    numnodes    INTEGER NOT NULL,
    status      TEXT    NOT NULL,
    status_detail TEXT  DEFAULT '',
    parsed_at   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS metrics (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id  INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    metric  TEXT    NOT NULL,
    value   REAL    NOT NULL,
    units   TEXT    DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_runs_benchmark  ON runs(benchmark);
CREATE INDEX IF NOT EXISTS idx_runs_cluster    ON runs(cluster);
CREATE INDEX IF NOT EXISTS idx_runs_status     ON runs(status);
CREATE INDEX IF NOT EXISTS idx_runs_parsed_at  ON runs(parsed_at);
"""


class ResultsDB:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._init()

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        try:
            yield con
            con.commit()
        finally:
            con.close()

    def _init(self) -> None:
        with self._conn() as con:
            con.executescript(_DDL)

    def store(self, result: ParseResult) -> int:
        """Insert a ParseResult and return the new run id."""
        with self._conn() as con:
            cur = con.execute(
                """
                INSERT INTO runs
                    (cluster, testset, ident, jobname, benchmark,
                     numprocs, ppn, numnodes, status, status_detail, parsed_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    result.cluster, result.testset, result.ident,
                    result.jobname, result.benchmark,
                    result.numprocs, result.ppn, result.numnodes,
                    result.status, result.status_detail,
                    result.parsed_at.isoformat() if result.parsed_at else "",
                ),
            )
            run_id = cur.lastrowid
            for metric, value in result.metrics.items():
                units = result.metric_units.get(metric, "")
                con.execute(
                    "INSERT INTO metrics (run_id, metric, value, units) VALUES (?,?,?,?)",
                    (run_id, metric, value, units),
                )
        return run_id

    def query(
        self,
        *,
        benchmark: Optional[str] = None,
        cluster: Optional[str] = None,
        testset: Optional[str] = None,
        ident: Optional[str] = None,
        status: Optional[str] = None,
        since: Optional[str] = None,
        until: Optional[str] = None,
        limit: int = 1000,
    ) -> list[dict]:
        """Return runs matching the given filters, with their metrics attached."""
        where: list[str] = []
        params: list = []

        if benchmark:
            where.append("r.benchmark = ?")
            params.append(benchmark)
        if cluster:
            where.append("r.cluster = ?")
            params.append(cluster)
        if testset:
            where.append("r.testset = ?")
            params.append(testset)
        if ident:
            where.append("r.ident = ?")
            params.append(ident)
        if status:
            where.append("r.status = ?")
            params.append(status)
        if since:
            where.append("r.parsed_at >= ?")
            params.append(since)
        if until:
            where.append("r.parsed_at <= ?")
            params.append(until)

        where_clause = ("WHERE " + " AND ".join(where)) if where else ""

        with self._conn() as con:
            rows = con.execute(
                f"""
                SELECT r.*, m.metric, m.value, m.units
                FROM runs r
                LEFT JOIN metrics m ON m.run_id = r.id
                {where_clause}
                ORDER BY r.parsed_at DESC
                LIMIT ?
                """,
                params + [limit],
            ).fetchall()

        # Group metrics back onto runs
        runs: dict[int, dict] = {}
        for row in rows:
            rid = row["id"]
            if rid not in runs:
                runs[rid] = {
                    k: row[k]
                    for k in ("id", "cluster", "testset", "ident", "jobname",
                               "benchmark", "numprocs", "ppn", "numnodes",
                               "status", "status_detail", "parsed_at")
                }
                runs[rid]["metrics"] = {}
            if row["metric"]:
                runs[rid]["metrics"][row["metric"]] = {
                    "value": row["value"],
                    "units": row["units"],
                }
        return list(runs.values())

    def export_json(self, **query_kwargs) -> str:
        return json.dumps(self.query(**query_kwargs), indent=2)

    def summary(self) -> dict:
        """Return high-level counts by status."""
        with self._conn() as con:
            rows = con.execute(
                "SELECT status, COUNT(*) as n FROM runs GROUP BY status"
            ).fetchall()
        return {row["status"]: row["n"] for row in rows}
