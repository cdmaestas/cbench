"""Cbench Python CLI — entry point for all subcommands."""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from cbench.config import ClusterConfig, load_config
from cbench import launchers, schedulers, templates
from cbench.db import ParseResult, ResultsDB
from cbench.parsers import REGISTRY, get_parser
from cbench.parse_filters import build_filter_set, apply_filters, AVAILABLE as FILTER_MODULES
from cbench.cli.nodehwtest import nodehwtest_group
from cbench.cli.utils_cmd import utils_group
from cbench.cli.diag import diag_cmd
from cbench.cli.snb import snb_group

console = Console()


def _db_path(cbenchtest: str) -> Path:
    return Path(cbenchtest) / "cbench_results.db"


def _cfg(config: Optional[str]) -> ClusterConfig:
    return load_config(config)


# ---------------------------------------------------------------------------
# CLI root
# ---------------------------------------------------------------------------

@click.group()
@click.version_option(package_name="cbench")
def cli() -> None:
    """Cbench HPC benchmarking framework — Python toolchain."""


cli.add_command(nodehwtest_group)
cli.add_command(utils_group)
cli.add_command(diag_cmd)
cli.add_command(snb_group)


# ---------------------------------------------------------------------------
# gen-jobs
# ---------------------------------------------------------------------------

@cli.command("gen-jobs")
@click.option("--testset", required=True, help="Testset name (e.g. bandwidth, linpack)")
@click.option("--ident", required=True, help="Run identifier (e.g. mycluster-run1)")
@click.option("--ppn", default=None, help="Comma-separated PPN values to generate (default: all from config)")
@click.option("--maxprocs", default=None, type=int, help="Limit max number of processes")
@click.option("--run-type", default="both", type=click.Choice(["batch", "interactive", "both"]))
@click.option("--dry-run", is_flag=True, help="Print generated scripts without writing")
@click.option("--config", default=None, help="Path to cluster.yaml")
@click.option("--cbenchtest", default=None, envvar="CBENCHTEST", help="CBENCHTEST directory")
def gen_jobs(
    testset: str,
    ident: str,
    ppn: Optional[str],
    maxprocs: Optional[int],
    run_type: str,
    dry_run: bool,
    config: Optional[str],
    cbenchtest: Optional[str],
) -> None:
    """Generate batch and/or interactive job scripts for a testset."""
    cfg = _cfg(config)
    cbenchtest = cbenchtest or os.environ.get("CBENCHTEST", ".")
    templates_dir = templates._templates_dir()

    # Determine which PPN values to use
    ppn_values = [int(p) for p in ppn.split(",")] if ppn else cfg.ppn_levels

    # Determine which benchmarks have templates
    benchmark_templates: list[str] = []
    for tfile in sorted(templates_dir.glob(f"{testset}_*.in")):
        bench = tfile.stem[len(testset) + 1:]
        benchmark_templates.append(bench)

    if not benchmark_templates:
        console.print(f"[red]No templates found for testset '{testset}' in {templates_dir}[/red]")
        raise SystemExit(1)

    run_types = ["batch", "interactive"] if run_type == "both" else [run_type]
    total = 0

    for ppn_val in ppn_values:
        max_procs_for_ppn = cfg.max_ppn_procs.get(str(ppn_val), ppn_val * cfg.max_nodes)
        valid_sizes = [n for n in templates.RUN_SIZES if n <= max_procs_for_ppn]
        if maxprocs:
            valid_sizes = [n for n in valid_sizes if n <= maxprocs]

        for numprocs in valid_sizes:
            numnodes = max(1, math.ceil(numprocs / ppn_val))
            walltime = templates.compute_walltime(numprocs, valid_sizes, cfg)
            launch_cmd = launchers.build_launch_cmd(numprocs, ppn_val, numnodes, cfg)

            for bench in benchmark_templates:
                jobname = f"{bench}-{ppn_val}ppn-{numprocs}"
                for rtype in run_types:
                    try:
                        raw = templates.build_job_template(testset, bench, rtype, cfg)
                    except FileNotFoundError as exc:
                        console.print(f"[yellow]Skipping {jobname}/{rtype}: {exc}[/yellow]")
                        continue

                    script = templates.substitute(
                        raw,
                        numprocs=numprocs,
                        ppn=ppn_val,
                        numnodes=numnodes,
                        walltime=walltime,
                        jobname=jobname,
                        benchmark=bench,
                        testset=testset,
                        ident=ident,
                        run_type=rtype,
                        launch_cmd=launch_cmd,
                        cfg=cfg,
                        cbenchtest=cbenchtest,
                    )

                    ext = schedulers.extension(cfg) if rtype == "batch" else ".sh"
                    script_name = f"{jobname}{ext}"
                    job_dir = Path(cbenchtest) / testset / ident / jobname

                    if dry_run:
                        console.rule(f"{job_dir}/{script_name}")
                        console.print(script)
                    else:
                        job_dir.mkdir(parents=True, exist_ok=True)
                        (job_dir / script_name).write_text(script)
                        (job_dir / script_name).chmod(0o755)

                    total += 1

    action = "Would generate" if dry_run else "Generated"
    console.print(f"[green]{action} {total} job script(s) for testset '{testset}', ident '{ident}'[/green]")


# ---------------------------------------------------------------------------
# start-jobs
# ---------------------------------------------------------------------------

@cli.command("start-jobs")
@click.option("--testset", required=True)
@click.option("--ident", required=True)
@click.option("--batch", "mode", flag_value="batch", default=True)
@click.option("--interactive", "mode", flag_value="interactive")
@click.option("--throttledbatch", "throttle", default=None, type=int,
              help="Keep N jobs running+queued at a time")
@click.option("--match", default=None, help="Regex to filter job names")
@click.option("--exclude", default=None, help="Regex to exclude job names")
@click.option("--minprocs", default=None, type=int)
@click.option("--maxprocs", default=None, type=int)
@click.option("--delay", default=0.5, type=float, help="Seconds between submissions")
@click.option("--poll-interval", default=120, type=int,
              help="Seconds between scheduler polls in throttled mode")
@click.option("--dry-run", is_flag=True)
@click.option("--config", default=None)
@click.option("--cbenchtest", default=None, envvar="CBENCHTEST")
def start_jobs(
    testset: str,
    ident: str,
    mode: str,
    throttle: Optional[int],
    match: Optional[str],
    exclude: Optional[str],
    minprocs: Optional[int],
    maxprocs: Optional[int],
    delay: float,
    poll_interval: int,
    dry_run: bool,
    config: Optional[str],
    cbenchtest: Optional[str],
) -> None:
    """Submit jobs from a generated testset/ident directory."""
    cfg = _cfg(config)
    cbenchtest = cbenchtest or os.environ.get("CBENCHTEST", ".")
    ident_dir = Path(cbenchtest) / testset / ident

    if not ident_dir.exists():
        console.print(f"[red]Directory not found: {ident_dir}[/red]")
        raise SystemExit(1)

    ext = schedulers.extension(cfg)
    # Discover job scripts matching *-*ppn-* pattern
    scripts: list[Path] = sorted(ident_dir.glob(f"**/*-*ppn-*{ext}"))

    # Apply filters
    def _keep(path: Path) -> bool:
        name = path.stem
        if match and not re.search(match, name):
            return False
        if exclude and re.search(exclude, name):
            return False
        # Extract numprocs from name like benchmark-Xppn-N
        m = re.search(r"-(\d+)$", name)
        if m:
            np = int(m.group(1))
            if minprocs and np < minprocs:
                return False
            if maxprocs and np > maxprocs:
                return False
        return True

    scripts = [s for s in scripts if _keep(s)]

    if not scripts:
        console.print("[yellow]No matching job scripts found.[/yellow]")
        return

    submitted = 0
    if throttle:
        # Throttled batch: keep ≤ throttle jobs running+queued
        remaining = list(scripts)
        while remaining:
            status = schedulers.query(ident, cfg)
            running_count = status.get("TOTAL", 0)
            slots = throttle - running_count
            for _ in range(max(0, slots)):
                if not remaining:
                    break
                script = remaining.pop(0)
                cmd = schedulers.submit_cmd(str(script), cfg)
                if dry_run:
                    console.print(f"[dim]Would submit:[/dim] {cmd}")
                else:
                    subprocess.run(cmd, shell=True, check=False)
                submitted += 1
                if delay:
                    time.sleep(delay)
            if remaining:
                time.sleep(poll_interval)
    else:
        for script in scripts:
            cmd = schedulers.submit_cmd(str(script), cfg)
            if mode == "interactive":
                cmd = f"bash {script}"
            if dry_run:
                console.print(f"[dim]Would submit:[/dim] {cmd}")
            else:
                subprocess.run(cmd, shell=True, check=False)
            submitted += 1
            if delay:
                time.sleep(delay)

    action = "Would submit" if dry_run else "Submitted"
    console.print(f"[green]{action} {submitted} job(s)[/green]")


# ---------------------------------------------------------------------------
# parse
# ---------------------------------------------------------------------------

@cli.command("parse")
@click.option("--testset", required=True)
@click.option("--ident", required=True)
@click.option("--output", default="table", type=click.Choice(["table", "json"]))
@click.option("--config", default=None)
@click.option("--cbenchtest", default=None, envvar="CBENCHTEST")
@click.option("--no-db", is_flag=True, help="Skip writing to SQLite")
@click.option(
    "--customparse",
    default=None,
    help="Comma-separated parse filter modules to apply (e.g. openmpi,slurm,misc).",
)
def parse_cmd(
    testset: str,
    ident: str,
    output: str,
    config: Optional[str],
    cbenchtest: Optional[str],
    no_db: bool,
    customparse: Optional[str],
) -> None:
    """Parse benchmark output files and store results."""
    cfg = _cfg(config)
    cbenchtest = cbenchtest or os.environ.get("CBENCHTEST", ".")
    ident_dir = Path(cbenchtest) / testset / ident

    # Build parse filter set from --customparse or cluster config
    filter_names: list[str] = []
    if customparse:
        filter_names = [n.strip() for n in customparse.split(",") if n.strip()]
    elif cfg.parse_filter_include:
        filter_names = [n for n in cfg.parse_filter_include if n in FILTER_MODULES]
    active_filters = build_filter_set(filter_names) if filter_names else {}

    if not ident_dir.exists():
        console.print(f"[red]Directory not found: {ident_dir}[/red]")
        raise SystemExit(1)

    db: Optional[ResultsDB] = None
    if not no_db:
        db = ResultsDB(_db_path(cbenchtest))

    results: list[dict] = []

    # Walk job directories
    for job_dir in sorted(ident_dir.iterdir()):
        if not job_dir.is_dir():
            continue
        jobname = job_dir.name

        # Determine benchmark from jobname (benchmark-Xppn-N)
        parts = jobname.rsplit("-", 2)
        if len(parts) < 3:
            continue
        benchmark = parts[0]
        ppn_str = parts[1].replace("ppn", "")
        numprocs_str = parts[2]

        try:
            ppn_val = int(ppn_str)
            numprocs = int(numprocs_str)
        except ValueError:
            continue

        numnodes = max(1, math.ceil(numprocs / ppn_val))

        # Find stdout file
        stdout_files = list(job_dir.glob("*.o*")) + list(job_dir.glob("slurm-*.out"))
        if not stdout_files:
            continue
        stdout = stdout_files[0].read_text(errors="replace")
        stderr_files = list(job_dir.glob("*.e*"))
        stderr = stderr_files[0].read_text(errors="replace") if stderr_files else ""

        # Run parse filters on combined output first
        filter_errors: list[str] = []
        if active_filters:
            filter_errors = apply_filters(active_filters, stdout + "\n" + stderr)

        parser = get_parser(benchmark)
        if parser is None:
            status_detail = "; ".join(filter_errors) if filter_errors else None
            result = ParseResult(
                cluster=cfg.cluster_name, testset=testset, ident=ident,
                jobname=jobname, benchmark=benchmark,
                numprocs=numprocs, ppn=ppn_val, numnodes=numnodes,
                status="NO_PARSER" if not filter_errors else "FILTER_ERROR",
                status_detail=status_detail,
            )
        else:
            parsed = parser.parse(stdout, stderr)
            # Filter errors override a PASSED result
            if filter_errors and parsed.status == "PASSED":
                status = "FILTER_ERROR"
                status_detail = "; ".join(filter_errors)
            else:
                status = parsed.status
                status_detail = parsed.status_detail
            result = ParseResult(
                cluster=cfg.cluster_name, testset=testset, ident=ident,
                jobname=jobname, benchmark=benchmark,
                numprocs=numprocs, ppn=ppn_val, numnodes=numnodes,
                status=status,
                status_detail=status_detail,
                metrics=parsed.metrics,
                metric_units=parser.metric_units(),
            )

        if db:
            db.store(result)

        results.append({
            "jobname": jobname,
            "benchmark": benchmark,
            "numprocs": numprocs,
            "ppn": ppn_val,
            "status": result.status,
            "metrics": result.metrics,
        })

    if output == "json":
        json_path = ident_dir / "results.json"
        json_path.write_text(json.dumps(results, indent=2))
        console.print(f"[green]Results written to {json_path}[/green]")
    else:
        _render_table(results, testset, ident)

    summary = _summarize(results)
    console.print(
        f"\n[bold]Summary:[/bold] "
        f"[green]{summary.get('PASSED', 0)} PASSED[/green]  "
        f"[red]{summary.get('ERROR', 0)} ERROR[/red]  "
        f"[yellow]{summary.get('OTHER', 0)} OTHER[/yellow]"
    )


def _render_table(results: list[dict], testset: str, ident: str) -> None:
    t = Table(title=f"{testset} / {ident}", show_lines=False)
    t.add_column("Job", style="cyan")
    t.add_column("NP", justify="right")
    t.add_column("PPN", justify="right")
    t.add_column("Status")
    t.add_column("Metrics")

    for r in results:
        status_style = "green" if r["status"] == "PASSED" else "red"
        metrics_str = "  ".join(
            f"{k}={v:.3g}" for k, v in r.get("metrics", {}).items()
        )
        t.add_row(
            r["jobname"],
            str(r["numprocs"]),
            str(r["ppn"]),
            f"[{status_style}]{r['status']}[/{status_style}]",
            metrics_str,
        )
    console.print(t)


def _summarize(results: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in results:
        key = "PASSED" if r["status"] == "PASSED" else ("ERROR" if "ERROR" in r["status"] else "OTHER")
        counts[key] = counts.get(key, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# rm-failed
# ---------------------------------------------------------------------------

@cli.command("rm-failed")
@click.option("--testset", required=True)
@click.option("--ident", required=True)
@click.option("--force", is_flag=True,
              help="Actually delete directories (default: dry-run preview)")
@click.option("--match", default=None, help="Regex to restrict job names considered")
@click.option("--status", "target_status", default="ERROR",
              help="Status pattern to match for removal (default: ERROR)")
@click.option("--config", default=None)
@click.option("--cbenchtest", default=None, envvar="CBENCHTEST")
def rm_failed(
    testset: str,
    ident: str,
    force: bool,
    match: Optional[str],
    target_status: str,
    config: Optional[str],
    cbenchtest: Optional[str],
) -> None:
    """Remove job directories whose parse status matches --status (default: ERROR).

    By default runs in preview mode — pass --force to actually delete.
    """
    cfg = _cfg(config)
    cbenchtest = cbenchtest or os.environ.get("CBENCHTEST", ".")
    ident_dir = Path(cbenchtest) / testset / ident

    if not ident_dir.exists():
        console.print(f"[red]Directory not found: {ident_dir}[/red]")
        raise SystemExit(1)

    to_remove: list[Path] = []

    for job_dir in sorted(ident_dir.iterdir()):
        if not job_dir.is_dir():
            continue
        jobname = job_dir.name
        if match and not re.search(match, jobname):
            continue

        parts = jobname.rsplit("-", 2)
        if len(parts) < 3:
            continue
        benchmark = parts[0]

        stdout_files = list(job_dir.glob("*.o*")) + list(job_dir.glob("slurm-*.out"))
        if not stdout_files:
            # No output file — treat as not-started, not an error
            continue
        stdout = stdout_files[0].read_text(errors="replace")
        stderr_files = list(job_dir.glob("*.e*"))
        stderr = stderr_files[0].read_text(errors="replace") if stderr_files else ""

        parser = get_parser(benchmark)
        if parser is None:
            continue
        parsed = parser.parse(stdout, stderr)

        if re.search(target_status, parsed.status):
            to_remove.append(job_dir)

    if not to_remove:
        console.print(f"[green]No jobs matching status '{target_status}' found.[/green]")
        return

    action = "Removing" if force else "Would remove"
    for path in to_remove:
        console.print(f"{action}: [cyan]{path}[/cyan]")
        if force:
            import shutil
            shutil.rmtree(path)

    if not force:
        console.print(
            f"\n[yellow]{len(to_remove)} director{'y' if len(to_remove)==1 else 'ies'} "
            f"would be removed. Pass [bold]--force[/bold] to delete.[/yellow]"
        )
    else:
        console.print(f"\n[green]Removed {len(to_remove)} director"
                      f"{'y' if len(to_remove)==1 else 'ies'}.[/green]")


# ---------------------------------------------------------------------------
# query
# ---------------------------------------------------------------------------

@cli.command("query")
@click.option("--benchmark", default=None)
@click.option("--cluster", default=None)
@click.option("--testset", default=None)
@click.option("--ident", default=None)
@click.option("--status", default=None)
@click.option("--since", default=None, help="ISO date string, e.g. 2025-01-01")
@click.option("--limit", default=100, type=int)
@click.option("--output", default="table", type=click.Choice(["table", "json"]))
@click.option("--cbenchtest", default=None, envvar="CBENCHTEST")
def query_cmd(
    benchmark: Optional[str],
    cluster: Optional[str],
    testset: Optional[str],
    ident: Optional[str],
    status: Optional[str],
    since: Optional[str],
    limit: int,
    output: str,
    cbenchtest: Optional[str],
) -> None:
    """Query stored benchmark results from the SQLite database."""
    cbenchtest = cbenchtest or os.environ.get("CBENCHTEST", ".")
    db_path = _db_path(cbenchtest)
    if not db_path.exists():
        console.print(f"[red]No results database found at {db_path}[/red]")
        raise SystemExit(1)

    db = ResultsDB(db_path)
    rows = db.query(
        benchmark=benchmark,
        cluster=cluster,
        testset=testset,
        ident=ident,
        status=status,
        since=since,
        limit=limit,
    )

    if output == "json":
        click.echo(json.dumps(rows, indent=2))
        return

    t = Table(title="Cbench Results", show_lines=False)
    t.add_column("ID", justify="right", style="dim")
    t.add_column("Cluster", style="cyan")
    t.add_column("Testset")
    t.add_column("Job")
    t.add_column("NP", justify="right")
    t.add_column("Status")
    t.add_column("Metrics")
    t.add_column("Parsed at", style="dim")

    for row in rows:
        status_val = row["status"]
        style = "green" if status_val == "PASSED" else "red"
        metrics_str = "  ".join(
            f"{k}={v['value']:.3g}{v['units']}" for k, v in row.get("metrics", {}).items()
        )
        t.add_row(
            str(row["id"]),
            row["cluster"],
            row["testset"],
            row["jobname"],
            str(row["numprocs"]),
            f"[{style}]{status_val}[/{style}]",
            metrics_str,
            (row["parsed_at"] or "")[:19],
        )

    console.print(t)
    console.print(f"[dim]{len(rows)} result(s)[/dim]")
