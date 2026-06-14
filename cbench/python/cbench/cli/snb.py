"""cbench snb — single-node benchmark run and report (port of single_node_benchmark.pl).

Usage:
  cbench snb run  [--ident ID] [--destdir DIR] [--tests REGEX] [--numcores N]
  cbench snb report [--ident ID] [--destdir DIR] [--node HOSTNAME]
"""

from __future__ import annotations

import os
import re
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
    cmd: str,
    outfile: Path,
    *,
    overwrite: bool = False,
    dry_run: bool = False,
    log_fh=None,
) -> None:
    """Run shell command, redirect stdout+stderr to outfile (append or overwrite)."""
    arrow = ">" if overwrite else ">>"
    msg = f"RUNCMD: {cmd} {arrow} {outfile}"
    if log_fh:
        _logmsg(log_fh, msg)
    if dry_run:
        return
    mode = "w" if overwrite else "a"
    with open(outfile, mode) as fh:
        subprocess.run(cmd, shell=True, stdout=fh, stderr=subprocess.STDOUT)


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
              default="stream|cachebench|dgemm|mpistreams|linpack|npb",
              show_default=True,
              help="Pipe-separated regex of tests to run")
@click.option("--binpath", default=None, envvar="CBENCH_BINPATH",
              help="Path to benchmark binary directory (default: $CBENCHOME/bin/hwtests)")
@click.option("--mpi-cmd", default="mpirun", show_default=True,
              help="MPI launch command for mpistreams")
@click.option("--dry-run", is_flag=True, help="Print commands without executing")
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
    config: Optional[str],
) -> None:
    """Run the single-node benchmark suite and save output files."""
    from cbench.config import load_config
    from cbench.utils import is_power_of_two

    cfg = load_config(config)
    hostname = node or _hostname()
    numcores = numcores or _detect_cores()
    ident = ident or f"{cfg.cluster_name}1"

    destdir_p = Path(destdir)
    ident_dir = destdir_p / ident
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
                    run(str(b), "streams")
            else:
                _logmsg(log, f"WARNING: no stream-* binaries found in {binpath_p}")

        # ------------------------------------------------------------------
        # cachebench
        # ------------------------------------------------------------------
        if re.search(r"cachebench", tests):
            _logmsg(log, "Starting CACHEBENCH testing")
            cb = binpath_p / "cachebench"
            if cb.exists():
                run(f"{cb} --lmbench", "cachebench", overwrite=True)
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
                        _logmsg(log, f"DRYRUN: echo '{marker}'; {mpi_cmd} -n {np} {stream_mpi}")
                    else:
                        with open(out("mpistreams"), "a") as fh:
                            fh.write(f"{marker}\n")
                            subprocess.run(
                                f"{mpi_cmd} -n {np} {stream_mpi}",
                                shell=True, stdout=fh, stderr=subprocess.STDOUT,
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
                    gen_cmd = (
                        f"cbench gen-jobs --testset linpack --ident {sub_ident} "
                        f"--maxprocs {procs} --ppn {procs} --cbenchtest {cbenchtest}"
                    )
                    start_cmd = (
                        f"cbench start-jobs --testset linpack --ident {sub_ident} "
                        f"--interactive --match {procs}ppn --cbenchtest {cbenchtest}"
                    )
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
                f"cbench gen-jobs --testset npb --ident {identbase} "
                f"--maxprocs {numcores} --cbenchtest {cbenchtest}",
                "npb",
            )
            run(
                f"cbench start-jobs --testset npb --ident {identbase} "
                f"--interactive --maxprocs {numcores} --cbenchtest {cbenchtest}",
                "npb",
            )

        _logmsg(
            log,
            f"Finished running the Single Node Benchmarks. "
            f"Run `cbench snb report --ident {ident} --destdir {destdir}` to view results.",
        )


# ---------------------------------------------------------------------------
# snb report
# ---------------------------------------------------------------------------

@snb_group.command("report")
@click.option("--ident", default=None, help="Test identifier")
@click.option("--destdir", default=".", show_default=True, type=click.Path())
@click.option("--node", default=None, help="Hostname of benchmarked node (default: current host)")
@click.option("--config", default=None)
def report_cmd(
    ident: Optional[str],
    destdir: str,
    node: Optional[str],
    config: Optional[str],
) -> None:
    """Parse snb output files and display a summary report."""
    from cbench.config import load_config

    cfg = load_config(config)
    hostname = node or _hostname()
    ident = ident or f"{cfg.cluster_name}1"
    destdir_p = Path(destdir)
    ident_dir = destdir_p / ident

    if not ident_dir.exists():
        console.print(f"[red]Directory not found: {ident_dir}[/red]")
        raise SystemExit(1)

    def out(tag: str) -> Path:
        return ident_dir / f"{hostname}.snb.{tag}.out"

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

    if not any_results:
        console.print(
            "[yellow]No parsed results found. "
            f"Run `cbench snb run --ident {ident} --destdir {destdir}` first.[/yellow]"
        )
