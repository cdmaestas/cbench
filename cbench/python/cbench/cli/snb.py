"""cbench snb — single-node benchmark run and report (port of single_node_benchmark.pl).

Usage:
  cbench snb run    [--ident ID] [--destdir DIR] [--tests REGEX] [--numcores N] [--store]
  cbench snb report [--ident ID] [--destdir DIR] [--node HOSTNAME] [--output table|json]
  cbench snb store  [--ident ID] [--destdir DIR] [--node HOSTNAME]
  cbench snb compare --ident ID --baseline ID [--node HOSTNAME] [--threshold PCT]
"""

from __future__ import annotations

import os
import re
import shlex
import socket
import subprocess
import time
from datetime import datetime
from pathlib import Path
from statistics import mean

import click
from rich.console import Console
from rich.table import Table

from cbench import fioprofile, iosizing

console = Console()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _hostname() -> str:
    return socket.gethostname()


def _detect_cores() -> int:
    return os.cpu_count() or 1


def _detect_physical_cores(cpuinfo_path: str | Path = Path("/proc/cpuinfo")) -> int:
    """Distinct (physical id, core id) pairs in /proc/cpuinfo; 0 if unknown
    (non-Linux, or cpuinfo without core ids). Mirrors the nodecheck probe."""
    try:
        text = Path(cpuinfo_path).read_text()
    except OSError:
        return 0
    pairs, phys = set(), ""
    for line in text.splitlines():
        key, _, val = line.partition(":")
        key = key.strip()
        if key == "physical id":
            phys = val.strip()
        elif key == "core id":
            pairs.add((phys, val.strip()))
    return len(pairs)


# ---------------------------------------------------------------------------
# node-aware fio helpers (see CLAUDE.md / session design)
# ---------------------------------------------------------------------------

_FIO_DIRECT_SIZE = fioprofile.DATA_SIZE  # fixed per-job size on the O_DIRECT path
_FIO_DIRECT_SIZE_BYTES = fioprofile.DATA_SIZE_BYTES
_FIO_CAPACITY_FRACTION = 0.9  # never plan to fill more than 90% of a target


def _read_memtotal_bytes(meminfo_path: str | Path = Path("/proc/meminfo")) -> int:
    """Return MemTotal in bytes from /proc/meminfo, or 0 if unavailable."""
    try:
        for line in Path(meminfo_path).read_text().splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) * 1024  # kB -> bytes
    except (OSError, ValueError, IndexError):
        pass
    return 0


def _detect_fstype(
    path: str | Path,
    mountinfo_path: str | Path = Path("/proc/self/mountinfo"),
) -> str:
    """Return the filesystem type for *path* by longest-mountpoint-prefix match
    against mountinfo. Returns 'unknown' off-Linux or on any error."""
    try:
        target = os.path.realpath(str(path))
        content = Path(mountinfo_path).read_text()
    except OSError:
        return "unknown"

    best_mp = ""
    best_fs = "unknown"
    for line in content.splitlines():
        # "<id> <par> <dev> <root> <mountpoint> <opts> [opt...] - <fstype> <src> <superopts>"
        if " - " not in line:
            continue
        left, right = line.split(" - ", 1)
        lfields = left.split()
        rfields = right.split()
        if len(lfields) < 5 or not rfields:
            continue
        mountpoint = lfields[4]
        fstype = rfields[0]
        if target == mountpoint or target.startswith(mountpoint.rstrip("/") + "/"):
            if len(mountpoint) >= len(best_mp):
                best_mp = mountpoint
                best_fs = fstype
    return best_fs


def _supports_odirect(directory: str | Path) -> bool:
    """Probe whether O_DIRECT is usable for files in *directory*."""
    flag = getattr(os, "O_DIRECT", None)
    if flag is None:  # non-Linux (e.g. macOS dev)
        return False
    probe = Path(directory) / ".cbench_odirect_probe"
    try:
        fd = os.open(str(probe), os.O_WRONLY | os.O_CREAT | flag, 0o600)
    except OSError:
        return False
    else:
        os.close(fd)
        return True
    finally:
        try:
            os.unlink(str(probe))
        except OSError:
            pass


def _fio_buffered_size_bytes(
    mem_total_bytes: int, numjobs: int, free_bytes: int
) -> tuple[int, bool]:
    """Per-job fio file size for the buffered (non-O_DIRECT) path.

    Targets 2x MemTotal aggregate to defeat the page cache, divided across
    *numjobs*. If that would exceed 90% of free space, caps to fit and returns
    caveat=True (the result may be cache-influenced).
    """
    numjobs = max(1, numjobs)
    target_aggregate = 2 * mem_total_bytes
    free_cap = int(free_bytes * _FIO_CAPACITY_FRACTION)
    caveat = target_aggregate > free_cap
    aggregate = min(target_aggregate, free_cap)
    per_job = max(aggregate // numjobs, 1)
    return per_job, caveat


def _fio_direct_space_shortfall(numjobs: int, free_bytes: int) -> tuple[int, int] | None:
    """(needed, usable) bytes when the O_DIRECT runs won't fit, else None.

    Each fio job lays out its own --size file and the target is emptied between
    the sequential (1 job) and random (*numjobs*) runs, so the peak is
    numjobs x the fixed direct size. Usable space is 90% of free.
    """
    needed = fioprofile.peak_bytes(numjobs, _FIO_DIRECT_SIZE_BYTES)
    usable = int(free_bytes * _FIO_CAPACITY_FRACTION)
    return (needed, usable) if needed > usable else None


def _clean_fio_dir(fio_dir: Path, log_fh) -> None:
    """Remove fio's data files so the next run starts from an empty target."""
    for tmp in fio_dir.glob("*"):
        try:
            tmp.unlink()
        except OSError as e:
            _logmsg(log_fh, f"WARNING: could not remove fio temp file {tmp}: {e}")


def _fio_benchmark_name(fstype: str, path: str | Path) -> str:
    """Encode an fs target into a distinct benchmark name (node identity stays
    in jobname). ('gpfs', '/gpfs/scratch') -> 'snb_fio_gpfs_scratch'."""
    base = os.path.basename(str(path).rstrip("/")) or "root"
    safe = re.sub(r"[^A-Za-z0-9]+", "_", f"{fstype}_{base}").strip("_")
    return f"snb_fio_{safe}"


# `snb report` row order for fio metrics (cbench.fioprofile job set first)
_FIO_REPORT_ORDER = (
    "seq_read_bw_MiB_s", "seq_write_bw_MiB_s",
    "rand_read_iops", "rand_write_iops", "rand_read_bw_MiB_s", "rand_write_bw_MiB_s",
    "rand_read_lat_avg_us", "rand_write_lat_avg_us", "rand_read_lat_p99_us", "rand_write_lat_p99_us",
    "create_ops", "stat_ops", "delete_ops",
)

# Marker written into the fio output file before each target's runs so the
# collector can split one file into per-target results.
_FIO_TARGET_MARKER = "### CBENCH FS-TARGET"


def _logmsg(log_fh, msg: str) -> None:
    ts = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    line = f"{ts} {msg}"
    log_fh.write(line + "\n")
    log_fh.flush()
    console.print(line)


#: Interval (seconds) between "still running" heartbeats for long commands.
_HEARTBEAT_SECS = 30.0


def _fmt_elapsed(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}m{s:02d}s" if m else f"{s}s"


def _cmd_label(cmd: str | list[str]) -> str:
    """Short identifier for heartbeat lines (program name + fio --name if any)."""
    if isinstance(cmd, str):
        parts = cmd.split()
        return parts[0] if parts else cmd
    if not cmd:
        return "?"
    base = os.path.basename(cmd[0])
    name = next((a.split("=", 1)[1] for a in cmd if a.startswith("--name=")), "")
    return f"{base} {name}".strip()


def _emit(log_fh, msg: str) -> None:
    """Write to the log file if present, else to the console."""
    if log_fh:
        _logmsg(log_fh, msg)
    else:
        console.print(msg)


def _runcmd(
    cmd: str | list[str],
    outfile: Path,
    *,
    overwrite: bool = False,
    dry_run: bool = False,
    log_fh=None,
    cwd: Path | None = None,
    heartbeat: float = _HEARTBEAT_SECS,
) -> None:
    """Run a command (string for trusted shell cmds, list for user-derived args).

    Strings are run with shell=True (only use for hardcoded commands).
    Lists are run with shell=False to prevent injection.

    While the command runs, a "still running (elapsed)" heartbeat is emitted
    every *heartbeat* seconds so a long test (fio, linpack, hpcc) is visibly
    alive rather than indistinguishable from a hang. Set heartbeat<=0 to disable.
    """
    display = cmd if isinstance(cmd, str) else " ".join(shlex.quote(a) for a in cmd)
    arrow = ">" if overwrite else ">>"
    msg = f"RUNCMD: {display} {arrow} {outfile}"
    if log_fh:
        _logmsg(log_fh, msg)
    if dry_run:
        return
    mode = "w" if overwrite else "a"
    label = _cmd_label(cmd)
    with open(outfile, mode) as fh:
        use_shell = isinstance(cmd, str)
        # nosec B602 / noqa S602: shell=True only for str cmds, which are
        # hardcoded by callers (see docstring); user-derived args use lists.
        proc = subprocess.Popen(  # noqa: S602 # nosec B602
            cmd, shell=use_shell, stdout=fh, stderr=subprocess.STDOUT, cwd=cwd
        )
        start = time.monotonic()
        next_beat = start + heartbeat
        try:
            while True:
                try:
                    proc.wait(timeout=1.0)
                    break
                except subprocess.TimeoutExpired:
                    now = time.monotonic()
                    if heartbeat > 0 and now >= next_beat:
                        _emit(log_fh, f"... still running ({_fmt_elapsed(now - start)}): {label}")
                        next_beat = now + heartbeat
        except BaseException:
            # Ctrl-C or other interruption: don't orphan the child.
            proc.kill()
            proc.wait()
            raise
    if proc.returncode != 0:
        msg = f"WARNING: command exited {proc.returncode}: {display}"
        if log_fh:
            _logmsg(log_fh, msg)
        else:
            console.print(f"[yellow]{msg}[/yellow]")


# ---------------------------------------------------------------------------
# output file parsers (for report command)
# ---------------------------------------------------------------------------

def _parse_streams_out(outfile: Path) -> dict[str, float]:
    """Return {operation: MB/s} from a STREAM output file."""
    if not outfile.exists():
        return {}
    result: dict[str, float] = {}
    for line in outfile.read_text(errors="replace").splitlines():
        # "Copy:       12345.67      0.0010  ..."
        m = re.match(r"(\w+):\s+(\d+\.\d+)", line)
        if m:
            result[m.group(1).lower()] = float(m.group(2))
    return result


def _parse_cachebench_out(outfile: Path) -> dict[str, float]:
    """Return {context: avg_MB/s} from a cachebench --lmbench output file."""
    if not outfile.exists():
        return {}
    data: dict[str, list[float]] = {}
    ctx = "unknown"
    for line in outfile.read_text(errors="replace").splitlines():
        m = re.search(r"====> (\S+)", line)
        if m:
            ctx = m.group(1)
            continue
        m2 = re.match(r"\d+\s+(\d+\.\d+)", line)
        if m2:
            data.setdefault(ctx, []).append(float(m2.group(1)))
    return {k: mean(v) for k, v in data.items() if v}


def _parse_dgemm_out(outfile: Path) -> dict[int, float]:
    """Return {mem_mb: avg_gflops} from nodeperf2-nompi output file."""
    if not outfile.exists():
        return {}
    data: dict[int, list[float]] = {}
    for line in outfile.read_text(errors="replace").splitlines():
        m = re.search(
            r"NN lda=\d+ ldb=\s*\d+ ldc=\d+ \d+ \d+ \d+ (\d+\.\d+) mem=(\d+) MB", line
        )
        if m:
            data.setdefault(int(m.group(2)), []).append(float(m.group(1)))
    return {mem: mean(vals) for mem, vals in data.items()}


def _generate_hpl_dat(cfg, numcores: int) -> str:
    """Return HPL.dat content sized to ~50% of node memory with a P×Q grid."""
    import math
    mem_mb = cfg.memory_per_node_mb
    n = int(math.sqrt(0.5 * mem_mb * 1024 * 1024 / 8))
    n = max((n // 256) * 256, 256)
    p, q = 1, numcores
    for pp in range(1, numcores + 1):
        qq = numcores // pp
        if pp * qq == numcores and pp <= qq:
            p, q = pp, qq
    return (
        "HPLinpack benchmark input file\n"
        "Innovative Computing Laboratory, University of Tennessee\n"
        "HPL.out  output file name (if any)\n"
        "6        device out (6=stdout,7=stderr,file)\n"
        "1        # of problems sizes (N)\n"
        f"{n}       Ns\n"
        "1        # of NBs\n"
        "192      NBs\n"
        "0        PMAP process mapping (0=Row-,1=Column-major)\n"
        "1        # of process grids (P x Q)\n"
        f"{p}        Ps\n"
        f"{q}        Qs\n"
        "16.0     threshold\n"
        "1        # of panel fact\n"
        "2        PFACTs (0=left, 1=Crout, 2=Right)\n"
        "1        # of recursive stopping criterium\n"
        "4        NBMINs (>= 1)\n"
        "1        # of panels in recursion\n"
        "2        NDIVs\n"
        "1        # of recursive panel fact.\n"
        "1        RFACTs (0=left, 1=Crout, 2=Right)\n"
        "1        # of broadcast\n"
        "1        BCASTs (0=1rg,1=1rM,2=2rg,3=2rM,4=Lng,5=LnM)\n"
        "1        # of lookahead depth\n"
        "1        DEPTHs (>=0)\n"
        "2        SWAP (0=bin-exch,1=long,2=mix)\n"
        "64       swapping threshold\n"
        "0        L1 in (0=transposed,1=no-transposed) form\n"
        "0        U  in (0=transposed,1=no-transposed) form\n"
        "1        Equilibration (0=no,1=yes)\n"
        "8        memory alignment in double (> 0)\n"
        "##### This line (no. 32) is ignored (it serves as a separator). ######\n"
        "0                               Number of additional problem sizes for PTRANS\n"
        "1200 10000 30000                values of N\n"
        "0                               number of additional blocking sizes for PTRANS\n"
        "40 9 8 13 13 20 16 32 64        values of NB\n"
    )


def _parse_linpack_out(outfile: Path) -> dict[str, float]:
    """Return xhpl metrics from an SNB linpack output file."""
    if not outfile.exists():
        return {}
    from cbench.parsers.xhpl import XhplParser
    result = XhplParser().parse(outfile.read_text(errors="replace"))
    return result.metrics if result.status == "PASSED" else {}


def _parse_npb_out(outfile: Path) -> dict[str, float]:
    """Return {<suite>_mops: val} from a concatenated NPB output file."""
    if not outfile.exists():
        return {}
    from cbench.parsers.npb import NpbParser
    text = outfile.read_text(errors="replace")
    # Split at each benchmark header; each section starts with "NAS Parallel Benchmarks"
    parts = re.split(r"(?=.*NAS Parallel Benchmarks)", text, flags=re.MULTILINE)
    metrics: dict[str, float] = {}
    parser = NpbParser()
    for part in parts:
        if "NAS Parallel Benchmarks" not in part:
            continue
        m = re.search(r"NAS Parallel Benchmarks[^-]*-\s*(\w+)\s+Benchmark", part)
        suite = m.group(1).lower() if m else "npb"
        result = parser.parse(part)
        if result.status == "PASSED" and "mops" in result.metrics:
            metrics[f"{suite}_mops"] = result.metrics["mops"]
    return metrics


def _parse_fio_out(outfile: Path) -> dict[str, float]:
    """Return fio metrics dict from an snb fio output file (first/only target).

    Back-compat helper used by the report text table; for per-target results
    use _parse_fio_targets().
    """
    if not outfile.exists():
        return {}
    from cbench.parsers.fio import FioParser
    result = FioParser().parse(outfile.read_text(errors="replace"))
    return result.metrics if result.status == "PASSED" else {}


def _parse_fio_targets(outfile: Path) -> list[tuple[str, str, str, dict[str, float]]]:
    """Split a per-target fio output file into (benchmark, status, status_detail, metrics).

    The run side writes a '### CBENCH FS-TARGET path=.. fstype=.. odirect=.. caveat=..'
    marker before each target's fio output. A target skipped for lack of space
    has a marker with ``skipped=insufficient_space`` and comes back as a NOTICE
    with no metrics. If no markers are present (e.g. an older single-target
    file) returns one ('snb_fio', 'PASSED', '', metrics) entry.
    """
    if not outfile.exists():
        return []
    from cbench.parsers.fio import FioParser

    text = outfile.read_text(errors="replace")
    if _FIO_TARGET_MARKER not in text:
        metrics = _parse_fio_out(outfile)
        return [("snb_fio", "PASSED", "", metrics)] if metrics else []

    results: list[tuple[str, str, str, dict[str, float]]] = []
    header: dict[str, str] | None = None
    buf: list[str] = []

    def _flush() -> None:
        if header is None:
            return
        path = header.get("path", "")
        fstype = header.get("fstype", "unknown")
        if header.get("skipped"):
            detail = (
                f"path={path} fstype={fstype} skipped: {header['skipped'].replace('_', ' ')} "
                f"(need {header.get('need_kb', '?')} kB, usable {header.get('usable_kb', '?')} kB)"
            )
            results.append((_fio_benchmark_name(fstype, path), "NOTICE", detail, {}))
            return
        parsed = FioParser().parse("\n".join(buf))
        if parsed.status != "PASSED" or not parsed.metrics:
            return
        detail = (
            f"path={path} fstype={fstype} "
            f"odirect={header.get('odirect', '?')} caveat={header.get('caveat', '0')}"
        )
        if "profile" in header:
            detail += (f" profile={header['profile']} seq_bs={header.get('seq_bs', '?')} "
                       f"runtime_s={header.get('runtime_s', '?')}")
        if header.get("caveat") == "1":
            detail += " (result may be cache-influenced)"
        if header.get("md") == "0":
            detail += " (metadata ops not measured: fio lacks filecreate/filestat/filedelete)"
        results.append((_fio_benchmark_name(fstype, path), "PASSED", detail, parsed.metrics))

    for line in text.splitlines():
        if line.startswith(_FIO_TARGET_MARKER):
            _flush()
            header = dict(
                re.findall(r"(\w+)=(\S+)", line[len(_FIO_TARGET_MARKER):])
            )
            buf = []
        else:
            buf.append(line)
    _flush()
    return results


def _parse_hpcc_out(outfile: Path) -> dict[str, float]:
    """Return selected HPCC metrics from an snb hpcc output file."""
    if not outfile.exists():
        return {}
    from cbench.parsers.hpcc import HpccParser
    result = HpccParser().parse(outfile.read_text(errors="replace"))
    return result.metrics if result.status == "PASSED" else {}


def _parse_mpistreams_out(outfile: Path) -> dict[int, dict[str, float]]:
    """Return {nprocs: {operation: MB/s}} from mpistreams output file."""
    if not outfile.exists():
        return {}
    data: dict[int, dict[str, float]] = {}
    np = 0
    for line in outfile.read_text(errors="replace").splitlines():
        m = re.search(r"====> (\d+) processes", line)
        if m:
            np = int(m.group(1))
            continue
        m2 = re.match(r"(\w+):\s+(\d+\.\d+)", line)
        if m2 and np:
            data.setdefault(np, {})[m2.group(1).lower()] = float(m2.group(2))
    return data


# ---------------------------------------------------------------------------
# SNB → DB: collect all metrics from saved output files
# ---------------------------------------------------------------------------

def _collect_snb_metrics(
    ident_dir: Path,
    hostname: str,
    cluster: str,
    ident: str,
    numcores: int,
) -> list:
    """Parse all snb output files and return a list of db.ParseResult objects."""
    from cbench.db import ParseResult as DBResult

    def outfile(tag: str) -> Path:
        return ident_dir / f"{hostname}.snb.{tag}.out"

    results = []

    def _make(
        benchmark: str,
        metrics: dict[str, float],
        units: dict[str, str],
        status_detail: str = "",
        status: str = "PASSED",
    ) -> None:
        # a NOTICE (e.g. fio target skipped for space) is kept with no metrics
        if metrics or status != "PASSED":
            results.append(DBResult(
                cluster=cluster,
                testset="snb",
                ident=ident,
                jobname=hostname,
                benchmark=benchmark,
                numprocs=numcores,
                ppn=numcores,
                numnodes=1,
                status=status,
                status_detail=status_detail,
                metrics=metrics,
                metric_units=units,
            ))

    # streams
    streams = _parse_streams_out(outfile("streams"))
    _make("snb_streams", streams, dict.fromkeys(streams, "MB/s"))

    # cachebench
    cb = _parse_cachebench_out(outfile("cachebench"))
    _make("snb_cachebench", cb, dict.fromkeys(cb, "MB/s"))

    # dgemm — flatten {mem_mb: gflops} → {"gflops_<mem>mb": val}
    dgemm_raw = _parse_dgemm_out(outfile("nodeperf2"))
    dgemm = {f"gflops_{mem}mb": gf for mem, gf in dgemm_raw.items()}
    _make("snb_dgemm", dgemm, dict.fromkeys(dgemm, "GFlops"))

    # mpistreams — flatten {nprocs: {op: val}} → {"<op>_<n>proc": val}
    ms_raw = _parse_mpistreams_out(outfile("mpistreams"))
    ms: dict[str, float] = {}
    ms_units: dict[str, str] = {}
    for np_count, ops in ms_raw.items():
        for op, val in ops.items():
            key = f"{op}_{np_count}proc"
            ms[key] = val
            ms_units[key] = "MB/s"
    _make("snb_mpistreams", ms, ms_units)

    # fio — one result per --fs-target (benchmark name encodes the target)
    fio_units = {
        "read_bw_MiB_s": "MiB/s", "write_bw_MiB_s": "MiB/s",
        "read_iops": "IOPS", "write_iops": "IOPS",
        "read_lat_avg_us": "us", "write_lat_avg_us": "us",
        "read_lat_p99_us": "us", "write_lat_p99_us": "us",
    }
    for benchmark, status, detail, fio_metrics in _parse_fio_targets(outfile("fio")):
        _make(
            benchmark,
            fio_metrics,
            {k: fio_units.get(k, "") for k in fio_metrics},
            status_detail=detail,
            status=status,
        )

    # hpcc
    hpcc = _parse_hpcc_out(outfile("hpcc"))
    from cbench.parsers.hpcc import HpccParser
    hpcc_units = HpccParser().metric_units()
    _make("snb_hpcc", hpcc, {k: hpcc_units.get(k, "") for k in hpcc})

    # linpack (xhpl)
    from cbench.parsers.xhpl import XhplParser
    linpack = _parse_linpack_out(outfile("linpack"))
    xhpl_units = XhplParser().metric_units()
    _make("snb_linpack", linpack, {k: xhpl_units.get(k, "") for k in linpack})

    # npb
    npb = _parse_npb_out(outfile("npb"))
    _make("snb_npb", npb, dict.fromkeys(npb, "Mop/s"))

    return results


def _store_snb_results(
    ident_dir: Path,
    hostname: str,
    cluster: str,
    ident: str,
    numcores: int,
    log_fh=None,
) -> int:
    """Parse output files and store all metrics to the results DB. Returns row count."""
    import os
    from cbench.db import ResultsDB

    cbenchtest = os.environ.get("CBENCHTEST", ".")
    db_path = Path(cbenchtest) / "cbench_results.db"
    db = ResultsDB(db_path)
    rows = _collect_snb_metrics(ident_dir, hostname, cluster, ident, numcores)
    for r in rows:
        db.store(r)
    msg = f"Stored {len(rows)} SNB result(s) to {db_path}"
    if log_fh:
        _logmsg(log_fh, msg)
    else:
        console.print(msg)
    return len(rows)


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------

@click.group("snb")
def snb_group() -> None:
    """Single-node benchmark suite: run benchmarks and report results."""


# ---------------------------------------------------------------------------
# snb run
# ---------------------------------------------------------------------------

def _build_remote_cmd(
    cfg,
    *,
    remote_node: str,
    ident: str,
    destdir: str,
    numcores: int,
    tests: str,
    binpath: str | None,
    mpi_cmd: str,
    dry_run: bool,
    store: bool,
    config: str | None,
    remote_cbench: str = "cbench",
    fs_target: tuple[str, ...] = (),
    heartbeat: float = _HEARTBEAT_SECS,
    io_profile: str | None = None,
    fio_runtime: int | None = None,
) -> list[str]:
    """Return the argv list to dispatch `cbench snb run` to a remote node."""
    import shlex as _shlex

    inner = [
        remote_cbench, "snb", "run",
        "--ident", ident,
        "--destdir", destdir,
        "--node", remote_node,
        "--numcores", str(numcores),
        "--tests", tests,
        "--mpi-cmd", mpi_cmd,
        "--heartbeat", str(heartbeat),
    ]
    for tgt in fs_target:
        inner += ["--fs-target", tgt]
    if io_profile:
        inner += ["--io-profile", io_profile]
    if fio_runtime:
        inner += ["--fio-runtime", str(fio_runtime)]
    if binpath:
        inner += ["--binpath", binpath]
    if config:
        inner += ["--config", config]
    if dry_run:
        inner.append("--dry-run")
    if store:
        inner.append("--store")

    inner_str = " ".join(_shlex.quote(a) for a in inner)
    extra = cfg.remotecmd_extraargs or ""

    if cfg.remotecmd_method == "ssh":
        cmd = ["ssh"] + (_shlex.split(extra) if extra else []) + [remote_node, inner_str]
    else:
        # pdsh
        cmd = ["pdsh"] + (_shlex.split(extra) if extra else []) + ["-w", remote_node, inner_str]
    return cmd


@snb_group.command("run")
@click.option("--ident", default=None, help="Test identifier (default: <cluster>1)")
@click.option("--destdir", default=".", show_default=True, type=click.Path(),
              help="Directory for output files")
@click.option("--node", default=None, help="Override hostname")
@click.option("--remote", default=None, metavar="NODE",
              help="Dispatch run to a remote node via ssh/pdsh (shared filesystem required)")
@click.option("--remote-cbench", default="cbench", show_default=True,
              help="Path to the cbench binary on the remote node")
@click.option("--numcores", default=None, type=int,
              help="CPU core count (default: auto-detected)")
@click.option("--fs-target", "fs_target", multiple=True, type=click.Path(),
              help="Filesystem path to target for fio I/O tests. Repeatable. "
                   "Required when fio is selected via --tests (fio is opt-in).")
@click.option("--io-profile", "--fio-profile", "io_profile",
              type=click.Choice(fioprofile.PROFILE_CHOICES), default=None,
              help="IO workload profile setting the fio sequential block size: ai 1m, general "
                   "4m, hpc 8m, streaming 16m; auto = hpc on a parallel filesystem, else general "
                   "(default: cluster.yaml io_profile, else auto). --fio-profile is an alias.")
@click.option("--fio-runtime", type=click.IntRange(min=1), default=None, metavar="SECONDS",
              help="Time cap per fio job (default: cluster.yaml fio_runtime_s, else 300)")
@click.option("--tests",
              default="stream|cachebench|dgemm|mpistreams|linpack|npb|hpcc",
              show_default=True,
              help="Pipe-separated regex of tests to run")
@click.option("--binpath", default=None, envvar="CBENCH_BINPATH",
              help="Path to benchmark binary directory (default: $CBENCHOME/bin/hwtests)")
@click.option("--mpi-cmd", default="mpirun", show_default=True,
              help="MPI launch command for mpistreams")
@click.option("--heartbeat", default=_HEARTBEAT_SECS, show_default=True, type=float,
              help="Seconds between 'still running' progress lines for long tests (<=0 disables)")
@click.option("--dry-run", is_flag=True, help="Print commands without executing")
@click.option("--store", is_flag=True, help="Store results in SQLite DB after running")
@click.option("--config", default=None)
def run_cmd(
    ident: str | None,
    destdir: str,
    node: str | None,
    remote: str | None,
    remote_cbench: str,
    numcores: int | None,
    fs_target: tuple[str, ...],
    io_profile: str | None,
    fio_runtime: int | None,
    tests: str,
    binpath: str | None,
    mpi_cmd: str,
    heartbeat: float,
    dry_run: bool,
    store: bool,
    config: str | None,
) -> None:
    """Run the single-node benchmark suite and save output files."""
    from functools import partial

    from cbench.config import load_config

    # All test commands run through this partial so --heartbeat applies uniformly.
    runcmd = partial(_runcmd, heartbeat=heartbeat)

    cfg = load_config(config)

    # fio is opt-in and needs an explicit filesystem to target.
    if re.search(r"\bfio\b", tests) and not fs_target:
        raise click.UsageError(
            "fio is selected but no --fs-target was given. fio I/O tests must "
            "target an explicit filesystem path, e.g. --fs-target /gpfs/scratch "
            "(repeatable). Omit fio from --tests to run the rest of the suite."
        )

    if remote:
        # Validate the remote node name before using it in a command
        if "/" in remote or "\\" in remote or remote.startswith("..") or " " in remote:
            raise click.UsageError(f"Invalid --remote value: '{remote}'")
        numcores = numcores or _detect_cores()
        ident = ident or f"{cfg.cluster_name}1"
        cmd = _build_remote_cmd(
            cfg,
            remote_node=remote,
            ident=ident,
            destdir=str(Path(destdir).resolve()),
            numcores=numcores,
            tests=tests,
            fs_target=fs_target,
            io_profile=io_profile,
            fio_runtime=fio_runtime,
            binpath=binpath,
            mpi_cmd=mpi_cmd,
            heartbeat=heartbeat,
            dry_run=dry_run,
            store=store,
            config=config,
            remote_cbench=remote_cbench,
        )
        import shlex as _shlex
        display = " ".join(_shlex.quote(a) for a in cmd)
        console.print(f"[bold]Dispatching to {remote} via {cfg.remotecmd_method}:[/bold] {display}")
        if not dry_run:
            result = subprocess.run(cmd)
            if result.returncode != 0:
                raise SystemExit(result.returncode)
        return

    hostname = node or _hostname()
    if "/" in hostname or "\\" in hostname or hostname.startswith(".."):
        raise click.UsageError(f"Invalid --node value: '{hostname}'")
    explicit_numcores = numcores is not None
    numcores = numcores or _detect_cores()
    ident = ident or f"{cfg.cluster_name}1"

    destdir_p = Path(destdir).resolve()
    ident_dir = (destdir_p / ident).resolve()
    if not ident_dir.is_relative_to(destdir_p):
        raise click.UsageError(
            f"Path traversal detected: ident '{ident}' escapes destdir"
        )
    ident_dir.mkdir(parents=True, exist_ok=True)

    cbenchome = os.environ.get("CBENCHOME", ".")
    binpath_p = Path(binpath) if binpath else Path(cbenchome) / "bin" / "hwtests"

    logfile = destdir_p / f"snb.{hostname}.{ident}.log"

    def out(tag: str) -> Path:
        return ident_dir / f"{hostname}.snb.{tag}.out"

    with open(logfile, "a") as log:
        _logmsg(log, f"INITIATING Single Node Benchmarking RUN on "
                     f"node={hostname} ident={ident} tests={tests}")

        def run(cmd: str, tag: str, overwrite: bool = False) -> None:
            runcmd(cmd, out(tag), overwrite=overwrite, dry_run=dry_run, log_fh=log)

        # Basic node info
        run("uname -s -r -m -p -i -o", "uname", overwrite=True)
        run("cat /proc/cpuinfo", "cpuinfo", overwrite=True)
        run("cat /proc/meminfo", "meminfo", overwrite=True)

        # ------------------------------------------------------------------
        # streams
        # ------------------------------------------------------------------
        if re.search(r"stream", tests):
            _logmsg(log, "Starting STREAMS testing")
            # Run any stream-* binaries found (excluding MPI variants)
            if binpath_p.exists():
                stream_bins = [
                    b for b in sorted(binpath_p.glob("stream-*"))
                    if "mpi" not in b.name.lower()
                ]
            else:
                stream_bins = []
            if stream_bins:
                run("true", "streams", overwrite=True)
                for b in stream_bins:
                    runcmd([str(b)], out("streams"), overwrite=False, dry_run=dry_run, log_fh=log)
            else:
                _logmsg(log, f"WARNING: no stream-* binaries found in {binpath_p}")

        # ------------------------------------------------------------------
        # cachebench
        # ------------------------------------------------------------------
        if re.search(r"cachebench", tests):
            _logmsg(log, "Starting CACHEBENCH testing")
            cb = binpath_p / "cachebench"
            if cb.exists():
                runcmd([str(cb), "--lmbench"], out("cachebench"), overwrite=True, dry_run=dry_run, log_fh=log)
            else:
                _logmsg(log, f"WARNING: cachebench not found at {cb}")

        # ------------------------------------------------------------------
        # dgemm (nodeperf2-nompi)
        # ------------------------------------------------------------------
        if re.search(r"dgemm", tests):
            _logmsg(log, "Starting DGEMM (nodeperf2-nompi) testing")
            # look in bin/ parent directory and in binpath
            np2_candidates = [
                binpath_p.parent / "nodeperf2-nompi",
                binpath_p / "nodeperf2-nompi",
            ]
            np2 = next((p for p in np2_candidates if p.exists()), None)
            if np2:
                run("true", "nodeperf2", overwrite=True)
                n = 2
                while n <= 2048:
                    iters = max(2, int(20000 / n))
                    if iters % 2 == 1:
                        iters += 1
                    env = dict(os.environ, OMP_NUM_THREADS=str(numcores))
                    for _ in range(3):
                        if dry_run:
                            _logmsg(log, f"DRYRUN: OMP_NUM_THREADS={numcores} {np2} -i {iters} -s {n}")
                        else:
                            with open(out("nodeperf2"), "a") as fh:
                                r = subprocess.run(
                                    [str(np2), "-i", str(iters), "-s", str(n)],
                                    env=env, stdout=fh, stderr=subprocess.STDOUT,
                                )
                            if r.returncode != 0:
                                _logmsg(log, f"WARNING: nodeperf2 exited {r.returncode} (n={n})")
                    n = max(n + 1, int(n * 1.5))
            else:
                _logmsg(log, f"WARNING: nodeperf2-nompi not found in {binpath_p}")

        # ------------------------------------------------------------------
        # mpistreams
        # ------------------------------------------------------------------
        if re.search(r"mpistreams", tests):
            _logmsg(log, "Starting Multi-Process STREAMS (MPI streams) testing")
            stream_mpi = binpath_p / "stream-mpi"
            if stream_mpi.exists():
                run("true", "mpistreams", overwrite=True)
                for np in range(1, numcores + 1):
                    marker = f"====> {np} processes"
                    if dry_run:
                        _logmsg(log, f"DRYRUN: {mpi_cmd} -n {np} {stream_mpi}")
                    else:
                        with open(out("mpistreams"), "a") as fh:
                            fh.write(f"{marker}\n")
                            r = subprocess.run(
                                shlex.split(mpi_cmd) + ["-n", str(np), str(stream_mpi)],
                                shell=False, stdout=fh, stderr=subprocess.STDOUT,
                            )
                        if r.returncode != 0:
                            _logmsg(log, f"WARNING: mpistreams exited {r.returncode} (np={np})")
            else:
                _logmsg(log, f"WARNING: stream-mpi not found at {stream_mpi}")

        # ------------------------------------------------------------------
        # linpack — direct xhpl invocation with auto-generated HPL.dat
        # ------------------------------------------------------------------
        if re.search(r"linpack", tests):
            _logmsg(log, "Starting Linpack (xhpl) testing")
            xhpl_candidates = [binpath_p / "xhpl", binpath_p.parent / "xhpl"]
            xhpl_bin = next((p for p in xhpl_candidates if p.exists()), None)
            if not xhpl_bin:
                import shutil as _shutil
                found = _shutil.which("xhpl")
                xhpl_bin = Path(found) if found else None
            if xhpl_bin:
                hpl_content = _generate_hpl_dat(cfg, numcores)
                linpack_dir = ident_dir / "linpack_run"
                if not dry_run:
                    linpack_dir.mkdir(exist_ok=True)
                    (linpack_dir / "HPL.dat").write_text(hpl_content)
                else:
                    _logmsg(log, f"DRYRUN: would write HPL.dat to {linpack_dir}")
                runcmd(
                    [str(xhpl_bin)],
                    out("linpack"), overwrite=True, dry_run=dry_run, log_fh=log,
                    cwd=linpack_dir,
                )
            else:
                _logmsg(log, "WARNING: xhpl binary not found on PATH or in binpath, skipping linpack")

        # ------------------------------------------------------------------
        # npb — direct invocation of NPB suite binaries
        # ------------------------------------------------------------------
        if re.search(r"npb", tests):
            _logmsg(log, "Starting NAS Parallel Benchmark testing")
            # Preferred suites: EP (CPU FP), CG (memory + sparse comm)
            npb_suites = ["EP", "CG"]
            npb_classes = ["B", "A", "C"]
            first_npb = True
            found_any_npb = False
            for suite in npb_suites:
                npb_bin = None
                for cls in npb_classes:
                    binary_name = f"{suite}.{cls}.x"
                    candidates = [binpath_p / binary_name, binpath_p.parent / binary_name]
                    npb_bin = next((p for p in candidates if p.exists()), None)
                    if not npb_bin:
                        import shutil as _shutil
                        found = _shutil.which(binary_name)
                        npb_bin = Path(found) if found else None
                    if npb_bin:
                        break
                if npb_bin:
                    found_any_npb = True
                    runcmd(
                        [mpi_cmd, "-np", str(numcores), str(npb_bin)],
                        out("npb"), overwrite=first_npb, dry_run=dry_run, log_fh=log,
                    )
                    first_npb = False
            if not found_any_npb:
                _logmsg(log, "WARNING: no NPB binaries found (EP.B.x etc.), skipping npb")

        # ------------------------------------------------------------------
        # fio — flexible I/O benchmark (sequential and random 4K)
        # ------------------------------------------------------------------
        if re.search(r"\bfio\b", tests):
            _logmsg(log, "Starting FIO storage I/O testing")
            import shutil
            fio_bin = binpath_p.parent / "fio"
            if not fio_bin.exists():
                fio_found = shutil.which("fio")
                fio_bin = Path(fio_found) if fio_found else None
            if not fio_bin:
                _logmsg(log, "WARNING: fio not found on PATH or in binpath")
            else:
                # one output file, one '### CBENCH FS-TARGET' section per target
                run("true", "fio", overwrite=True)
                # Random-I/O and metadata job count = IO thread count (the
                # iosizing.io_threads rule): every CPU of io_threads_basis,
                # capped by io_threads_max; an explicit --numcores is taken as
                # the count to use. The sequential job stays single-stream.
                io_cpus = numcores
                if cfg.io_threads_basis == "physical" and not explicit_numcores:
                    io_cpus = _detect_physical_cores() or numcores
                fio_numjobs = fioprofile.numjobs(iosizing.cap_threads(io_cpus, cfg))
                io_profile = io_profile or cfg.io_profile
                fio_runtime = fio_runtime or cfg.fio_runtime_s
                # metadata engines (filecreate/filestat/filedelete) need fio >= 3.23
                if dry_run:
                    fio_md = True
                else:
                    eng = subprocess.run([str(fio_bin), "--enghelp"], capture_output=True, text=True)
                    fio_md = fioprofile.has_metadata_engines(eng.stdout + eng.stderr)
                    if not fio_md:
                        _logmsg(log, f"WARNING: {fio_bin} lacks the filecreate/filestat/filedelete "
                                     "engines (needs fio >= 3.23); metadata ops not measured")
                for target in fs_target:
                    tgt = Path(target).resolve()
                    if not dry_run and not (tgt.is_dir() and os.access(tgt, os.W_OK)):
                        _logmsg(log, f"WARNING: --fs-target not a writable directory, skipping: {tgt}")
                        continue

                    fstype = _detect_fstype(tgt)
                    if fstype == "unknown":
                        _logmsg(log, f"WARNING: could not determine filesystem type for {tgt}; labeling 'unknown'")

                    fio_dir = tgt / f".cbench_fio.{ident}"
                    if not dry_run:
                        fio_dir.mkdir(parents=True, exist_ok=True)

                    direct = _supports_odirect(fio_dir if not dry_run else tgt)
                    caveat = False
                    if direct:
                        size_arg = _FIO_DIRECT_SIZE
                        free_bytes = shutil.disk_usage(str(tgt)).free if tgt.is_dir() else None
                        short = (_fio_direct_space_shortfall(fio_numjobs, free_bytes)
                                 if free_bytes is not None else None)
                        if short:
                            need_kb, usable_kb = short[0] // 1024, short[1] // 1024
                            _logmsg(log, f"WARNING: skipping fio on {fstype} ({tgt}): needs "
                                         f"{need_kb} kB ({fio_numjobs} x {_FIO_DIRECT_SIZE}) but only "
                                         f"{usable_kb} kB usable (90% of free)")
                            marker = (f"{_FIO_TARGET_MARKER} path={tgt} fstype={fstype} odirect=1 "
                                      f"skipped=insufficient_space need_kb={need_kb} "
                                      f"usable_kb={usable_kb}")
                            if not dry_run:
                                with open(out("fio"), "a") as fh:
                                    fh.write(marker + "\n")
                                try:
                                    fio_dir.rmdir()
                                except OSError as e:
                                    _logmsg(log, f"WARNING: could not remove fio temp dir {fio_dir}: {e}")
                            else:
                                _logmsg(log, f"DRYRUN: {marker}")
                            continue
                    else:
                        mem_total = _read_memtotal_bytes()
                        free_bytes = shutil.disk_usage(str(tgt)).free if not dry_run else 100 * 1024**3
                        if mem_total <= 0:
                            size_arg = fioprofile.BUFFERED_FALLBACK_SIZE
                            caveat = True
                            _logmsg(log, f"WARNING: O_DIRECT unavailable on {fstype} ({tgt}) and MemTotal unknown; "
                                         f"buffered run at {size_arg} may be cache-influenced")
                        else:
                            per_job, caveat = _fio_buffered_size_bytes(mem_total, fio_numjobs, free_bytes)
                            size_arg = str(per_job)
                            msg = (f"O_DIRECT unavailable on {fstype} ({tgt}); buffered fallback, "
                                   f"per-job size={per_job} bytes")
                            if caveat:
                                msg += " (capped by free space — result may be cache-influenced)"
                            _logmsg(log, "WARNING: " + msg)

                    profile, seq_bs = fioprofile.seq_block_size(io_profile, fstype, cfg.io_seq_bs)
                    marker = (f"{_FIO_TARGET_MARKER} path={tgt} fstype={fstype} "
                              f"odirect={int(direct)} caveat={int(caveat)} profile={profile} "
                              f"seq_bs={seq_bs} runtime_s={fio_runtime} md={int(fio_md)}")
                    if not dry_run:
                        with open(out("fio"), "a") as fh:
                            fh.write(marker + "\n")
                    else:
                        _logmsg(log, f"DRYRUN: {marker}")

                    jobs = fioprofile.data_jobs(
                        str(fio_bin), str(fio_dir), seq_bs=seq_bs, njobs=fio_numjobs,
                        runtime_s=fio_runtime, direct=direct, size=size_arg,
                    )
                    if fio_md:
                        jobs += fioprofile.metadata_jobs(
                            str(fio_bin), str(fio_dir), njobs=fio_numjobs, runtime_s=fio_runtime,
                        )
                    for _name, argv in jobs:
                        runcmd(argv, out("fio"), overwrite=False, dry_run=dry_run, log_fh=log)
                        # Empty the target between jobs: the space check and the
                        # buffered sizing budget one job's files, not several.
                        if not dry_run:
                            _clean_fio_dir(fio_dir, log)

                    if not dry_run:
                        try:
                            fio_dir.rmdir()
                        except OSError as e:
                            _logmsg(log, f"WARNING: could not remove fio temp dir {fio_dir}: {e}")

        # ------------------------------------------------------------------
        # hpcc — HPC Challenge (HPL + STREAM + DGEMM + FFT + RandomAccess)
        # ------------------------------------------------------------------
        if re.search(r"\bhpcc\b", tests):
            _logmsg(log, "Starting HPCC (HPC Challenge) testing")
            hpcc_candidates = [
                binpath_p / "hpcc",
                binpath_p.parent / "hpcc",
            ]
            hpcc_bin = next((p for p in hpcc_candidates if p.exists()), None)
            if not hpcc_bin:
                import shutil
                found = shutil.which("hpcc")
                hpcc_bin = Path(found) if found else None
            if hpcc_bin:
                hpl_dat = _generate_hpl_dat(cfg, numcores)
                hpcc_dir = ident_dir / "hpcc_run"
                if not dry_run:
                    hpcc_dir.mkdir(exist_ok=True)
                    (hpcc_dir / "HPL.dat").write_text(hpl_dat)
                else:
                    _logmsg(log, f"DRYRUN: would write HPL.dat (sized for {numcores} cores) to {hpcc_dir}")
                runcmd(
                    [str(hpcc_bin)],
                    out("hpcc"), overwrite=True, dry_run=dry_run, log_fh=log,
                    cwd=hpcc_dir,
                )
                # Also capture hpccoutf.txt if produced
                hpcc_out_f = hpcc_dir / "hpccoutf.txt"
                if not dry_run and hpcc_out_f.exists():
                    with open(out("hpcc"), "a") as fh:
                        fh.write("\n--- hpccoutf.txt ---\n")
                        fh.write(hpcc_out_f.read_text(errors="replace"))
            else:
                _logmsg(log, "WARNING: hpcc binary not found on PATH or in binpath")

        _logmsg(
            log,
            f"Finished running the Single Node Benchmarks. "
            f"Run `cbench snb report --ident {ident} --destdir {destdir}` to view results.",
        )

        if store and not dry_run:
            _store_snb_results(ident_dir, hostname, cfg.cluster_name, ident, numcores, log)


# ---------------------------------------------------------------------------
# snb report
# ---------------------------------------------------------------------------

@snb_group.command("report")
@click.option("--ident", default=None, help="Test identifier")
@click.option("--destdir", default=".", show_default=True, type=click.Path())
@click.option("--node", default=None, help="Hostname of benchmarked node (default: current host)")
@click.option("--output", "output_fmt", default="table",
              type=click.Choice(["table", "json"]), show_default=True,
              help="Output format")
@click.option("--store", is_flag=True, help="Store results in SQLite DB")
@click.option("--config", default=None)
def report_cmd(
    ident: str | None,
    destdir: str,
    node: str | None,
    output_fmt: str,
    store: bool,
    config: str | None,
) -> None:
    """Parse snb output files and display a summary report."""
    from cbench.config import load_config

    cfg = load_config(config)
    hostname = node or _hostname()
    # Sanitize hostname: reject path separators to prevent traversal in file names
    if "/" in hostname or "\\" in hostname or hostname.startswith(".."):
        raise click.UsageError(f"Invalid --node value: '{hostname}'")
    ident = ident or f"{cfg.cluster_name}1"
    destdir_p = Path(destdir).resolve()
    ident_dir = (destdir_p / ident).resolve()
    if not ident_dir.is_relative_to(destdir_p):
        raise click.UsageError(
            f"Path traversal detected: ident '{ident}' escapes destdir"
        )

    if not ident_dir.exists():
        console.print(f"[red]Directory not found: {ident_dir}[/red]")
        raise SystemExit(1)

    numcores = _detect_cores()

    def out(tag: str) -> Path:
        return ident_dir / f"{hostname}.snb.{tag}.out"

    # JSON output: collect all metrics and dump
    if output_fmt == "json":
        import json
        collected = _collect_snb_metrics(ident_dir, hostname, cfg.cluster_name, ident, numcores)
        payload = {
            "cluster": cfg.cluster_name,
            "ident": ident,
            "node": hostname,
            "benchmarks": {r.benchmark: r.metrics for r in collected},
        }
        click.echo(json.dumps(payload, indent=2))
        if store:
            _store_snb_results(ident_dir, hostname, cfg.cluster_name, ident, numcores)
        return

    console.rule(f"[bold]Single Node Benchmark Report — {hostname}")

    # Basic node info
    uname_f = out("uname")
    if uname_f.exists():
        console.print(f"[bold]Node:[/bold]  {hostname}")
        console.print(f"[bold]Ident:[/bold] {ident}")
        console.print(uname_f.read_text(errors="replace").strip())

    any_results = False

    # ------------------------------------------------------------------
    # STREAM
    # ------------------------------------------------------------------
    streams = _parse_streams_out(out("streams"))
    if streams:
        any_results = True
        console.rule("[bold]STREAM Results")
        tbl = Table(box=None, padding=(0, 2))
        tbl.add_column("Operation")
        tbl.add_column("MB/s", justify="right")
        for op, val in sorted(streams.items()):
            tbl.add_row(op.capitalize(), f"{val:.1f}")
        console.print(tbl)

    # ------------------------------------------------------------------
    # Cachebench
    # ------------------------------------------------------------------
    cb = _parse_cachebench_out(out("cachebench"))
    if cb:
        any_results = True
        console.rule("[bold]Cachebench Results")
        tbl = Table(box=None, padding=(0, 2))
        tbl.add_column("Test")
        tbl.add_column("Avg MB/s", justify="right")
        for test, val in sorted(cb.items()):
            tbl.add_row(test, f"{val:.1f}")
        console.print(tbl)

    # ------------------------------------------------------------------
    # DGEMM (nodeperf2)
    # ------------------------------------------------------------------
    dgemm = _parse_dgemm_out(out("nodeperf2"))
    if dgemm:
        any_results = True
        console.rule("[bold]DGEMM Results (nodeperf2-nompi)")
        tbl = Table(box=None, padding=(0, 2))
        tbl.add_column("Memory (MB)", justify="right")
        tbl.add_column("Avg GFlops", justify="right")
        for mem, gf in sorted(dgemm.items()):
            tbl.add_row(str(mem), f"{gf:.2f}")
        console.print(tbl)

    # ------------------------------------------------------------------
    # MPI Streams
    # ------------------------------------------------------------------
    mpistreams = _parse_mpistreams_out(out("mpistreams"))
    if mpistreams:
        any_results = True
        console.rule("[bold]Multi-Process STREAMS Results")
        ops = sorted({op for d in mpistreams.values() for op in d})
        tbl = Table(box=None, padding=(0, 2))
        tbl.add_column("Processes", justify="right")
        for op in ops:
            tbl.add_column(f"{op.capitalize()} MB/s", justify="right")
        for np, data in sorted(mpistreams.items()):
            tbl.add_row(str(np), *[f"{data.get(op, 0):.1f}" for op in ops])
        console.print(tbl)

    # ------------------------------------------------------------------
    # fio
    # ------------------------------------------------------------------
    fio_targets = _parse_fio_targets(out("fio"))
    if fio_targets:
        any_results = True
        console.rule("[bold]FIO I/O Results")
        for benchmark, status, detail, metrics in fio_targets:
            console.print(f"[bold]{benchmark}[/bold]  {status}  [dim]{detail}[/dim]")
            if not metrics:
                continue
            tbl = Table(box=None, padding=(0, 2))
            tbl.add_column("Metric")
            tbl.add_column("Value", justify="right")
            ordered = [k for k in _FIO_REPORT_ORDER if k in metrics]
            ordered += sorted(k for k in metrics if k not in _FIO_REPORT_ORDER)
            for key in ordered:
                tbl.add_row(key, f"{metrics[key]:.1f}")
            console.print(tbl)

    # ------------------------------------------------------------------
    # hpcc
    # ------------------------------------------------------------------
    hpcc_metrics = _parse_hpcc_out(out("hpcc"))
    if hpcc_metrics:
        any_results = True
        console.rule("[bold]HPCC Results")
        tbl = Table(box=None, padding=(0, 2))
        tbl.add_column("Metric")
        tbl.add_column("Value", justify="right")
        for key, val in sorted(hpcc_metrics.items()):
            tbl.add_row(key, f"{val:.4g}")
        console.print(tbl)

    # ------------------------------------------------------------------
    # Linpack
    # ------------------------------------------------------------------
    linpack_metrics = _parse_linpack_out(out("linpack"))
    if linpack_metrics:
        any_results = True
        console.rule("[bold]Linpack (xhpl) Results")
        tbl = Table(box=None, padding=(0, 2))
        tbl.add_column("Metric")
        tbl.add_column("Value", justify="right")
        for key, val in sorted(linpack_metrics.items()):
            tbl.add_row(key, f"{val:.4g}")
        console.print(tbl)

    # ------------------------------------------------------------------
    # NPB
    # ------------------------------------------------------------------
    npb_metrics = _parse_npb_out(out("npb"))
    if npb_metrics:
        any_results = True
        console.rule("[bold]NAS Parallel Benchmark Results")
        tbl = Table(box=None, padding=(0, 2))
        tbl.add_column("Suite")
        tbl.add_column("Mop/s", justify="right")
        for key, val in sorted(npb_metrics.items()):
            suite = key.replace("_mops", "").upper()
            tbl.add_row(suite, f"{val:.1f}")
        console.print(tbl)

    if not any_results:
        console.print(
            "[yellow]No parsed results found. "
            f"Run `cbench snb run --ident {ident} --destdir {destdir}` first.[/yellow]"
        )
    elif store:
        _store_snb_results(ident_dir, hostname, cfg.cluster_name, ident, numcores)


# ---------------------------------------------------------------------------
# snb store
# ---------------------------------------------------------------------------

@snb_group.command("store")
@click.option("--ident", default=None, help="Test identifier")
@click.option("--destdir", default=".", show_default=True, type=click.Path())
@click.option("--node", default=None, help="Hostname (default: current host)")
@click.option("--numcores", default=None, type=int, help="CPU core count (default: auto-detected)")
@click.option("--config", default=None)
def store_cmd(
    ident: str | None,
    destdir: str,
    node: str | None,
    numcores: int | None,
    config: str | None,
) -> None:
    """Parse saved snb output files and store all metrics to the SQLite DB."""
    from cbench.config import load_config

    cfg = load_config(config)
    hostname = node or _hostname()
    if "/" in hostname or "\\" in hostname or hostname.startswith(".."):
        raise click.UsageError(f"Invalid --node value: '{hostname}'")
    ident = ident or f"{cfg.cluster_name}1"
    numcores = numcores or _detect_cores()
    destdir_p = Path(destdir).resolve()
    ident_dir = (destdir_p / ident).resolve()
    if not ident_dir.is_relative_to(destdir_p):
        raise click.UsageError(f"Path traversal detected: ident '{ident}' escapes destdir")
    if not ident_dir.exists():
        console.print(f"[red]Directory not found: {ident_dir}[/red]")
        raise SystemExit(1)
    _store_snb_results(ident_dir, hostname, cfg.cluster_name, ident, numcores)


# ---------------------------------------------------------------------------
# snb compare
# ---------------------------------------------------------------------------

@snb_group.command("compare")
@click.option("--ident", required=True, help="Current run identifier")
@click.option("--baseline", required=True, help="Baseline run identifier to compare against")
@click.option("--node", default=None, help="Hostname (default: current host)")
@click.option("--threshold", default=5.0, show_default=True, type=float,
              help="Regression threshold in percent (absolute change)")
@click.option("--config", default=None)
def compare_cmd(
    ident: str,
    baseline: str,
    node: str | None,
    threshold: float,
    config: str | None,
) -> None:
    """Compare SNB results for two idents from the SQLite DB and flag regressions."""
    import os
    from cbench.config import load_config
    from cbench.db import ResultsDB

    cfg = load_config(config)
    hostname = node or _hostname()
    if "/" in hostname or "\\" in hostname or hostname.startswith(".."):
        raise click.UsageError(f"Invalid --node value: '{hostname}'")

    cbenchtest = os.environ.get("CBENCHTEST", ".")
    db_path = Path(cbenchtest) / "cbench_results.db"
    if not db_path.exists():
        console.print(f"[red]No results DB found at {db_path}. Run `cbench snb store` first.[/red]")
        raise SystemExit(1)

    db = ResultsDB(db_path)

    def _fetch(run_ident: str) -> dict[str, dict[str, float]]:
        """Return {benchmark: {metric: value}} for the given ident+node."""
        rows = db.query(testset="snb", ident=run_ident, cluster=cfg.cluster_name)
        result: dict[str, dict[str, float]] = {}
        for row in rows:
            if row["jobname"] != hostname:
                continue
            bm = row["benchmark"]
            result[bm] = {k: v["value"] for k, v in row["metrics"].items()}
        return result

    current = _fetch(ident)
    base = _fetch(baseline)

    if not current:
        console.print(f"[red]No SNB results for ident='{ident}' node='{hostname}' in DB.[/red]")
        raise SystemExit(1)
    if not base:
        console.print(f"[red]No SNB results for baseline='{baseline}' node='{hostname}' in DB.[/red]")
        raise SystemExit(1)

    console.rule(f"[bold]SNB Comparison: {baseline} → {ident}  (node: {hostname})")

    all_benchmarks = sorted(set(current) | set(base))
    regressions = 0

    for bm in all_benchmarks:
        cur_metrics = current.get(bm, {})
        base_metrics = base.get(bm, {})
        all_keys = sorted(set(cur_metrics) | set(base_metrics))
        if not all_keys:
            continue

        tbl = Table(title=bm, box=None, padding=(0, 2))
        tbl.add_column("Metric")
        tbl.add_column("Baseline", justify="right")
        tbl.add_column("Current", justify="right")
        tbl.add_column("Change %", justify="right")
        tbl.add_column("Status")

        for key in all_keys:
            b_val = base_metrics.get(key)
            c_val = cur_metrics.get(key)
            if b_val is None:
                tbl.add_row(key, "—", f"{c_val:.4g}", "—", "[yellow]NEW[/yellow]")
                continue
            if c_val is None:
                tbl.add_row(key, f"{b_val:.4g}", "—", "—", "[yellow]MISSING[/yellow]")
                continue
            if b_val == 0:
                pct = 0.0
            else:
                pct = (c_val - b_val) / abs(b_val) * 100.0
            pct_str = f"{pct:+.1f}%"
            if abs(pct) >= threshold:
                # Regressions: lower is worse for bandwidth/IOPS/GFlops; higher is worse for latency
                is_latency = "lat" in key or "latency" in key
                regressed = (pct < 0 and not is_latency) or (pct > 0 and is_latency)
                if regressed:
                    status = "[red]REGRESSED[/red]"
                    regressions += 1
                else:
                    status = "[green]IMPROVED[/green]"
            else:
                status = "[dim]OK[/dim]"
            tbl.add_row(key, f"{b_val:.4g}", f"{c_val:.4g}", pct_str, status)

        console.print(tbl)

    if regressions:
        console.print(f"\n[red bold]{regressions} regression(s) detected (threshold: {threshold}%)[/red bold]")
        raise SystemExit(1)
    console.print(f"\n[green bold]No regressions detected (threshold: {threshold}%)[/green bold]")
