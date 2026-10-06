"""`cbench watch`: the state of a testset's jobs, from their heartbeat files.

Each gen-jobs job rewrites ``<jobdir>/<job>.heartbeat`` (common_header.in)::

    Cbench heartbeat: <job> (jobid N) started|still running|exited rc=N,
        elapsed 0h12m30s at 2026-10-05 12:35:29, every 60s

(one line; files from before the interval was recorded lack ", every Ns").
Each job is one of:

* ``running``: the file says started / still running and was updated within
  the stale window.
* ``stale``: it says running but hasn't been updated for ``stale_factor``
  heartbeat intervals (default 3): killed with SIGKILL, or its node died.
* ``finished`` (rc 0) / ``failed`` (rc != 0): the file records the exit.
* ``not started``: no heartbeat file (queued, not submitted, or generated
  with heartbeats off); ``no heartbeat`` when the job has output from a run
  without one.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_LINE_RE = re.compile(
    r"^Cbench heartbeat: (?P<job>\S+) \(jobid (?P<jobid>[^)]*)\) "
    r"(?P<state>started|still running|exited rc=(?P<rc>-?\d+)), "
    r"elapsed (?P<h>\d+)h(?P<m>\d+)m(?P<s>\d+)s at (?P<at>[\d-]+ [\d:]+)"
    r"(?:, every (?P<every>\d+)s)?"
)

RUNNING = "running"
STALE = "stale"
FINISHED = "finished"
FAILED = "failed"
NOT_STARTED = "not started"
NO_HEARTBEAT = "no heartbeat"
#: states a --follow waits on
ACTIVE = {RUNNING, NOT_STARTED}


@dataclass
class Heartbeat:
    job: str
    jobid: str
    state: str            # "started" | "still running" | "exited"
    rc: int | None
    elapsed_s: int
    at: datetime
    interval_s: int | None


def parse_heartbeat(text: str) -> Heartbeat | None:
    m = _LINE_RE.match(text.strip().splitlines()[-1] if text.strip() else "")
    if not m:
        return None
    exited = m.group("rc") is not None
    return Heartbeat(
        job=m.group("job"), jobid=m.group("jobid"),
        state="exited" if exited else m.group("state"),
        rc=int(m.group("rc")) if exited else None,
        elapsed_s=int(m.group("h")) * 3600 + int(m.group("m")) * 60 + int(m.group("s")),
        at=datetime.strptime(m.group("at"), "%Y-%m-%d %H:%M:%S"),
        interval_s=int(m.group("every")) if m.group("every") else None,
    )


@dataclass
class JobStatus:
    job: str
    status: str
    elapsed_s: int | None = None
    rc: int | None = None
    age_s: int | None = None        # seconds since the heartbeat file changed
    detail: str = ""


def hms(seconds: int | None) -> str:
    if seconds is None:
        return "-"
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}h{m:02d}m{s:02d}s" if h else f"{m}m{s:02d}s"


def job_status(jobdir: Path, *, default_interval: int, stale_factor: float = 3,
               stale_after: int | None = None, now: float | None = None) -> JobStatus:
    now = time.time() if now is None else now
    name = jobdir.name
    files = sorted(jobdir.glob("*.heartbeat"), key=lambda p: p.stat().st_mtime)
    if not files:
        has_output = any(p.is_file() for p in jobdir.glob("*.o*")) or any(jobdir.glob("slurm-*.out"))
        if has_output:
            return JobStatus(name, NO_HEARTBEAT, detail="output from a run without a heartbeat")
        return JobStatus(name, NOT_STARTED)
    path = files[-1]
    hb = parse_heartbeat(path.read_text(errors="replace"))
    age = int(now - path.stat().st_mtime)
    if hb is None:
        return JobStatus(name, NO_HEARTBEAT, age_s=age, detail=f"unreadable {path.name}")
    if hb.state == "exited":
        return JobStatus(name, FINISHED if hb.rc == 0 else FAILED, hb.elapsed_s, hb.rc, age,
                         f"jobid {hb.jobid}")
    interval = hb.interval_s or default_interval
    window = stale_after if stale_after is not None else int(stale_factor * interval)
    elapsed = hb.elapsed_s + age          # time since the last update counts too
    if age > window:
        return JobStatus(name, STALE, elapsed, None, age,
                         f"no heartbeat for {hms(age)} (every {interval}s); killed? jobid {hb.jobid}")
    return JobStatus(name, RUNNING, elapsed, None, age, f"jobid {hb.jobid}")


def scan(ident_dir: Path, **kw) -> list[JobStatus]:
    """One status per job directory under ``$CBENCHTEST/<testset>/<ident>``."""
    if not ident_dir.is_dir():
        return []
    return [job_status(d, **kw) for d in sorted(p for p in ident_dir.iterdir() if p.is_dir())]


def all_done(statuses: list[JobStatus]) -> bool:
    return bool(statuses) and not any(s.status in ACTIVE for s in statuses)


def succeeded(statuses: list[JobStatus]) -> bool:
    """No job failed or went stale (one without a heartbeat is unknown, not failed)."""
    return not any(s.status in (FAILED, STALE) for s in statuses)
