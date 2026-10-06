"""The operations `cbench mcp` exposes as MCP tools (cbench.mcp_server).

Plain functions returning JSON-able dicts, with no MCP dependency, so they
run (and are tested) on every Python cbench supports; the MCP SDK needs 3.10+.

Consent: every operation that changes something (cluster.yaml, files under
$CBENCHTEST, remote nodes, the batch queue, builds) takes ``confirm``. Without
``confirm=True`` it changes nothing and returns the plan: the exact cbench
command, or the cluster.yaml diff. MCP hosts also prompt per tool call (the
server marks these tools non-read-only); ``confirm`` keeps a model from acting
on its own reading of a request. ``parse_results`` is the exception: it only
re-derives the results database from job output, and re-parsing overwrites
rather than duplicates (db.py).

Missing system software is never installed: ``check_deps`` names it and
suggests the package to install (an admin's job). cbench's own benchmark
builders are the one thing it can install, through ``build_benchmark``.

Side-effecting operations run the cbench CLI in a subprocess (``python -m
cbench``), so they behave exactly as from a shell. Long ones (interactive
start-jobs, builds) run detached as tasks: the call returns a task id, and
``task_status`` reports progress and the log tail, so a long run never holds
an MCP request open.
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from cbench import nodecheck, profiles, upstream, watch
from cbench.config import (
    _KEY_ALIASES,
    _SCHEMA,
    ClusterConfig,
    ConfigError,
    check_config_data,
    config_path,
    load_config,
)
from cbench.db import ResultsDB

#: seconds a synchronous CLI call (gen-jobs, batch start-jobs, parse,
#: nodecheck) may take
CLI_TIMEOUT = 900
#: characters of CLI output returned (the end is kept: it has the summary)
OUTPUT_CHARS = 8000
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]*$")
_TASK_RE = re.compile(r"^[0-9a-f]{12}$")


class ToolError(Exception):
    """A request the tool refuses or can't do; the message says why."""


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _cbenchtest(cbenchtest: str | None) -> Path:
    val = cbenchtest or os.environ.get("CBENCHTEST")
    if not val:
        raise ToolError("no CBENCHTEST: set it in the server's environment or pass cbenchtest")
    return Path(val)


def _name(value: str, what: str) -> str:
    """Testset / ident / benchmark names become path parts: no separators."""
    if not _NAME_RE.match(value or ""):
        raise ToolError(f"invalid {what} {value!r} (letters, digits, '.', '_', '-')")
    return value


def _ident_dir(cbenchtest: str | None, testset: str, ident: str) -> Path:
    return _cbenchtest(cbenchtest) / _name(testset, "testset") / _name(ident, "ident")


def _tail(text: str, limit: int = OUTPUT_CHARS) -> str:
    return text if len(text) <= limit else "...\n" + text[-limit:]


def _cli_env(cbenchtest: str | None) -> dict:
    env = dict(os.environ, NO_COLOR="1", TERM="dumb", COLUMNS="200")
    if cbenchtest:
        env["CBENCHTEST"] = str(cbenchtest)
    return env


def cli_argv(args: list[str]) -> list[str]:
    return [sys.executable, "-m", "cbench", *args]


def _plan(args: list[str], what: str, **extra) -> dict:
    return {"confirmed": False, "would_run": "cbench " + " ".join(args),
            "effect": what, "next": "call again with confirm=true to run it", **extra}


def _run_cli(args: list[str], cbenchtest: str | None) -> dict:
    try:
        proc = subprocess.run(cli_argv(args), capture_output=True, text=True,  # noqa: S603 # nosec B603 — argv list, no shell
                              timeout=CLI_TIMEOUT, env=_cli_env(cbenchtest), check=False)
    except subprocess.TimeoutExpired as exc:
        raise ToolError(f"cbench {args[0]} did not finish in {CLI_TIMEOUT}s") from exc
    return {"confirmed": True, "command": "cbench " + " ".join(args), "exit_code": proc.returncode,
            "ok": proc.returncode == 0, "output": _tail(proc.stdout), "stderr": _tail(proc.stderr, 4000)}


def _opt(args: list[str], flag: str, value) -> None:
    if value is None or value is False or value == "" or value == ():
        return
    if value is True:
        args.append(flag)
    elif isinstance(value, (list, tuple)):
        for v in value:
            args += [flag, str(v)]
    else:
        args += [flag, str(value)]


# ---------------------------------------------------------------------------
# tasks: detached long-running CLI calls
# ---------------------------------------------------------------------------

def _tasks_dir(cbenchtest: str | None) -> Path:
    return _cbenchtest(cbenchtest) / ".cbench-mcp" / "tasks"


def start_task(args: list[str], cbenchtest: str | None, kind: str) -> dict:
    """Run ``cbench <args>`` detached; its output goes to a log, its exit code
    to a file the shell wrapper writes when it ends."""
    tdir = _tasks_dir(cbenchtest)
    tdir.mkdir(parents=True, exist_ok=True)
    task_id = secrets.token_hex(6)
    log, rcfile = tdir / f"{task_id}.log", tdir / f"{task_id}.rc"
    # "$0" is the rc file, "$@" the cbench argv: values never enter the script text
    wrapper = ["/bin/sh", "-c", '"$@"; echo $? > "$0"', str(rcfile), *cli_argv(args)]
    with log.open("w") as fh:
        proc = subprocess.Popen(wrapper, stdout=fh, stderr=subprocess.STDOUT,  # noqa: S603 # nosec B603 — fixed script, argv list
                                stdin=subprocess.DEVNULL, env=_cli_env(cbenchtest),
                                start_new_session=True)
    meta = {"task_id": task_id, "kind": kind, "command": "cbench " + " ".join(args),
            "pid": proc.pid, "started": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "log": str(log)}
    (tdir / f"{task_id}.json").write_text(json.dumps(meta, indent=2))
    return {"confirmed": True, **meta, "next": "poll task_status(task_id)"}


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def task_status(task_id: str, tail_lines: int = 40, cbenchtest: str | None = None) -> dict:
    """State of a task started by start_jobs(interactive) or build_benchmark."""
    if not _TASK_RE.match(task_id or ""):
        raise ToolError(f"invalid task id {task_id!r}")
    tdir = _tasks_dir(cbenchtest)
    meta_file = tdir / f"{task_id}.json"
    if not meta_file.is_file():
        raise ToolError(f"no task {task_id} under {tdir}")
    meta = json.loads(meta_file.read_text())
    rcfile = tdir / f"{task_id}.rc"
    if rcfile.is_file() and rcfile.read_text().strip():
        rc = int(rcfile.read_text().strip())
        state = "finished" if rc == 0 else "failed"
    else:
        rc = None
        state = "running" if _alive(meta["pid"]) else "gone"   # killed without an exit code
    log = Path(meta["log"])
    lines = log.read_text(errors="replace").splitlines() if log.is_file() else []
    return {**meta, "state": state, "exit_code": rc,
            "log_tail": "\n".join(lines[-max(1, min(tail_lines, 500)):])}


# ---------------------------------------------------------------------------
# read-only: environment, config, testsets, facts, jobs, results
# ---------------------------------------------------------------------------

def _facts_files(cbenchtest: Path) -> list[dict]:
    out = []
    for f in sorted((cbenchtest / "nodefacts").glob("*.json")):
        try:
            d = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            out.append({"name": f.stem, "error": "unreadable"})
            continue
        out.append({"name": f.stem, "created": d.get("created"), "hosts": len(d.get("hosts", [])),
                    "ok": bool(d.get("verdict", {}).get("ok"))})
    return out


def status(cbenchtest: str | None = None, config: str | None = None) -> dict:
    """Where cbench is pointed: env, cluster.yaml, node facts, results DB."""
    from importlib.metadata import PackageNotFoundError, version
    try:
        ver = version("cbench")
    except PackageNotFoundError:
        ver = "unknown"
    out: dict = {
        "cbench_version": ver, "python": sys.version.split()[0],
        "env": {k: os.environ.get(k) for k in ("CBENCHOME", "CBENCHTEST", "CBENCHCLUSTER")},
    }
    path = config_path(config)
    out["config_file"] = str(path) if path else None
    try:
        out["cluster_name"] = load_config(config).cluster_name
    except ConfigError as exc:
        out["config_error"] = str(exc)
    ct = cbenchtest or os.environ.get("CBENCHTEST")
    if ct:
        ctp = Path(ct)
        out["cbenchtest"] = str(ctp)
        out["node_facts"] = _facts_files(ctp)
        db = ctp / "cbench_results.db"
        out["results_db"] = {"path": str(db), "runs_by_status": ResultsDB(db).summary()} if db.is_file() else None
        out["testsets_with_jobs"] = sorted(
            p.name for p in ctp.iterdir()
            if p.is_dir() and not p.name.startswith(".") and p.name not in ("nodefacts", "bin", "src")
        ) if ctp.is_dir() else []
    return out


def get_config(config: str | None = None, include_schema: bool = False) -> dict:
    """The effective cluster.yaml settings: which keys the file sets, and the
    defaults for the rest (which gen-jobs never uses for sizing)."""
    path = config_path(config)
    cfg = load_config(config)
    values = {f.name: getattr(cfg, f.name) for f in dataclasses.fields(ClusterConfig)
              if f.name != "explicit_keys"}
    out = {"config_file": str(path) if path else None,
           "set_in_file": sorted(cfg.explicit_keys), "values": values,
           "deprecated_aliases": dict(_KEY_ALIASES)}
    if include_schema:
        out["schema"] = _SCHEMA
    return out


def _config_target(config: str | None, cbenchtest: str | None) -> Path:
    found = config_path(config)
    if found:
        return found
    if config:
        return Path(config)
    return _cbenchtest(cbenchtest) / "cluster.yaml"


def set_config(updates: dict | None = None, remove: list[str] | None = None,
               config: str | None = None, cbenchtest: str | None = None,
               confirm: bool = False) -> dict:
    """Change top-level cluster.yaml keys. The result is schema-validated before
    anything is written; without confirm only the diff is returned."""
    updates, remove = dict(updates or {}), list(remove or [])
    if not updates and not remove:
        raise ToolError("nothing to change: pass updates and/or remove")
    path = _config_target(config, cbenchtest)
    exists = path.is_file()
    text = path.read_text() if exists else ""
    old = (yaml.safe_load(text) or {}) if exists else {}
    if not isinstance(old, dict):
        raise ToolError(f"{path} is not a YAML mapping")
    new = {k: v for k, v in old.items() if k not in remove}
    unknown = [k for k in remove if k not in old]
    new.update(updates)
    try:
        check_config_data(json.loads(json.dumps(new)), path)   # validate a copy
    except ConfigError as exc:
        raise ToolError(str(exc)) from exc
    diff = {
        "set": {k: {"old": old.get(k), "new": v} for k, v in updates.items() if old.get(k) != v},
        "removed": [k for k in remove if k in old],
    }
    out: dict = {"config_file": str(path), "creates_file": not exists, "diff": diff}
    if unknown:
        out["not_in_file"] = unknown
    if "#" in text:
        out["note"] = "the file has comments; rewriting it drops them (the old file is kept as .bak)"
    if not diff["set"] and not diff["removed"]:
        return {**out, "confirmed": confirm, "changed": False}
    if not confirm:
        return {**out, "confirmed": False, "next": "call again with confirm=true to write it"}
    path.parent.mkdir(parents=True, exist_ok=True)
    if exists:
        shutil.copy2(path, path.with_name(path.name + ".bak"))
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(yaml.safe_dump(new, sort_keys=False, default_flow_style=False))
    tmp.replace(path)
    return {**out, "confirmed": True, "changed": True,
            "backup": str(path.with_name(path.name + ".bak")) if exists else None}


#: template stems that are pieces of job scripts, not benchmarks
_NOT_BENCHMARK = re.compile(r"_(header|footer|dat|txt)$")


def list_testsets(config: str | None = None) -> dict:
    """Testsets gen-jobs can generate (from the templates), and IO profiles."""
    from cbench.templates import _templates_dir
    tdir = _templates_dir()
    testsets: dict[str, list[str]] = {}
    for t in sorted(tdir.glob("*_*.in")):
        if _NOT_BENCHMARK.search(t.stem):
            continue
        ts, bench = t.stem.split("_", 1)
        testsets.setdefault(ts, []).append(bench)
    cfg = load_config(config)
    try:
        custom = profiles.custom_profiles(cfg.io_profiles or {}, tdir)
        profile_error = None
    except profiles.ProfileError as exc:
        custom, profile_error = {}, str(exc)
    profs = {}
    for name, p in {**profiles.PROFILES, **custom}.items():
        profs[name] = {
            "custom": name in custom, "description": p.description,
            "default_groups": list(p.default_groups),
            "groups": {g: {"target": grp.target,
                           "members": [f"{m.home}_{m.benchmark}" for m in grp.members]}
                       for g, grp in p.groups.items()},
        }
    out = {"templates_dir": str(tdir), "testsets": testsets, "profiles": profs}
    if profile_error:
        out["custom_profile_error"] = profile_error
    return out


def node_facts(name: str | None = None, cbenchtest: str | None = None) -> dict:
    """List the nodecheck facts files, or show one (verdict, aggregate, hosts)."""
    ct = _cbenchtest(cbenchtest)
    if not name:
        return {"facts": _facts_files(ct)}
    try:
        path = nodecheck.facts_path(ct, name)
    except nodecheck.NodecheckError as exc:
        raise ToolError(str(exc)) from exc
    if not path.is_file():
        raise ToolError(f"no facts file {path} (run nodecheck first)")
    d = json.loads(path.read_text())
    warnings = []
    try:
        _facts, warnings = nodecheck.load_facts(ct, name)
    except nodecheck.NodecheckError as exc:
        warnings = [str(exc)]
    return {"path": str(path), "created": d.get("created"), "schema_version": d.get("schema_version"),
            "nodelist": d.get("nodelist"), "hosts": d.get("hosts"), "verdict": d.get("verdict"),
            "aggregate": d.get("aggregate"), "warnings": warnings}


def watch_jobs(testset: str, ident: str, cbenchtest: str | None = None,
               config: str | None = None, stale_after: int | None = None) -> dict:
    """Each job's state from its heartbeat file (cbench watch)."""
    ident_dir = _ident_dir(cbenchtest, testset, ident)
    if not ident_dir.is_dir():
        raise ToolError(f"no jobs at {ident_dir} (run gen_jobs first)")
    cfg = load_config(config)
    st = watch.scan(ident_dir, default_interval=cfg.job_heartbeat_s or 60, stale_after=stale_after)
    counts: dict[str, int] = {}
    for s in st:
        counts[s.status] = counts.get(s.status, 0) + 1
    return {"testset": testset, "ident": ident, "counts": counts,
            "all_done": watch.all_done(st), "succeeded": watch.succeeded(st),
            "jobs": [dataclasses.asdict(s) for s in st]}


def query_results(benchmark: str | None = None, testset: str | None = None,
                  ident: str | None = None, status: str | None = None,
                  cluster: str | None = None, since: str | None = None,
                  until: str | None = None, limit: int = 100,
                  cbenchtest: str | None = None) -> dict:
    """Parsed results from the results database, newest first, with metrics."""
    db = _cbenchtest(cbenchtest) / "cbench_results.db"
    if not db.is_file():
        raise ToolError(f"no results database at {db} (run parse_results first)")
    rows = ResultsDB(db).query(benchmark=benchmark, testset=testset, ident=ident, status=status,
                               cluster=cluster, since=since, until=until,
                               limit=max(1, min(limit, 5000)))
    return {"count": len(rows), "results": rows}


# ---------------------------------------------------------------------------
# dependencies and updates
# ---------------------------------------------------------------------------

#: missing command -> what to install (RHEL-family / Debian-family package names)
_PACKAGES = {
    "mpicc": "openmpi-devel (dnf) / libopenmpi-dev (apt), or load an MPI module",
    "mpicxx": "openmpi-devel (dnf) / libopenmpi-dev (apt), or load an MPI module",
    "mpif90": "openmpi-devel (dnf) / libopenmpi-dev (apt), or load an MPI module",
    "mpirun": "openmpi (dnf) / openmpi-bin (apt), or load an MPI module",
    "orterun": "openmpi (dnf) / openmpi-bin (apt), or load an MPI module",
    "gfortran": "gcc-gfortran (dnf) / gfortran (apt)",
    "cc": "gcc", "gcc": "gcc", "g++": "gcc-c++ (dnf) / g++ (apt)", "make": "make",
    "git": "git", "autoconf": "autoconf", "automake": "automake", "libtool": "libtool",
    "fio": "fio", "pdsh": "pdsh plus pdsh-rcmd-ssh (EPEL)", "ssh": "openssh-clients",
    "findmnt": "util-linux", "sbatch": "the Slurm client (slurm)", "qsub": "the Torque/PBS client",
    "bsub": "the LSF client",
}
_BATCH_CMD = {"slurm": "sbatch", "torque": "qsub", "pbspro": "qsub", "lsf": "bsub", "moab": "msub"}


def _suggest(tool: str) -> str:
    return _PACKAGES.get(tool.split()[0], "") or "install it, or put it on PATH"


def check_deps(benchmarks: list[str] | None = None, prefix: str | None = None,
               config: str | None = None) -> dict:
    """What's missing to generate, run and build benchmarks on this host, with
    suggestions. Never installs anything."""
    from cbench.builders import REGISTRY
    from cbench.cli.build import BuildLock

    cfg = load_config(config)
    tools: dict[str, str] = {}
    if cfg.batch_method in _BATCH_CMD:
        tools[_BATCH_CMD[cfg.batch_method]] = f"batch_method {cfg.batch_method}"
    if cfg.joblaunch_method == "openmpi" and not cfg.joblaunch_cmd:
        tools["mpirun"] = "joblaunch_method openmpi (mpirun or orterun)"
    tools[cfg.remotecmd_method] = f"remotecmd_method {cfg.remotecmd_method} (nodecheck)"
    tools["fio"] = "fio, the default node-local IO benchmark"
    tools["findmnt"] = "nodecheck's filesystem probe (falls back to stat -f)"
    system = []
    for tool, why in tools.items():
        found = shutil.which(tool) or (tool == "mpirun" and shutil.which("orterun"))
        system.append({"tool": tool, "needed_for": why, "found": bool(found),
                       **({} if found else {"suggest": _suggest(tool)})})

    names = benchmarks or sorted(REGISTRY)
    unknown = [n for n in names if n not in REGISTRY]
    if unknown:
        raise ToolError(f"unknown benchmark(s): {', '.join(unknown)}; known: {', '.join(sorted(REGISTRY))}")
    pre = Path(prefix or os.environ.get("CBENCHTEST", "."))
    lock = BuildLock(pre)
    builds = []
    for n in names:
        b = REGISTRY[n]()
        entry = lock._data.get(n) or {}
        bins = entry.get("binaries", [])
        built = bool(bins) and all((pre / "bin" / x).exists() or (pre / "bin" / "hwtests" / x).exists()
                                   for x in bins)
        missing = b.check_requires()
        row: dict = {"benchmark": n, "built": built, "optional": b.optional}
        if entry.get("built_at"):
            row["built_at"] = entry["built_at"]
        if missing:
            row["missing"] = [{"requirement": m, "suggest": _suggest(m)} for m in missing]
        if not built:
            row["next"] = ("install the missing requirements first (an admin task)" if missing
                           else f"build_benchmark('{n}') can build it")
        builds.append(row)
    return {"prefix": str(pre), "system": system, "benchmarks": builds,
            "note": "cbench never installs system packages; it can build its own benchmarks "
                    "(build_benchmark, with confirm)"}


def check_updates(benchmarks: list[str] | None = None, prefix: str | None = None) -> dict:
    """Newer upstream versions of benchmark sources (network lookups, report only)."""
    from cbench.builders import REGISTRY
    names = benchmarks or sorted(REGISTRY)
    unknown = [n for n in names if n not in REGISTRY]
    if unknown:
        raise ToolError(f"unknown benchmark(s): {', '.join(unknown)}")
    pre = Path(prefix or os.environ.get("CBENCHTEST", "."))
    checks = [dataclasses.asdict(upstream.check_builder(REGISTRY[n](), pre / "src")) for n in names]
    return {"checks": checks, "updates": [c["name"] for c in checks if c["status"] == upstream.UPDATE]}


# ---------------------------------------------------------------------------
# side-effecting (confirm)
# ---------------------------------------------------------------------------

def run_nodecheck(nodelist: str | None = None, partition: str | None = None,
                  ignore: str | None = None, name: str | None = None,
                  allow_heterogeneous: bool = False, cbenchtest: str | None = None,
                  config: str | None = None, confirm: bool = False) -> dict:
    """Probe a node pool (pdsh/ssh) and write $CBENCHTEST/nodefacts/<name>.json."""
    if bool(nodelist) == bool(partition):
        raise ToolError("pass exactly one of nodelist or partition")
    ct = _cbenchtest(cbenchtest)
    args = ["nodecheck"]
    for flag, val in (("--nodelist", nodelist), ("--partition", partition), ("--ignore", ignore),
                      ("--name", name), ("--allow-heterogeneous", allow_heterogeneous),
                      ("--cbenchtest", str(ct)), ("--config", config)):
        _opt(args, flag, val)
    if not confirm:
        return _plan(args, "runs a read-only probe on each node over pdsh/ssh and writes "
                           "the node facts file")
    out = _run_cli(args, str(ct))
    if out["ok"]:
        out["facts"] = node_facts(name or load_config(config).cluster_name, str(ct))
    return out


def gen_jobs(ident: str, testset: str | None = None, profile: str | None = None,
             groups: list[str] | None = None, nodefacts: str | None = None,
             ppn: str | None = None, maxprocs: int | None = None, match: str | None = None,
             nodelist: str | None = None, concurrent: bool = False,
             heartbeat: int | None = None, fio_runtime: int | None = None,
             io500_stonewall: int | None = None, run_type: str = "both",
             cbenchtest: str | None = None, config: str | None = None,
             confirm: bool = False) -> dict:
    """Generate job scripts for a testset or IO profile under $CBENCHTEST/<testset>/<ident>."""
    if bool(testset) == bool(profile):
        raise ToolError("pass exactly one of testset or profile")
    if run_type not in ("batch", "interactive", "both"):
        raise ToolError("run_type must be batch, interactive or both")
    ct = _cbenchtest(cbenchtest)
    target = _name(testset or profile, "testset/profile")
    args = ["gen-jobs", "--ident", _name(ident, "ident")]
    for flag, val in (("--testset", testset), ("--profile", profile), ("--group", groups),
                      ("--nodefacts", nodefacts), ("--ppn", ppn), ("--maxprocs", maxprocs),
                      ("--match", match), ("--nodelist", nodelist), ("--concurrent", concurrent),
                      ("--heartbeat", heartbeat), ("--fio-runtime", fio_runtime),
                      ("--io500-stonewall", io500_stonewall), ("--run-type", run_type),
                      ("--cbenchtest", str(ct)), ("--config", config)):
        _opt(args, flag, val)
    if not confirm:
        return _plan(args, f"writes job scripts under {ct / target / ident}")
    out = _run_cli(args, str(ct))
    jobdir = ct / target / ident
    if jobdir.is_dir():
        out["jobs"] = sorted(p.name for p in jobdir.iterdir() if p.is_dir())
    return out


def start_jobs(testset: str, ident: str, mode: str = "batch", match: str | None = None,
               exclude: str | None = None, minprocs: int | None = None,
               maxprocs: int | None = None, concurrent: bool = False,
               cbenchtest: str | None = None, config: str | None = None,
               confirm: bool = False) -> dict:
    """Submit generated jobs to the batch system, or run them interactively on
    this host (detached: returns a task id)."""
    if mode not in ("batch", "interactive"):
        raise ToolError("mode must be batch or interactive")
    ident_dir = _ident_dir(cbenchtest, testset, ident)
    if not ident_dir.is_dir():
        raise ToolError(f"no jobs at {ident_dir} (run gen_jobs first)")
    ct = str(_cbenchtest(cbenchtest))
    args = ["start-jobs", "--testset", testset, "--ident", ident, f"--{mode}"]
    for flag, val in (("--match", match), ("--exclude", exclude), ("--minprocs", minprocs),
                      ("--maxprocs", maxprocs), ("--concurrent", concurrent),
                      ("--cbenchtest", ct), ("--config", config)):
        _opt(args, flag, val)
    if not confirm:
        what = ("submits the jobs to the batch system" if mode == "batch" else
                "runs the jobs on this host in the background (benchmarks write data and "
                "load the machine; IO jobs fill their targets while running)")
        return _plan(args, what)
    if mode == "interactive":
        return start_task(args, ct, "start-jobs")
    return _run_cli(args, ct)


def parse_results(testset: str, ident: str, store: bool = True,
                  cbenchtest: str | None = None, config: str | None = None) -> dict:
    """Parse the jobs' output and (by default) store the results in the DB.
    Idempotent: re-parsing a run overwrites its rows."""
    ident_dir = _ident_dir(cbenchtest, testset, ident)
    if not ident_dir.is_dir():
        raise ToolError(f"no jobs at {ident_dir}")
    ct = str(_cbenchtest(cbenchtest))
    args = ["parse", "--testset", testset, "--ident", ident, "--output", "json",
            "--cbenchtest", ct]
    _opt(args, "--config", config)
    _opt(args, "--no-db", not store)
    out = _run_cli(args, ct)
    results_file = ident_dir / "results.json"
    if out["ok"] and results_file.is_file():
        results = json.loads(results_file.read_text())
        counts: dict[str, int] = {}
        for r in results:
            key = r["status"].split("(")[0]
            counts[key] = counts.get(key, 0) + 1
        out.update(results=results, counts=counts)
        out.pop("output", None)
    return out


def build_benchmark(benchmark: str, force: bool = False, prefix: str | None = None,
                    cbenchtest: str | None = None, confirm: bool = False) -> dict:
    """Download and build one of cbench's benchmark builders (detached task)."""
    from cbench.builders import REGISTRY
    if benchmark not in REGISTRY:
        raise ToolError(f"unknown benchmark {benchmark!r}; known: {', '.join(sorted(REGISTRY))}")
    b = REGISTRY[benchmark]()
    missing = b.check_requires()
    ct = str(_cbenchtest(cbenchtest))
    args = ["build", "run", benchmark]
    _opt(args, "--prefix", prefix)
    _opt(args, "--force", force)
    if missing:
        return {"confirmed": False, "refused": True,
                "missing": [{"requirement": m, "suggest": _suggest(m)} for m in missing],
                "effect": "can't build: system requirements are missing (an admin installs them)"}
    if not confirm:
        return _plan(args, f"downloads {b.source_url} and compiles it into "
                           f"{prefix or ct}/bin", source=b.source_url)
    return start_task(args, ct, "build")
