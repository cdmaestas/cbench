"""Cbench nodehwtest CLI subcommands.

Subcommands:
  gen-jobs    -- write nodelist file for a test identifier
  start-jobs  -- submit per-node batch scripts or run via pdsh
  parse       -- parse node_hw_test output files and report outliers
"""

from __future__ import annotations

import math
import os
import re
import shlex
import statistics
import subprocess
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from cbench.config import load_config
from cbench.db import ParseResult as DBResult, ResultsDB
from cbench.hw_tests import REGISTRY, get_hw_test

console = Console()

CBENCH_MARK = "CBENCH MARK:"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _testset_path(cbenchtest: str) -> Path:
    return Path(cbenchtest) / "nodehwtest"


def _ident_path(cbenchtest: str, ident: str) -> Path:
    base = _testset_path(cbenchtest)
    resolved = (base / ident).resolve()
    if not str(resolved).startswith(str(base.resolve())):
        raise click.UsageError(
            f"Path traversal detected: ident '{ident}' escapes nodehwtest directory"
        )
    return resolved


def _parse_run_file(path: Path) -> tuple[dict[str, list[float]], dict[str, str], list[float]]:
    """Parse a single *.node_hw_test.run#### file.

    Returns:
        numeric  — {metric_key: [values]}
        strings  — {metric_key: value}
        elapsed  — [elapsed_minutes_per_module]
    """
    lines = path.read_text(errors="replace").splitlines()
    numeric: dict[str, list[float]] = {}
    strings: dict[str, str] = {}
    elapsed_times: list[float] = []

    in_header = True
    linegrab = False
    buf: list[str] = []
    current_module = ""
    last_module = ""
    last_elapsed = 0.0
    timestamp_count = 0

    for line in lines:
        if CBENCH_MARK in line:
            in_header = False

            if linegrab:
                # end of a section — dispatch to hw_test parser
                _dispatch(current_module, buf, numeric, strings)
                linegrab = False
                buf = []

            if "ITERATION" in line:
                pass  # iteration markers just delimit runs

            elif "MODULE" in line:
                m = re.search(r"MODULE\s+(\S+)", line)
                if m:
                    last_module = current_module
                    current_module = m.group(1)

            elif "TIMESTAMP" in line:
                m = re.search(r"elapsed=([\d.]+)\s+min", line)
                if m:
                    this_elapsed = float(m.group(1))
                    delta = this_elapsed - last_elapsed
                    last_elapsed = this_elapsed
                    timestamp_count += 1
                    if timestamp_count > 1:
                        elapsed_times.append(delta)
                        mod = last_module if last_module else current_module
                        key = f"{mod}_elapsed"
                        numeric.setdefault(key, []).append(delta)

        elif in_header:
            continue
        else:
            if not linegrab:
                linegrab = True
            buf.append(line)

    # flush last section
    if linegrab and buf:
        _dispatch(current_module, buf, numeric, strings)

    return numeric, strings, elapsed_times


def _dispatch(
    module: str,
    buf: list[str],
    numeric: dict[str, list[float]],
    strings: dict[str, str],
) -> None:
    """Call the hw_test parser for *module* and accumulate results."""
    if not module:
        return
    hw = get_hw_test(module)
    if hw is None:
        return
    try:
        data = hw.parse(buf)
    except Exception as exc:
        console.print(f"[yellow]Warning: hw_test parser '{module}' failed: {exc}[/yellow]")
        return
    for k, v in data.items():
        if isinstance(v, str):
            strings[k] = v
        else:
            try:
                numeric.setdefault(k, []).append(float(v))
            except (TypeError, ValueError):
                strings[k] = str(v)


def _load_targets(target_file: Path) -> dict[str, dict[str, float]]:
    """Read a target values file → {key: {mean, max, min, stddev}}."""
    targets: dict[str, dict[str, float]] = {}
    if not target_file.exists():
        return targets
    for line in target_file.read_text().splitlines():
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split(",")
        if len(parts) >= 5:
            key = parts[0].strip()
            try:
                targets[key] = {
                    "mean": float(parts[1]),
                    "max": float(parts[2]),
                    "min": float(parts[3]),
                    "stddev": float(parts[4]),
                }
            except (ValueError, IndexError):
                pass
    return targets


def _save_targets(
    target_file: Path,
    targets: dict[str, dict[str, float]],
    total_nodes: int,
    total_iterations: int,
) -> None:
    lines = [
        "# Cbench nodehwtest target value file",
        f"# Generated from {total_iterations} iterations across {total_nodes} nodes",
        "# Format: TESTNAME, MEAN, MAX, MIN, STDDEVIATION, SAMPLECOUNT",
    ]
    for k in sorted(targets):
        t = targets[k]
        lines.append(
            f"{k}, {t['mean']:.4f}, {t['max']:.4f}, {t['min']:.4f}, "
            f"{t['stddev']:.4f}, {int(t.get('count', 0))},"
        )
    target_file.write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------

@click.group("nodehwtest")
def nodehwtest_group() -> None:
    """Node hardware testing commands."""


# ---------------------------------------------------------------------------
# gen-jobs
# ---------------------------------------------------------------------------

@nodehwtest_group.command("gen-jobs")
@click.option("--nodelist", required=True, help="Pdsh-style node list, e.g. n[1-10]")
@click.option("--ident", default=None, help="Test identifier (default: <cluster>1)")
@click.option("--cbenchtest", default=None, envvar="CBENCHTEST")
@click.option("--config", default=None)
def gen_jobs(nodelist: str, ident: Optional[str], cbenchtest: Optional[str], config: Optional[str]) -> None:
    """Create a nodehwtest identifier directory and record the node list."""
    cfg = load_config(config)
    cbenchtest = cbenchtest or os.environ.get("CBENCHTEST", ".")
    if ident is None:
        ident = f"{cfg.cluster_name}1"

    ident_dir = _ident_path(cbenchtest, ident)
    ident_dir.mkdir(parents=True, exist_ok=True)

    nodelist_file = ident_dir / "nodelist"
    nodelist_file.write_text(f"nodelist={nodelist}\n")

    console.print(f"[green]Created nodehwtest identifier '{ident}' at {ident_dir}[/green]")
    console.print(f"  Node list: {nodelist}")


# ---------------------------------------------------------------------------
# start-jobs
# ---------------------------------------------------------------------------

@nodehwtest_group.command("start-jobs")
@click.option("--ident", default=None)
@click.option("--nodelist", default=None, help="Override node list from ident dir")
@click.option("--remote", is_flag=True, help="Run via pdsh remote execution")
@click.option("--batch", is_flag=True, help="Submit per-node batch jobs")
@click.option("--nodebatch", is_flag=True, help="Alias for --batch")
@click.option("--batchargs", default="", help="Extra arguments for batch submission")
@click.option("--match", default=None, help="Only run modules matching this regex")
@click.option("--exclude", default=None, help="Exclude modules matching this regex")
@click.option("--class", "test_class", default=None, help="Run only tests of this class")
@click.option("--preamble", default=None, help="Shell command to run before node_hw_test")
@click.option("--background", is_flag=True, help="Run remote execution in background")
@click.option("--ignore-nodes", default=None, help="Pdsh-style list of nodes to exclude")
@click.option("--cbenchtest", default=None, envvar="CBENCHTEST")
@click.option("--cbenchome", default=None, envvar="CBENCHOME")
@click.option("--config", default=None)
@click.option("--dry-run", is_flag=True)
def start_jobs(
    ident: Optional[str],
    nodelist: Optional[str],
    remote: bool,
    batch: bool,
    nodebatch: bool,
    batchargs: str,
    match: Optional[str],
    exclude: Optional[str],
    test_class: Optional[str],
    preamble: Optional[str],
    background: bool,
    ignore_nodes: Optional[str],
    cbenchtest: Optional[str],
    cbenchome: Optional[str],
    config: Optional[str],
    dry_run: bool,
) -> None:
    """Start nodehwtest jobs via batch scheduler or remote (pdsh) execution."""
    if not (remote or batch or nodebatch):
        raise click.UsageError("One of --remote, --batch, or --nodebatch is required.")

    cfg = load_config(config)
    cbenchtest = cbenchtest or os.environ.get("CBENCHTEST", ".")
    cbenchome = cbenchome or os.environ.get("CBENCHOME", ".")
    if ident is None:
        ident = f"{cfg.cluster_name}1"

    ident_dir = _ident_path(cbenchtest, ident)
    ident_dir.mkdir(parents=True, exist_ok=True)

    # resolve node list
    nodes: list[str] = []
    if nodelist:
        nodes = _expand_pdsh(nodelist)
    else:
        nodelist_file = ident_dir / "nodelist"
        if nodelist_file.exists():
            for line in nodelist_file.read_text().splitlines():
                m = re.match(r"nodelist=(.+)", line.strip())
                if m:
                    nodes = _expand_pdsh(m.group(1))
        if not nodes:
            raise click.UsageError(f"No node list found in {nodelist_file}. Use --nodelist.")

    # apply ignore list
    if ignore_nodes:
        ignore_set = set(_expand_pdsh(ignore_nodes))
        nodes = [n for n in nodes if n not in ignore_set]

    console.print(f"Starting nodehwtest jobs for identifier '{ident}' on {len(nodes)} nodes")

    node_hw_test_parts = [
        shlex.quote(f"{cbenchtest}/nodehwtest/node_hw_test"),
        "--ident", shlex.quote(ident),
    ]
    if match:
        node_hw_test_parts += ["--match", shlex.quote(match)]
    if exclude:
        node_hw_test_parts += ["--exclude", shlex.quote(exclude)]
    if test_class:
        node_hw_test_parts += ["--class", shlex.quote(test_class)]
    node_hw_test_cmd = " ".join(node_hw_test_parts)

    if preamble:
        # preamble is user-supplied shell code; quote the hw_test invocation
        # but leave preamble verbatim as it is intentional shell logic
        node_hw_test_cmd = f"{preamble} ; {node_hw_test_cmd}"

    submitted = 0

    if batch or nodebatch:
        # Generate and submit one batch script per node
        for node in sorted(nodes):
            jobname = f"nodehwtest-{node}"
            script = _build_batch_script(cfg, node, jobname, node_hw_test_cmd, ident, cbenchtest)
            script_path = ident_dir / f"nhwt-{node}.{cfg.batch_method}"
            if not dry_run:
                script_path.write_text(script)
                batch_exe = cfg.batch_cmd or _default_batch_cmd(cfg)
                cmd_parts = shlex.split(batch_exe)
                if batchargs:
                    cmd_parts += shlex.split(batchargs)
                cmd_parts.append(str(script_path))
                try:
                    subprocess.run(cmd_parts, shell=False, check=False)
                except Exception as e:
                    console.print(f"[yellow]Warning: could not submit {node}: {e}[/yellow]")
            else:
                console.print(f"  [dim]Would submit: {script_path}[/dim]")
            submitted += 1

        action = "Would submit" if dry_run else "Submitted"
        console.print(f"[green]{action} {submitted} nodehwtest batch jobs[/green]")

    elif remote:
        # Run via pdsh — each node name is shell-quoted; env vars are quoted too
        node_str = ",".join(shlex.quote(n) for n in sorted(nodes))
        env_prefix = (
            f"export CBENCHOME={shlex.quote(cbenchome)}; "
            f"export CBENCHTEST={shlex.quote(cbenchtest)};"
        )
        remote_cmd = shlex.quote(f"{env_prefix} {node_hw_test_cmd}")
        cmd = f"pdsh -w {node_str} {remote_cmd}"
        if dry_run:
            console.print(f"[dim]Would run: {cmd}[/dim]")
        else:
            if background:
                subprocess.Popen(cmd, shell=True)
                console.print(f"[green]Backgrounded remote execution on {len(nodes)} nodes[/green]")
            else:
                subprocess.run(cmd, shell=True)


def _expand_pdsh(spec: str) -> list[str]:
    """Minimally expand a pdsh-style node list like n[1-3,5] → [n1,n2,n3,n5]."""
    nodes: list[str] = []
    m = re.match(r"^([^\[]+)\[([^\]]+)\](.*)$", spec)
    if not m:
        # plain comma-separated list or single node
        return [n.strip() for n in spec.split(",") if n.strip()]
    prefix = m.group(1)
    ranges = m.group(2)
    suffix = m.group(3)
    for part in ranges.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-", 1)
            width = len(lo) if lo.startswith("0") else 0
            for i in range(int(lo), int(hi) + 1):
                nodes.append(f"{prefix}{str(i).zfill(width) if width else i}{suffix}")
        else:
            nodes.append(f"{prefix}{part}{suffix}")
    return nodes


def _default_batch_cmd(cfg) -> str:
    return {"slurm": "sbatch", "torque": "qsub", "lsf": "bsub"}.get(cfg.batch_method, "sbatch")


def _build_batch_script(cfg, node: str, jobname: str, nodecmd: str, ident: str, cbenchtest: str) -> str:
    method = cfg.batch_method
    lines = ["#!/bin/bash"]
    if method == "slurm":
        lines += [
            f"#SBATCH --job-name={jobname}",
            f"#SBATCH -w {node}",
            f"#SBATCH --nodes=1",
            f"#SBATCH --time={cfg.default_walltime}",
        ]
    elif method in ("torque", "pbspro"):
        lines += [
            f"#PBS -N {jobname}",
            f"#PBS -l nodes={node}:ppn={cfg.procs_per_node}",
            f"#PBS -l walltime={cfg.default_walltime}",
        ]
    elif method == "lsf":
        lines += [
            f"#BSUB -J {jobname}",
            f"#BSUB -m {node}",
            f"#BSUB -W {cfg.default_walltime}",
        ]
    lines += [
        "",
        f"export CBENCHTEST={shlex.quote(cbenchtest)}",
        f"export CBENCHOME={shlex.quote(cbenchtest)}",
        "",
        nodecmd,
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# parse
# ---------------------------------------------------------------------------

@nodehwtest_group.command("parse")
@click.option("--ident", default=None)
@click.option("--characterize", is_flag=True, help="Compute statistical targets from parsed data")
@click.option("--save-targets", default=None, metavar="FILE", help="Save characterized targets to file")
@click.option("--load-targets", default=None, metavar="FILE", help="Load target values from file")
@click.option("--lastnruns", default=1, show_default=True, help="Parse the last N runs per node")
@click.option("--only-run", default=None, type=int, help="Parse only run number N")
@click.option("--match", default=None, help="Only parse nodes matching this regex")
@click.option("--class", "test_class", default=None, help="Only analyze tests of this class")
@click.option("--no-errors", is_flag=True, help="Skip outlier reporting")
@click.option("--iteration-analyze", is_flag=True, help="Report per-node iteration counts")
@click.option("--output", default="table", type=click.Choice(["table", "json"]))
@click.option("--store", is_flag=True, help="Store parsed results to cbench_results.db")
@click.option("--cbenchtest", default=None, envvar="CBENCHTEST")
@click.option("--config", default=None)
def parse_cmd(
    ident: Optional[str],
    characterize: bool,
    save_targets: Optional[str],
    load_targets: Optional[str],
    lastnruns: int,
    only_run: Optional[int],
    match: Optional[str],
    test_class: Optional[str],
    no_errors: bool,
    iteration_analyze: bool,
    output: str,
    store: bool,
    cbenchtest: Optional[str],
    config: Optional[str],
) -> None:
    """Parse nodehwtest output files and report statistical outliers."""
    cfg = load_config(config)
    cbenchtest = cbenchtest or os.environ.get("CBENCHTEST", ".")
    if ident is None:
        ident = f"{cfg.cluster_name}1"

    ident_dir = _ident_path(cbenchtest, ident)
    if not ident_dir.exists():
        console.print(f"[red]Identifier directory not found: {ident_dir}[/red]")
        raise SystemExit(1)

    console.print(f"[green]Cbench nodehwtest output parser[/green]")
    console.print(f"  Parsing identifier: {ident}")
    if characterize:
        console.print("  Running CHARACTERIZE mode")

    # -- collect all run files --
    # file naming: <node>.node_hw_test.run<NNNN>
    run_file_re = re.compile(r"^(.+)\.node_hw_test\.run(\d+)$")

    # node → {run_id: Path}
    node_runs: dict[str, dict[int, Path]] = {}
    for f in ident_dir.iterdir():
        m = run_file_re.match(f.name)
        if not m:
            continue
        node = m.group(1)
        run_id = int(m.group(2))
        if match and not re.search(match, node):
            continue
        node_runs.setdefault(node, {})[run_id] = f

    # -- parse selected run files --
    # nodehash: node → {metric: [values]}
    nodehash: dict[str, dict[str, list]] = {}
    node_iterations: dict[str, int] = {}
    total_files = 0
    total_iterations = 0

    for node in sorted(node_runs):
        runs = node_runs[node]
        if not runs:
            continue
        max_run = max(runs.keys())

        if only_run is not None:
            run_ids = [only_run] if only_run in runs else []
        else:
            run_ids = sorted(runs.keys(), reverse=True)[:lastnruns]

        for run_id in run_ids:
            f = runs[run_id]
            numeric, _strings, _elapsed = _parse_run_file(f)

            # filter by test_class if requested
            if test_class:
                hw_name_map = {hw_cls().name: hw_cls().test_class for hw_cls in REGISTRY.values()}
                numeric = {
                    k: v
                    for k, v in numeric.items()
                    if any(
                        k.startswith(mod) and hw_name_map.get(mod, "") == test_class
                        for mod in hw_name_map
                    )
                }

            if node not in nodehash:
                nodehash[node] = {}

            for k, vals in numeric.items():
                nodehash[node].setdefault(k, []).extend(vals)

            total_files += 1
            total_iterations += 1

        node_iterations[node] = len(run_ids)

    # -- characterize OR load targets --
    targets: dict[str, dict[str, float]] = {}

    if characterize:
        # aggregate across all nodes
        all_vals: dict[str, list[float]] = {}
        for node, metrics in nodehash.items():
            for k, vals in metrics.items():
                all_vals.setdefault(k, []).extend(vals)

        for k, vals in all_vals.items():
            if len(vals) < 2:
                continue
            mean = statistics.mean(vals)
            stddev = statistics.pstdev(vals)
            targets[k] = {
                "mean": mean,
                "max": max(vals),
                "min": min(vals),
                "stddev": stddev,
                "count": len(vals),
            }

        # print characterized targets
        console.print("\n[green]CHARACTERIZED TARGET VALUES:[/green]")
        for k in sorted(targets):
            t = targets[k]
            console.print(
                f"  [magenta]{k}[/magenta]: "
                f"mean=[cyan]{t['mean']:.4f}[/cyan] "
                f"max=[cyan]{t['max']:.4f}[/cyan] "
                f"min=[cyan]{t['min']:.4f}[/cyan] "
                f"stddev=[cyan]{t['stddev']:.4f}[/cyan] "
                f"(n={int(t['count'])})"
            )

        if save_targets:
            tfile = (ident_dir / save_targets).resolve()
            if not str(tfile).startswith(str(ident_dir.resolve())):
                raise click.UsageError(f"--save-targets path escapes the ident directory: {tfile}")
            _save_targets(tfile, targets, len(nodehash), total_iterations)
            console.print(f"[cyan]Saved target values to {tfile}[/cyan]")
    else:
        tfile_name = load_targets or "target_hw_values"
        tfile = (ident_dir / tfile_name).resolve()
        if not str(tfile).startswith(str(ident_dir.resolve())):
            raise click.UsageError(f"--load-targets path escapes the ident directory: {tfile}")
        targets = _load_targets(tfile)
        if targets:
            console.print(f"[cyan]Loaded target values from {tfile}[/cyan]")
        else:
            console.print(
                "[yellow]No target values found — run with --characterize first.[/yellow]"
            )
            characterize = True  # switch to characterize mode silently

    # -- flag outliers --
    if not no_errors and targets:
        console.print("\n[bold red]Nodes with tests exceeding two standard deviations (95%):[/bold red]")
        outliers: list[tuple[str, str, float, float, float, float, float, int]] = []

        for node in sorted(nodehash):
            for k, vals in sorted(nodehash[node].items()):
                if not vals or k not in targets:
                    continue
                val = statistics.mean(vals)
                t = targets[k]
                delta = abs(val - t["mean"])
                if delta == 0:
                    continue
                if t["stddev"] == 0:
                    continue
                if delta >= 2 * t["stddev"]:
                    sign = "+" if val > t["mean"] else "-"
                    pct = (delta / t["stddev"]) * 100
                    outliers.append((node, k, val, t["mean"], delta, pct, t["stddev"], len(vals)))

        if output == "table":
            if outliers:
                tbl = Table(show_header=True)
                tbl.add_column("Node")
                tbl.add_column("Test")
                tbl.add_column("Actual", justify="right")
                tbl.add_column("Expected", justify="right")
                tbl.add_column("Delta%", justify="right")
                tbl.add_column("StdDev", justify="right")
                for node, k, actual, good, delta, pct, stddev, n in outliers:
                    tbl.add_row(
                        node, k,
                        f"{actual:.4f}", f"{good:.4f}",
                        f"{pct:.1f}%", f"{stddev:.4f}",
                    )
                console.print(tbl)
            else:
                console.print("[green]No outliers detected.[/green]")
        else:
            import json
            rows = [
                {"node": n, "test": k, "actual": a, "expected": g,
                 "delta_pct": p, "stddev": s, "samples": cnt}
                for n, k, a, g, d, p, s, cnt in outliers
            ]
            console.print(json.dumps(rows, indent=2))

    # -- iteration analysis --
    if iteration_analyze and node_iterations:
        vals = list(node_iterations.values())
        if len(vals) >= 2:
            mean = statistics.mean(vals)
            console.print(f"\n[green]Iteration analysis:[/green]")
            console.print(f"  Mean: {mean:.2f}  Min: {min(vals)}  Max: {max(vals)}")

    # -- store to DB --
    if store and nodehash:
        db_path = Path(cbenchtest) / "cbench_results.db"
        db = ResultsDB(db_path)
        stored_count = 0
        for node, metrics in nodehash.items():
            flat: dict[str, float] = {
                k: statistics.mean(vals) for k, vals in metrics.items() if vals
            }
            if not flat:
                continue
            result = DBResult(
                cluster=cfg.cluster_name,
                testset="nodehwtest",
                ident=ident,
                jobname=node,
                benchmark="nodehwtest",
                numprocs=1,
                ppn=1,
                numnodes=1,
                status="PASSED",
                metrics=flat,
            )
            db.store(result)
            stored_count += 1
        console.print(f"[green]Stored {stored_count} node(s) to {db_path}[/green]")

    # summary
    console.print(
        f"\n[green]Summary:[/green] parsed {total_files} files "
        f"for {len(nodehash)} nodes"
    )
