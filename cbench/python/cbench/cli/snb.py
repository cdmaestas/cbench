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
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

console = Console()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _hostname() -> str:
    return socket.gethostname()


def _detect_cores() -> int:
    return os.cpu_count() or 1


def _logmsg(log_fh, msg: str) -> None:
    ts = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    line = f"{ts} {msg}"
    log_fh.write(line + "\n")
    log_fh.flush()
    console.print(line)


def _runcmd(
    cmd: "str | list[str]",
    outfile: Path,
    *,
    overwrite: bool = False,
    dry_run: bool = False,
    log_fh=None,
    cwd: "Optional[Path]" = None,
) -> None:
    """Run a command (string for trusted shell cmds, list for user-derived args).

    Strings are run with shell=True (only use for hardcoded commands).
    Lists are run with shell=False to prevent injection.
    """
    display = cmd if isinstance(cmd, str) else " ".join(shlex.quote(a) for a in cmd)
    arrow = ">" if overwrite else ">>"
    msg = f"RUNCMD: {display} {arrow} {outfile}"
    if log_fh:
        _logmsg(log_fh, msg)
    if dry_run:
        return
    mode = "w" if overwrite else "a"
    with open(outfile, mode) as fh:
        use_shell = isinstance(cmd, str)
        subprocess.run(cmd, shell=use_shell, stdout=fh, stderr=subprocess.STDOUT, cwd=cwd)


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


def _parse_fio_out(outfile: Path) -> dict[str, float]:
    """Return fio metrics dict from an snb fio output file."""
    if not outfile.exists():
        return {}
    from cbench.parsers.fio import FioParser
    result = FioParser().parse(outfile.read_text(errors="replace"))
    return result.metrics if result.status == "PASSED" else {}


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
) -> "list":
    """Parse all snb output files and return a list of db.ParseResult objects."""
    from cbench.db import ParseResult as DBResult

    def outfile(tag: str) -> Path:
        return ident_dir / f"{hostname}.snb.{tag}.out"

    results = []

    def _make(benchmark: str, metrics: dict[str, float], units: dict[str, str]) -> None:
        if metrics:
            results.append(DBResult(
                cluster=cluster,
                testset="snb",
                ident=ident,
                jobname=hostname,
                benchmark=benchmark,
                numprocs=numcores,
                ppn=numcores,
                numnodes=1,
                status="PASSED",
                metrics=metrics,
                metric_units=units,
            ))

    # streams
    streams = _parse_streams_out(outfile("streams"))
    _make("snb_streams", streams, {k: "MB/s" for k in streams})

    # cachebench
    cb = _parse_cachebench_out(outfile("cachebench"))
    _make("snb_cachebench", cb, {k: "MB/s" for k in cb})

    # dgemm — flatten {mem_mb: gflops} → {"gflops_<mem>mb": val}
    dgemm_raw = _parse_dgemm_out(outfile("nodeperf2"))
    dgemm = {f"gflops_{mem}mb": gf for mem, gf in dgemm_raw.items()}
    _make("snb_dgemm", dgemm, {k: "GFlops" for k in dgemm})

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

    # fio
    fio = _parse_fio_out(outfile("fio"))
    fio_units = {
        "read_bw_MiB_s": "MiB/s", "write_bw_MiB_s": "MiB/s",
        "read_iops": "IOPS", "write_iops": "IOPS",
        "read_lat_avg_us": "us", "write_lat_avg_us": "us",
        "read_lat_p99_us": "us", "write_lat_p99_us": "us",
    }
    _make("snb_fio", fio, {k: fio_units.get(k, "") for k in fio})

    # hpcc
    hpcc = _parse_hpcc_out(outfile("hpcc"))
    from cbench.parsers.hpcc import HpccParser
    hpcc_units = HpccParser().metric_units()
    _make("snb_hpcc", hpcc, {k: hpcc_units.get(k, "") for k in hpcc})

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

@snb_group.command("run")
@click.option("--ident", default=None, help="Test identifier (default: <cluster>1)")
@click.option("--destdir", default=".", show_default=True, type=click.Path(),
              help="Directory for output files")
@click.option("--node", default=None, help="Override hostname")
@click.option("--numcores", default=None, type=int,
              help="CPU core count (default: auto-detected)")
@click.option("--tests",
              default="stream|cachebench|dgemm|mpistreams|linpack|npb|fio|hpcc",
              show_default=True,
              help="Pipe-separated regex of tests to run")
@click.option("--binpath", default=None, envvar="CBENCH_BINPATH",
              help="Path to benchmark binary directory (default: $CBENCHOME/bin/hwtests)")
@click.option("--mpi-cmd", default="mpirun", show_default=True,
              help="MPI launch command for mpistreams")
@click.option("--dry-run", is_flag=True, help="Print commands without executing")
@click.option("--store", is_flag=True, help="Store results in SQLite DB after running")
@click.option("--config", default=None)
def run_cmd(
    ident: Optional[str],
    destdir: str,
    node: Optional[str],
    numcores: Optional[int],
    tests: str,
    binpath: Optional[str],
    mpi_cmd: str,
    dry_run: bool,
    store: bool,
    config: Optional[str],
) -> None:
    """Run the single-node benchmark suite and save output files."""
    from cbench.config import load_config
    from cbench.utils import is_power_of_two

    cfg = load_config(config)
    hostname = node or _hostname()
    if "/" in hostname or "\\" in hostname or hostname.startswith(".."):
        raise click.UsageError(f"Invalid --node value: '{hostname}'")
    numcores = numcores or _detect_cores()
    ident = ident or f"{cfg.cluster_name}1"

    destdir_p = Path(destdir).resolve()
    ident_dir = (destdir_p / ident).resolve()
    if not str(ident_dir).startswith(str(destdir_p)):
        raise click.UsageError(
            f"Path traversal detected: ident '{ident}' escapes destdir"
        )
    ident_dir.mkdir(parents=True, exist_ok=True)

    cbenchome = os.environ.get("CBENCHOME", ".")
    binpath = binpath or os.path.join(cbenchome, "bin", "hwtests")
    binpath_p = Path(binpath)

    logfile = destdir_p / f"snb.{hostname}.{ident}.log"

    def out(tag: str) -> Path:
        return ident_dir / f"{hostname}.snb.{tag}.out"

    with open(logfile, "a") as log:
        _logmsg(log, f"INITIATING Single Node Benchmarking RUN on "
                     f"node={hostname} ident={ident} tests={tests}")

        def run(cmd: str, tag: str, overwrite: bool = False) -> None:
            _runcmd(cmd, out(tag), overwrite=overwrite, dry_run=dry_run, log_fh=log)

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
                    _runcmd([str(b)], out("streams"), overwrite=False, dry_run=dry_run, log_fh=log)
            else:
                _logmsg(log, f"WARNING: no stream-* binaries found in {binpath_p}")

        # ------------------------------------------------------------------
        # cachebench
        # ------------------------------------------------------------------
        if re.search(r"cachebench", tests):
            _logmsg(log, "Starting CACHEBENCH testing")
            cb = binpath_p / "cachebench"
            if cb.exists():
                _runcmd([str(cb), "--lmbench"], out("cachebench"), overwrite=True, dry_run=dry_run, log_fh=log)
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
                                subprocess.run(
                                    [str(np2), "-i", str(iters), "-s", str(n)],
                                    env=env, stdout=fh, stderr=subprocess.STDOUT,
                                )
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
                            subprocess.run(
                                shlex.split(mpi_cmd) + ["-n", str(np), str(stream_mpi)],
                                shell=False, stdout=fh, stderr=subprocess.STDOUT,
                            )
            else:
                _logmsg(log, f"WARNING: stream-mpi not found at {stream_mpi}")

        # ------------------------------------------------------------------
        # linpack — delegate to cbench gen-jobs / start-jobs
        # ------------------------------------------------------------------
        if re.search(r"linpack", tests):
            _logmsg(log, "Starting Linpack testing")
            identbase = f"snb_{ident}"
            cbenchtest = os.environ.get("CBENCHTEST", ".")
            for threads in range(1, numcores + 1):
                count = numcores // threads
                for procs in range(1, count + 1):
                    if procs > 1 and not is_power_of_two(procs):
                        continue
                    if threads > 1 and not is_power_of_two(threads):
                        continue
                    sub_ident = f"{identbase}_{threads}threads"
                    gen_cmd = [
                        "cbench", "gen-jobs", "--testset", "linpack",
                        "--ident", sub_ident,
                        "--maxprocs", str(procs), "--ppn", str(procs),
                        "--cbenchtest", cbenchtest,
                    ]
                    start_cmd = [
                        "cbench", "start-jobs", "--testset", "linpack",
                        "--ident", sub_ident,
                        "--interactive", "--match", f"{procs}ppn",
                        "--cbenchtest", cbenchtest,
                    ]
                    run(gen_cmd, "linpack")
                    run(start_cmd, "linpack")

        # ------------------------------------------------------------------
        # npb — delegate to cbench gen-jobs / start-jobs
        # ------------------------------------------------------------------
        if re.search(r"npb", tests):
            _logmsg(log, "Starting NAS Parallel Benchmark testing")
            identbase = f"snb_{ident}"
            cbenchtest = os.environ.get("CBENCHTEST", ".")
            run("true", "npb", overwrite=True)
            run(
                ["cbench", "gen-jobs", "--testset", "npb",
                 "--ident", identbase, "--maxprocs", str(numcores),
                 "--cbenchtest", cbenchtest],
                "npb",
            )
            run(
                ["cbench", "start-jobs", "--testset", "npb",
                 "--ident", identbase, "--interactive",
                 "--maxprocs", str(numcores), "--cbenchtest", cbenchtest],
                "npb",
            )

        # ------------------------------------------------------------------
        # fio — flexible I/O benchmark (sequential and random 4K)
        # ------------------------------------------------------------------
        if re.search(r"\bfio\b", tests):
            _logmsg(log, "Starting FIO storage I/O testing")
            fio_bin = binpath_p.parent / "fio"
            if not fio_bin.exists():
                import shutil
                fio_found = shutil.which("fio")
                fio_bin = Path(fio_found) if fio_found else None
            if fio_bin:
                fio_dir = ident_dir / "fio_tmp"
                if not dry_run:
                    fio_dir.mkdir(exist_ok=True)
                run("true", "fio", overwrite=True)
                # Sequential 1 MiB block read/write
                _runcmd(
                    [
                        str(fio_bin),
                        "--name=seq_rw", "--rw=rw", "--bs=1m",
                        "--size=1g", "--numjobs=1", "--iodepth=8",
                        "--ioengine=libaio", "--direct=1",
                        "--directory", str(fio_dir),
                        "--output-format=normal",
                    ],
                    out("fio"), overwrite=False, dry_run=dry_run, log_fh=log,
                )
                # Random 4 KiB block read/write
                _runcmd(
                    [
                        str(fio_bin),
                        "--name=rand_rw", "--rw=randrw", "--bs=4k",
                        "--size=1g", "--numjobs=4", "--iodepth=32",
                        "--ioengine=libaio", "--direct=1",
                        "--directory", str(fio_dir),
                        "--output-format=normal",
                    ],
                    out("fio"), overwrite=False, dry_run=dry_run, log_fh=log,
                )
                # Clean up temp files
                if not dry_run:
                    for tmp in fio_dir.glob("*"):
                        try:
                            tmp.unlink()
                        except OSError:
                            pass
                    try:
                        fio_dir.rmdir()
                    except OSError:
                        pass
            else:
                _logmsg(log, "WARNING: fio not found on PATH or in binpath")

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
                import math
                # Generate a minimal HPL.dat sized to ~50% of available memory
                mem_mb = cfg.memory_per_node_mb
                # N ≈ sqrt(0.5 * mem_bytes / 8)
                n = int(math.sqrt(0.5 * mem_mb * 1024 * 1024 / 8))
                n = (n // 256) * 256  # round down to multiple of 256
                n = max(n, 256)
                # Find a P×Q grid close to square with P≤Q
                p, q = 1, numcores
                for pp in range(1, numcores + 1):
                    qq = numcores // pp
                    if pp * qq == numcores and pp <= qq:
                        p, q = pp, qq
                hpl_dat = (
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
                hpcc_dir = ident_dir / "hpcc_run"
                if not dry_run:
                    hpcc_dir.mkdir(exist_ok=True)
                    (hpcc_dir / "HPL.dat").write_text(hpl_dat)
                else:
                    _logmsg(log, f"DRYRUN: would write HPL.dat with N={n} P={p} Q={q} to {hpcc_dir}")
                _runcmd(
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
    ident: Optional[str],
    destdir: str,
    node: Optional[str],
    output_fmt: str,
    store: bool,
    config: Optional[str],
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
    if not str(ident_dir).startswith(str(destdir_p)):
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
    fio_metrics = _parse_fio_out(out("fio"))
    if fio_metrics:
        any_results = True
        console.rule("[bold]FIO I/O Results")
        tbl = Table(box=None, padding=(0, 2))
        tbl.add_column("Metric")
        tbl.add_column("Value", justify="right")
        for key in ("read_bw_MiB_s", "write_bw_MiB_s",
                    "read_iops", "write_iops",
                    "read_lat_avg_us", "write_lat_avg_us",
                    "read_lat_p99_us", "write_lat_p99_us"):
            if key in fio_metrics:
                tbl.add_row(key, f"{fio_metrics[key]:.1f}")
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
    ident: Optional[str],
    destdir: str,
    node: Optional[str],
    numcores: Optional[int],
    config: Optional[str],
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
    if not str(ident_dir).startswith(str(destdir_p)):
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
    node: Optional[str],
    threshold: float,
    config: Optional[str],
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
    else:
        console.print(f"\n[green bold]No regressions detected (threshold: {threshold}%)[/green bold]")
