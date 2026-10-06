"""Cbench Python CLI — entry point for all subcommands."""

from __future__ import annotations

import json
import math
import os
import re
import shlex
import subprocess
import time
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from cbench.config import ClusterConfig, load_config
from cbench import hostlist, launchers, nodecompare, schedulers, templates
from cbench.db import ParseResult, ResultsDB
from cbench.parsers import get_parser
from cbench.parse_filters import build_filter_set, apply_filters, AVAILABLE as FILTER_MODULES
from cbench.cli.nodecheck import nodecheck_cmd
from cbench.cli.nodehwtest import nodehwtest_group
from cbench.cli.utils_cmd import utils_group
from cbench.cli.diag import diag_cmd
from cbench.cli.snb import snb_group
from cbench.cli.build import build_group
from cbench.cli.serve import serve_cmd

console = Console()


def _safe_path(base: str, *parts: str) -> Path:
    """Join parts onto base and raise UsageError if the result escapes base."""
    resolved = (Path(base).joinpath(*parts)).resolve()
    base_resolved = Path(base).resolve()
    if not resolved.is_relative_to(base_resolved):
        raise click.UsageError(
            f"Path traversal detected: '{'/'.join(parts)}' escapes '{base}'"
        )
    return resolved


def _safe_regex(pattern: str | None, option: str) -> re.Pattern | None:
    """Compile a user-supplied regex, raising UsageError on invalid syntax."""
    if pattern is None:
        return None
    try:
        return re.compile(pattern)
    except re.error as exc:
        raise click.UsageError(f"Invalid regex for {option}: {exc}") from exc


def _db_path(cbenchtest: str) -> Path:
    return Path(cbenchtest) / "cbench_results.db"


#: testset -> benchmarks gen-jobs skips unless selected with --match
#: (fileop: superseded by fio, which also covers data IOPS).
_DEFAULT_SKIP: dict[str, set[str]] = {"iometadata": {"fileop"}}
#: single-node, non-MPI benchmarks generated once (numprocs 1), not per ppn x size;
#: they size their own concurrency from the IO thread count
_SINGLE_INSTANCE = {"fio", "bonnie", "iozone", "gpfsperf"}
#: whole-node MPI suites generated at ppn = IO threads, one job per node count
_NODE_SWEEP = {"io500", "gpfsperfmpi"}
#: single-node benchmarks generated once per node, pinned to it, for comparing
#: nodes (nodes from --nodelist, else the nodecheck facts' hosts)
_PER_NODE = {"gpfsperfnode"}


def _pin_to_node(cfg: ClusterConfig, node: str, ppn: int, testset: str, ident: str,
                 concurrent: bool) -> dict:
    """Scheduler tokens that place a per-node job on ``node``. Under Slurm the
    jobs also share one name with --dependency=singleton, so they run one at a
    time unless ``concurrent``. Other schedulers are not pinned: the job then
    runs gpfsperf on its node over ssh (see iogpfs_gpfsperfnode.in)."""
    spec = f"-N 1 --ntasks-per-node {ppn} -w {node}"
    if not concurrent:
        spec += f" -J cbench-pernode-{testset}-{ident} --dependency=singleton"
    return {"SLURM_NODESPEC": spec, "TORQUE_NODESPEC": f"{node}:ppn={ppn}"}


def _cfg(config: str | None) -> ClusterConfig:
    return load_config(config)


# ---------------------------------------------------------------------------
# CLI root
# ---------------------------------------------------------------------------

@click.group()
@click.version_option(package_name="cbench", prog_name="cbench")
def cli() -> None:
    """Cbench HPC benchmarking framework — Python toolchain."""


cli.add_command(nodecheck_cmd)
cli.add_command(nodehwtest_group)
cli.add_command(utils_group)
cli.add_command(diag_cmd)
cli.add_command(snb_group)
cli.add_command(build_group)
cli.add_command(serve_cmd)


@cli.command("mcp")
def mcp_cmd() -> None:
    """Run the cbench MCP server on stdio, for MCP clients such as Claude.

    Needs the mcp extra: pip install 'cbench[mcp]' (Python 3.10+). Register it
    with a client, for example Claude Code:

    \b
        claude mcp add cbench -e CBENCHTEST=/path -- cbench mcp

    Read-only tools: status, get_config, list_testsets, node_facts, watch_jobs,
    query_results, task_status, check_deps, check_updates. Tools that change
    anything (set_config, run_nodecheck, gen_jobs, start_jobs, build_benchmark)
    only return the command or cluster.yaml diff unless called with
    confirm=true. parse_results needs no confirm (re-parsing overwrites).
    System packages are never installed; check_deps only suggests them.
    """
    try:
        from cbench.mcp_server import main as serve_mcp
    except ImportError as exc:
        raise click.ClickException(
            f"the MCP server needs the mcp package ({exc}); install it with "
            "pip install 'cbench[mcp]' (Python 3.10+)") from exc
    serve_mcp()


# ---------------------------------------------------------------------------
# gen-jobs
# ---------------------------------------------------------------------------

@cli.command("gen-jobs")
@click.option("--testset", default=None, help="Testset name (e.g. bandwidth, linpack)")
@click.option("--profile", default=None, metavar="NAME",
              help="Generate an IO profile (e.g. io-default) instead of a testset; jobs go "
                   "under <cbenchtest>/<profile>/<ident>/")
@click.option("--group", "groups", multiple=True, metavar="GROUP",
              help="Profile group(s) to generate (repeatable, or 'all'; default: the "
                   "profile's default groups, e.g. node-local)")
@click.option("--ident", required=True, help="Run identifier (e.g. mycluster-run1)")
@click.option("--ppn", default=None, help="Comma-separated PPN values to generate (default: all from config)")
@click.option("--maxprocs", default=None, type=int, help="Limit max number of processes")
@click.option("--run-type", default="both", type=click.Choice(["batch", "interactive", "both"]))
@click.option("--dry-run", is_flag=True, help="Print generated scripts without writing")
@click.option("--config", default=None, help="Path to cluster.yaml")
@click.option("--cbenchtest", default=None, envvar="CBENCHTEST", help="CBENCHTEST directory")
@click.option("--match", default=None, metavar="REGEX",
              help="Only generate jobs whose name matches REGEX; also selects benchmarks "
                   "skipped by default (e.g. --match fileop)")
@click.option("--nodefacts", default=None, metavar="NAME|PATH",
              help="Node facts from `cbench nodecheck` (name under <cbenchtest>/nodefacts/ or a "
                   ".json path); sizes IO tests from the real compute nodes")
@click.option("--fio-runtime", type=click.IntRange(min=1), default=None, metavar="SECONDS",
              help="Time cap per fio data job (default: cluster.yaml fio_runtime_s, else 300)")
@click.option("--io500-stonewall", type=click.IntRange(min=1), default=None, metavar="SECONDS",
              help="IO500 stonewall per write phase (default: cluster.yaml io500_stonewall_s, "
                   "else 300; below 300 IO500 marks the run [INVALID])")
@click.option("--nodelist", default=None, metavar="HOSTLIST",
              help="Nodes for per-node jobs (gpfs-node group), e.g. 'n[1-8]' "
                   "(default: the hosts in --nodefacts)")
@click.option("--concurrent", is_flag=True,
              help="Per-node jobs: let the scheduler run them at the same time (default: one "
                   "node at a time via Slurm --dependency=singleton)")
@click.option("--heartbeat", type=click.IntRange(min=0), default=None, metavar="SECONDS",
              help="Seconds between the 'still running' lines each job writes to stderr "
                   "(default: cluster.yaml job_heartbeat_s, else 60; 0 disables)")
def gen_jobs(
    testset: str | None,
    profile: str | None,
    groups: tuple[str, ...],
    ident: str,
    ppn: str | None,
    maxprocs: int | None,
    run_type: str,
    dry_run: bool,
    config: str | None,
    cbenchtest: str | None,
    match: str | None,
    nodefacts: str | None,
    fio_runtime: int | None,
    io500_stonewall: int | None,
    heartbeat: int | None,
    nodelist: str | None,
    concurrent: bool,
) -> None:
    """Generate batch and/or interactive job scripts for a testset or IO profile."""
    from cbench import hplsizing, iosizing, profiles
    from cbench.nodecheck import NodecheckError, load_facts

    if bool(testset) == bool(profile):
        raise click.UsageError("pass exactly one of --testset or --profile")
    if groups and not profile:
        raise click.UsageError("--group only applies with --profile")

    cfg = _cfg(config)
    if fio_runtime:
        cfg.fio_runtime_s = fio_runtime
    if io500_stonewall:
        cfg.io500_stonewall_s = io500_stonewall
    if heartbeat is not None:
        cfg.job_heartbeat_s = heartbeat
    cbenchtest = cbenchtest or os.environ.get("CBENCHTEST", ".")
    templates_dir = templates._templates_dir()
    match_re = _safe_regex(match, "--match")

    # Determine which PPN values to use
    ppn_values = [int(p) for p in ppn.split(",")] if ppn else cfg.ppn_levels

    # Node-aware IO: resolve node values up front and fail BEFORE rendering
    # anything if an IO template needs values we don't have (an unset token
    # would otherwise render as an empty string, e.g. a broken `-b ` for IOR).
    facts = None
    if nodefacts:
        try:
            facts, fact_warnings = load_facts(cbenchtest, nodefacts)
        except NodecheckError as exc:
            raise click.ClickException(str(exc)) from exc
        for w in fact_warnings:
            console.print(f"[yellow]WARNING: {w}[/yellow]")
    nv = iosizing.resolve_node_values(cfg, facts)
    if nv.cpus:
        iosizing.io_threads(nv, cfg)  # surfaces io_threads_basis fallback warnings now
    for w in nv.warnings:
        console.print(f"[yellow]WARNING: {w}[/yellow]")
    # Members to generate: (home testset whose template is used, template
    # benchmark, benchmark name in the job name). Jobs are written under
    # out_ts — the testset, or the profile acting as a virtual testset.
    # (home testset, template benchmark, job benchmark name, target override)
    members: list[tuple[str, str, str, str | None]] = []
    if profile:
        try:
            prof = profiles.get_profile(profile, cfg.io_profiles, templates_dir)
            selected = profiles.select_groups(prof, groups)
        except profiles.ProfileError as exc:
            raise click.UsageError(str(exc)) from exc
        out_ts = profile
        used: list[str] = []
        for gname in selected:
            group = prof.groups[gname]
            if not (nv.targets.get(group.target) or {}).get("path"):
                hint = (" (and io_targets.parallel is not GPFS per the node facts)"
                        if group.target == "gpfs" else "")
                console.print(f"[yellow]WARNING: skipping group '{gname}': io_targets.{group.target} "
                              f"is not set in cluster.yaml{hint}[/yellow]")
                continue
            if not group.members:
                console.print(f"[yellow]WARNING: group '{gname}' has no benchmarks yet[/yellow]")
                continue
            target = group.target if group.route_members else None
            members += [(m.home, m.benchmark, profiles.job_benchmark(m, group), target)
                        for m in group.members]
            used.append(gname)
        if not members:
            raise click.ClickException(f"profile '{profile}': nothing to generate for groups "
                                       f"{', '.join(selected)}")
        console.print(f"Profile {profile}: generating groups {', '.join(used)}")
    else:
        out_ts = testset
        members = [(testset, t.stem[len(testset) + 1:], t.stem[len(testset) + 1:], None)
                   for t in sorted(templates_dir.glob(f"{testset}_*.in"))]
        if not members:
            console.print(f"[red]No templates found for testset '{testset}' in {templates_dir}[/red]")
            raise SystemExit(1)

        # Benchmarks superseded in the Python toolchain stay available (the Perl
        # tools still use their templates) but only run when --match selects them.
        default_skip = _DEFAULT_SKIP.get(testset, set())
        if not match_re:
            skipped_default = [m[1] for m in members if m[1] in default_skip]
            members = [m for m in members if m[1] not in default_skip]
            if skipped_default:
                console.print(f"Skipping {', '.join(skipped_default)} by default "
                              f"(superseded; select with --match)")
    benchmark_templates = [bench for _home, bench, _out, _target in members]

    sized = [b for home, b, _o, _t in members if iosizing.needs_io_sizing(home, b)]
    if sized and not nv.mem_io_kb:
        raise click.ClickException(
            f"testset '{out_ts}' sizes {', '.join(sized)} from node memory: pass --nodefacts "
            "NAME (run `cbench nodecheck` first) or set memory_per_node_mb explicitly in cluster.yaml"
        )
    threaded = [b for b in benchmark_templates if b in _SINGLE_INSTANCE | _NODE_SWEEP | _PER_NODE]
    if threaded and not nv.cpus:
        raise click.ClickException(
            f"testset '{out_ts}' sizes {', '.join(threaded)} concurrency from node CPUs: pass "
            "--nodefacts NAME (run `cbench nodecheck` first) or set procs_per_node explicitly "
            "in cluster.yaml"
        )
    if sized:
        console.print(f"Node-aware IO sizing from {nv.source}: MemTotal {nv.mem_io_kb} kB (IO)")
    if not ppn and nv.cpus and any(b.startswith("mdtest") for b in benchmark_templates):
        threads = iosizing.io_threads(nv, cfg)
        ppn_values = iosizing.ppn_levels_for_metadata(ppn_values, cfg.procs_per_node, threads)
        console.print(f"Metadata ppn levels from {nv.source} ({threads} IO threads/node): {ppn_values}")
    # Linpack/HPCC: HPL.dat / hpccinf.txt are memory-sized (MIN MemTotal).
    hpl_benches = [b for b in benchmark_templates if hplsizing.input_spec(b)]
    hpl_mem_mb = (nv.mem_nonio_kb or 0) // 1024
    hpl_factors = hplsizing.mem_util_factors(cfg, out_ts)
    if hpl_benches and not hpl_mem_mb:
        raise click.ClickException(
            f"testset '{out_ts}' sizes {', '.join(hpl_benches)} (HPL N) from node memory: pass "
            "--nodefacts NAME (run `cbench nodecheck` first) or set memory_per_node_mb explicitly "
            "in cluster.yaml"
        )
    if hpl_benches:
        console.print(f"HPL sizing from {nv.source}: {hpl_mem_mb} MB/node (min MemTotal), "
                      f"memory_util_factors {hpl_factors}")
    caveats: set[str] = set()
    gen_warnings: set[str] = set()
    skipped_no_grid: list[str] = []
    run_types = ["batch", "interactive"] if run_type == "both" else [run_type]
    total = 0

    def emit(home: str, bench: str, out_bench: str, ppn_val: int, numprocs: int,
             numnodes: int, walltime: str, launch_cmd: str, target: str | None = None,
             node: str | None = None) -> None:
        """Render and write one job (every run type) for a member at (ppn, numprocs).
        ``target``: a custom profile group's io_targets key, overriding the
        benchmark's usual target. ``node``: the node a per-node job is pinned to."""
        nonlocal total
        jobname = f"{out_bench}-{ppn_val}ppn-{numprocs}"
        if match_re and not match_re.search(jobname):
            return
        try:
            kw = {"testset": home, "benchmark": bench, "target": target}
            if bench == "fio":
                io_extra, warning = iosizing.fio_tokens(nv, cfg, **kw)
                if warning:
                    gen_warnings.add(f"{jobname}: {warning}")
            elif bench == "iozone":
                io_extra = iosizing.iozone_tokens(nv, cfg, **kw)
            elif bench == "gpfsperf":
                io_extra = iosizing.gpfsperf_tokens(nv, cfg, **kw)
            elif bench == "io500":
                io_extra = iosizing.io500_tokens(nv, cfg, **kw)
            elif bench == "gpfsperfnode":
                io_extra = {**iosizing.gpfsperfnode_tokens(nv, cfg, node=node, **kw),
                            **_pin_to_node(cfg, node, ppn_val, out_ts, ident, concurrent)}
            elif bench == "gpfsperfmpi":
                io_extra = iosizing.gpfsperfmpi_tokens(nv, cfg, numnodes=numnodes,
                                                       numprocs=numprocs, **kw)
            elif iosizing.needs_io_sizing(home, bench) and bench.startswith("ior"):
                io_extra = iosizing.ior_tokens(nv, cfg, ppn=ppn_val, numprocs=numprocs, **kw)
            elif iosizing.needs_io_sizing(home, bench):
                io_extra = iosizing.bonnie_tokens(nv, cfg, **kw)
            elif target or iosizing.target_name_for(bench):
                io_extra = iosizing.target_tokens(nv, bench, target)
            else:
                io_extra = {}
        except iosizing.IOSizingError as exc:
            raise click.ClickException(str(exc)) from exc
        if io_extra.get("IO_CAVEAT"):
            caveats.add(f"{jobname}: {io_extra['IO_CAVEAT']}")
        if nv.labels:
            io_extra = {**io_extra, "CBENCH_LABELS": nv.labels}
        hpl_spec = hplsizing.input_spec(bench)
        hpl_input = None
        if hpl_spec:
            try:
                hpl_input = hplsizing.render(
                    hpl_spec, templates_dir, numprocs=numprocs, ppn=ppn_val,
                    mem_per_node_mb=hpl_mem_mb, factors=hpl_factors,
                )
            except hplsizing.HplSizingError as exc:
                raise click.ClickException(str(exc)) from exc
            if hpl_input is None:
                skipped_no_grid.append(jobname)
                return
            io_extra = {**io_extra,
                        "MEM_UTIL_FACTORS": ",".join(str(f) for f in hpl_factors)}
        for rtype in run_types:
            try:
                raw = templates.build_job_template(home, bench, rtype, cfg)
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
                benchmark=out_bench,
                testset=out_ts,
                ident=ident,
                run_type=rtype,
                launch_cmd=launch_cmd,
                cfg=cfg,
                cbenchtest=cbenchtest,
                extra=io_extra,
            )

            ext = schedulers.extension(cfg) if rtype == "batch" else ".sh"
            script_name = f"{jobname}{ext}"
            job_dir = _safe_path(cbenchtest, out_ts, ident, jobname)

            if dry_run:
                console.rule(f"{job_dir}/{script_name}")
                console.print(script)
            else:
                job_dir.mkdir(parents=True, exist_ok=True)
                (job_dir / script_name).write_text(script)
                (job_dir / script_name).chmod(0o755)

            total += 1

        if hpl_input is not None:
            input_path = _safe_path(cbenchtest, out_ts, ident, jobname, hpl_spec.filename)
            if dry_run:
                console.rule(str(input_path))
                console.print(hpl_input)
            else:
                input_path.parent.mkdir(parents=True, exist_ok=True)
                input_path.write_text(hpl_input)

    for ppn_val in ppn_values:
        max_procs_for_ppn = cfg.max_ppn_procs.get(str(ppn_val), ppn_val * cfg.max_nodes)
        valid_sizes = [n for n in templates.RUN_SIZES if n <= max_procs_for_ppn]
        if maxprocs:
            valid_sizes = [n for n in valid_sizes if n <= maxprocs]

        for numprocs in valid_sizes:
            numnodes = max(1, math.ceil(numprocs / ppn_val))
            walltime = templates.compute_walltime(numprocs, valid_sizes, cfg)
            launch_cmd = launchers.build_launch_cmd(numprocs, ppn_val, numnodes, cfg)
            for home, bench, out_bench, target in members:
                if bench not in _SINGLE_INSTANCE | _NODE_SWEEP | _PER_NODE:
                    emit(home, bench, out_bench, ppn_val, numprocs, numnodes, walltime, launch_cmd,
                         target)

    # Single-node, non-MPI benchmarks: one job at their real concurrency — T
    # IO threads on 1 node, named <bench>-<T>ppn-<T> — so the name, the
    # scheduler request (T tasks on one node, not 1) and the parsed ppn agree.
    singles = [m for m in members if m[1] in _SINGLE_INSTANCE]
    if singles:
        threads = iosizing.io_threads(nv, cfg)
        launch_cmd = launchers.build_launch_cmd(threads, threads, 1, cfg)
        walltime = templates.compute_walltime(threads, [threads], cfg)
        for home, bench, out_bench, target in singles:
            emit(home, bench, out_bench, threads, threads, 1, walltime, launch_cmd, target)

    # Whole-node MPI suites (IO500): ppn = IO threads, one job per node count
    # (1, 2, 4, ... up to max_nodes, and max_nodes itself), within --maxprocs.
    sweeps = [m for m in members if m[1] in _NODE_SWEEP]
    if sweeps:
        threads = iosizing.io_threads(nv, cfg)
        node_counts = sorted({n for n in (2 ** i for i in range(20)) if n <= cfg.max_nodes}
                             | {cfg.max_nodes})
        sizes = [threads * n for n in node_counts if not maxprocs or threads * n <= maxprocs]
        for numprocs in sizes:
            numnodes = numprocs // threads
            launch_cmd = launchers.build_launch_cmd(numprocs, threads, numnodes, cfg)
            walltime = templates.compute_walltime(numprocs, sizes, cfg)
            for home, bench, out_bench, target in sweeps:
                emit(home, bench, out_bench, threads, numprocs, numnodes, walltime, launch_cmd,
                     target)

    # Per-node benchmarks: the single-node job once per node, pinned to it and
    # named <bench>-<node>-<T>ppn-<T>, so parse can compare the nodes.
    per_node = [m for m in members if m[1] in _PER_NODE]
    if per_node:
        nodes = hostlist.expand(nodelist) if nodelist else list(nv.hosts)
        # each name is written into a job script (NODE="...") and a scheduler
        # option (-w), so it must be a plain host name
        bad = hostlist.invalid_hostnames(nodes)
        if bad:
            raise click.UsageError(f"not a valid host name: {', '.join(map(repr, bad))}")
        if not nodes:
            gen_warnings.add(
                f"skipping {', '.join(m[1] for m in per_node)}: no node list (pass --nodelist, or "
                "--nodefacts from a `cbench nodecheck` of the nodes to compare)")
        else:
            threads = iosizing.io_threads(nv, cfg)
            launch_cmd = launchers.build_launch_cmd(threads, threads, 1, cfg)
            walltime = templates.compute_walltime(threads, [threads], cfg)
            for home, bench, out_bench, target in per_node:
                for node in nodes:
                    emit(home, bench, f"{out_bench}-{node}", threads, threads, 1, walltime,
                         launch_cmd, target, node=node)

    if skipped_no_grid:
        console.print(f"[yellow]WARNING: no HPL P x Q grid (P:Q within 1:3) for "
                      f"{len(skipped_no_grid)} job(s), not generated: "
                      f"{', '.join(skipped_no_grid)}[/yellow]")
    for note in sorted(nv.notes):
        console.print(f"NOTE: io_profile {note}")
    for w in sorted(gen_warnings):
        console.print(f"[yellow]WARNING: {w}[/yellow]")
    for c in sorted(caveats):
        console.print(f"[yellow]WARNING (capacity cap): {c}[/yellow]")
    action = "Would generate" if dry_run else "Generated"
    console.print(f"[green]{action} {total} job script(s) for testset '{out_ts}', ident '{ident}'[/green]")


# ---------------------------------------------------------------------------
# start-jobs
# ---------------------------------------------------------------------------

@cli.command("start-jobs")
@click.option("--testset", required=True)
@click.option("--ident", required=True)
@click.option("--batch", "mode", flag_value="batch", default=True)
@click.option("--interactive", "mode", flag_value="interactive")
@click.option("--echo-output", is_flag=True,
              help="With --interactive: also stream each job's output to the terminal "
                   "(sets CBENCH_ECHO_OUTPUT=YES; output still goes to the job's .o file)")
@click.option("--concurrent", is_flag=True,
              help="With --interactive: start every job at once and wait for all of them "
                   "(default: one at a time), e.g. per-node gpfsperf under shared load")
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
    echo_output: bool,
    concurrent: bool,
    throttle: int | None,
    match: str | None,
    exclude: str | None,
    minprocs: int | None,
    maxprocs: int | None,
    delay: float,
    poll_interval: int,
    dry_run: bool,
    config: str | None,
    cbenchtest: str | None,
) -> None:
    """Submit jobs from a generated testset/ident directory."""
    if echo_output and mode != "interactive":
        raise click.UsageError("--echo-output only applies with --interactive")
    if concurrent and mode != "interactive":
        raise click.UsageError("--concurrent only applies with --interactive (for batch jobs, "
                               "generate per-node jobs with gen-jobs --concurrent)")
    cfg = _cfg(config)
    cbenchtest = cbenchtest or os.environ.get("CBENCHTEST", ".")
    ident_dir = _safe_path(cbenchtest, testset, ident)

    if not ident_dir.exists():
        console.print(f"[red]Directory not found: {ident_dir}[/red]")
        raise SystemExit(1)

    match_re = _safe_regex(match, "--match")
    exclude_re = _safe_regex(exclude, "--exclude")

    # gen-jobs writes batch scripts with the scheduler's extension and
    # interactive scripts as .sh; run the kind that was asked for
    ext = ".sh" if mode == "interactive" else schedulers.extension(cfg)
    # Discover job scripts matching *-*ppn-* pattern
    scripts: list[Path] = sorted(ident_dir.glob(f"**/*-*ppn-*{ext}"))

    # Apply filters
    def _keep(path: Path) -> bool:
        name = path.stem
        if match_re and not match_re.search(name):
            return False
        if exclude_re and exclude_re.search(name):
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
                    _submit_batch(cmd, script)
                submitted += 1
                if delay:
                    time.sleep(delay)
            if remaining:
                time.sleep(poll_interval)
    elif mode == "interactive" and concurrent and not dry_run:
        # every job at once; each still writes its own .o file
        env = {**os.environ, "CBENCH_ECHO_OUTPUT": "YES"} if echo_output else None
        procs = []
        for script in scripts:
            console.print(f"[bold]Starting {script.parent.name}[/bold]")
            procs.append((script, subprocess.Popen(["bash", str(script)], shell=False, env=env)))
        failed = [f"{script.parent.name} (exit {rc})" for script, p in procs
                  if (rc := p.wait()) != 0]
        submitted = len(procs)
        if failed:
            console.print(f"[red]{len(failed)} of {submitted} interactive job(s) exited nonzero: "
                          f"{', '.join(failed)}[/red]")
            raise SystemExit(1)
    else:
        failed = []
        for script in scripts:
            if mode == "interactive":
                if dry_run:
                    console.print(f"[dim]Would run:[/dim] bash {script}")
                else:
                    env = {**os.environ, "CBENCH_ECHO_OUTPUT": "YES"} if echo_output else None
                    console.print(f"[bold]Running {script.parent.name}[/bold]")
                    rc = subprocess.run(["bash", str(script)], shell=False, check=False,
                                        env=env).returncode
                    # one failing job must not stop the rest of the run, but it
                    # must not pass unnoticed either
                    if rc != 0:
                        failed.append(f"{script.parent.name} (exit {rc})")
                        console.print(f"[red]{script.parent.name} exited {rc}[/red]")
            else:
                cmd = schedulers.submit_cmd(str(script), cfg)
                if dry_run:
                    console.print(f"[dim]Would submit:[/dim] {cmd}")
                else:
                    _submit_batch(cmd, script)
            submitted += 1
            if delay:
                time.sleep(delay)
        if failed:
            console.print(f"[red]{len(failed)} of {submitted} interactive job(s) exited nonzero: "
                          f"{', '.join(failed)}[/red]")
            raise SystemExit(1)

    action = "Would submit" if dry_run else "Submitted"
    console.print(f"[green]{action} {submitted} job(s)[/green]")


# ---------------------------------------------------------------------------
# parse
# ---------------------------------------------------------------------------

@cli.command("watch")
@click.option("--testset", required=True, help="Testset or profile name")
@click.option("--ident", required=True)
@click.option("--follow", type=int, is_flag=False, flag_value=10, default=None, metavar="[SECONDS]",
              help="Redraw every SECONDS (default 10) until no job is running or waiting to "
                   "start; then exit 0, or 1 if any job failed or went stale")
@click.option("--stale-after", type=click.IntRange(min=1), default=None, metavar="SECONDS",
              help="Call a running job stale after this long without a heartbeat (default: "
                   "3 of its heartbeat intervals)")
@click.option("--config", default=None)
@click.option("--cbenchtest", default=None, envvar="CBENCHTEST")
def watch_cmd(testset: str, ident: str, follow: int | None, stale_after: int | None,
              config: str | None, cbenchtest: str | None) -> None:
    """Show each job's state from its heartbeat file: running, stale (no heartbeat
    for 3 intervals: killed?), finished, failed (exit code), or not started."""
    from rich.live import Live

    from cbench import watch

    cfg = _cfg(config)
    cbenchtest = cbenchtest or os.environ.get("CBENCHTEST", ".")
    ident_dir = _safe_path(cbenchtest, testset, ident)
    if not ident_dir.is_dir():
        raise click.ClickException(f"no jobs at {ident_dir} (run gen-jobs first)")
    default_interval = cfg.job_heartbeat_s or 60

    def snapshot():
        statuses = watch.scan(ident_dir, default_interval=default_interval,
                              stale_after=stale_after)
        return statuses, _watch_table(statuses, testset, ident)

    if follow is None:
        _statuses, table = snapshot()
        console.print(table)
        return
    with Live(console=console, auto_refresh=False) as live:
        while True:
            statuses, table = snapshot()
            live.update(table, refresh=True)
            if watch.all_done(statuses):
                break
            time.sleep(max(1, follow))
    raise SystemExit(0 if watch.succeeded(statuses) else 1)


def _watch_table(statuses, testset: str, ident: str):
    from rich.console import Group
    from rich.text import Text

    from cbench import watch

    styles = {watch.RUNNING: "cyan", watch.FINISHED: "green", watch.FAILED: "red",
              watch.STALE: "bold red", watch.NOT_STARTED: "dim", watch.NO_HEARTBEAT: "yellow"}
    t = Table(title=f"{testset} / {ident}")
    for col in ("Job", "State", "Elapsed", "Exit", "Last update", "Detail"):
        t.add_column(col, justify="right" if col in ("Elapsed", "Exit", "Last update") else "left")
    for s in statuses:
        style = styles.get(s.status, "")
        t.add_row(s.job, f"[{style}]{s.status}[/{style}]" if style else s.status,
                  watch.hms(s.elapsed_s), "-" if s.rc is None else str(s.rc),
                  "-" if s.age_s is None else f"{watch.hms(s.age_s)} ago", s.detail)
    counts: dict[str, int] = {}
    for s in statuses:
        counts[s.status] = counts.get(s.status, 0) + 1
    order = (watch.RUNNING, watch.STALE, watch.FINISHED, watch.FAILED, watch.NOT_STARTED,
             watch.NO_HEARTBEAT)
    summary = "  ".join(f"{counts[k]} {k}" for k in order if counts.get(k))
    return Group(t, Text(summary or "no jobs"))


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
@click.option("--outlier-pct", default=10.0, type=click.FloatRange(min=0), show_default=True,
              help="Per-node jobs: flag a node this many percent worse than the median")
def parse_cmd(
    testset: str,
    ident: str,
    output: str,
    config: str | None,
    cbenchtest: str | None,
    no_db: bool,
    customparse: str | None,
    outlier_pct: float,
) -> None:
    """Parse benchmark output files and store results."""
    cfg = _cfg(config)
    cbenchtest = cbenchtest or os.environ.get("CBENCHTEST", ".")
    ident_dir = _safe_path(cbenchtest, testset, ident)

    # Build parse filter set from --customparse or cluster config
    filter_names: list[str] = []
    if customparse:
        filter_names = [n.strip() for n in customparse.split(",") if n.strip()]
    elif cfg.parse_filter_include:
        filter_names = [n for n in cfg.parse_filter_include if n in FILTER_MODULES]
    try:
        active_filters = build_filter_set(filter_names) if filter_names else {}
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc

    if not ident_dir.exists():
        console.print(f"[red]Directory not found: {ident_dir}[/red]")
        raise SystemExit(1)

    db: ResultsDB | None = None
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

        # Find stdout file (newest run when the job has been run more than once)
        stdout_file, stderr_file = _job_output_files(job_dir)
        if stdout_file is None:
            continue
        stdout = stdout_file.read_text(errors="replace")
        stderr = stderr_file.read_text(errors="replace") if stderr_file else ""

        # Run parse filters on combined output first
        filter_errors: list[str] = []
        if active_filters:
            filter_errors = apply_filters(active_filters, stdout + "\n" + stderr)

        parser = get_parser(benchmark)
        if parser is None:
            # "" (not None): every other row stores "", and NULL would slip past
            # `status_detail = ''` queries
            status_detail = "; ".join(filter_errors)
            result = ParseResult(
                cluster=cfg.cluster_name, testset=testset, ident=ident,
                jobname=jobname, benchmark=benchmark,
                numprocs=numprocs, ppn=ppn_val, numnodes=numnodes,
                status="NO_PARSER" if not filter_errors else "FILTER_ERROR",
                status_detail=status_detail,
            )
        else:
            parsed = parser.parse(stdout, stderr)
            # Filter errors override a PASSED result, and a NOTSTARTED one: a job
            # whose output shows launch errors did start, and failed
            if filter_errors and parsed.status in ("PASSED", "NOTSTARTED"):
                status = "FILTER_ERROR"
                status_detail = "; ".join(filter_errors)
            else:
                status = parsed.status
                # a parser error keeps its status; filter hits say why it failed
                status_detail = "; ".join(filter(None, [parsed.status_detail, *filter_errors]))
            # gen-jobs writes a CBENCH CAVEAT line when it had to shrink a run
            # (e.g. IO capped to free space) and a CBENCH LABEL line with the
            # interconnect / GPFS transport nodecheck saw; keep them with the result.
            caveats = _caveat_lines(stdout)
            if caveats:
                status_detail = "; ".join(filter(None, [status_detail, *caveats]))
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
            "status_detail": result.status_detail,
            "metrics": result.metrics,
            # per-node jobs (gpfs-node) name their node; parse compares them
            "node": nodecompare.node_from_output(stdout),
        })

    if output == "json":
        json_path = ident_dir / "results.json"
        json_path.write_text(json.dumps(results, indent=2))
        console.print(f"[green]Results written to {json_path}[/green]")
    else:
        _render_table(results, testset, ident)
        _render_node_comparison(results, outlier_pct)

    summary = _summarize(results)
    console.print(
        f"\n[bold]Summary:[/bold] "
        f"[green]{summary.get('PASSED', 0)} PASSED[/green]  "
        f"[red]{summary.get('ERROR', 0)} ERROR[/red]  "
        f"[yellow]{summary.get('OTHER', 0)} OTHER[/yellow]"
    )


def _submit_batch(cmd: str, script: Path) -> None:
    """Run a scheduler submit command; a failed submission must not be counted."""
    try:
        result = subprocess.run(shlex.split(cmd), shell=False, check=False)
    except OSError as e:
        raise AssertionError(f"Failed to run batch submit command {cmd!r} "
                             f"for {script.parent.name}: {e}") from e
    if result.returncode != 0:
        raise AssertionError(f"Batch submit for {script.parent.name} exited "
                             f"{result.returncode}: {cmd}")


def _job_output_files(job_dir: Path) -> tuple[Path | None, Path | None]:
    """(stdout, stderr) of a job's most recent run.

    A job dir collects one ``<job>.o<id>`` (or ``slurm-<id>.out``) per run and
    may hold stray files, so take the newest stdout rather than whichever the
    directory listing returns first. stderr is the matching ``.e<id>`` when it
    exists, else the newest ``*.e*``.
    """
    stdouts = [f for f in (*job_dir.glob("*.o*"), *job_dir.glob("slurm-*.out")) if f.is_file()]
    if not stdouts:
        return None, None
    stdout = max(stdouts, key=lambda f: (f.stat().st_mtime, f.name))
    m = re.search(r"\.o([^.]*)$", stdout.name)
    paired = stdout.with_name(stdout.name[: m.start()] + ".e" + m.group(1)) if m else None
    if paired is not None and paired.is_file():
        return stdout, paired
    stderrs = [f for f in job_dir.glob("*.e*") if f.is_file()]
    return stdout, (max(stderrs, key=lambda f: (f.stat().st_mtime, f.name)) if stderrs else None)


def _caveat_lines(stdout: str) -> list[str]:
    """Unique ``CBENCH CAVEAT:`` and ``CBENCH LABEL:`` lines from job output, in order."""
    seen: dict[str, None] = {}
    for line in stdout.splitlines():
        for marker in ("CBENCH CAVEAT:", "CBENCH LABEL:"):
            idx = line.find(marker)
            if idx >= 0:
                seen.setdefault(line[idx:].strip(), None)
                break
    return list(seen)


def _render_node_comparison(results: list[dict], pct: float) -> None:
    """Per-node jobs: one row per node, then the nodes more than ``pct`` percent
    worse than the median (cbench.nodecompare)."""
    groups, outliers = nodecompare.compare(results, pct)
    for group, by_node in sorted(groups.items()):
        metrics = sorted({m for ms in by_node.values() for m in ms if nodecompare.compared(m)})
        t = Table(title=f"Per-node comparison: {group} ({len(by_node)} nodes)")
        t.add_column("Node", style="cyan")
        for m in metrics:
            t.add_column(m, justify="right")
        flagged = {(o.node, o.metric) for o in outliers if o.group == group}
        for node in sorted(by_node):
            cells = []
            for m in metrics:
                v = by_node[node].get(m)
                cell = "" if v is None else f"{v:.4g}"
                cells.append(f"[red]{cell}[/red]" if (node, m) in flagged else cell)
            t.add_row(node, *cells)
        console.print(t)
        if len(by_node) < 2:
            console.print("  (one node: nothing to compare)")
    if outliers:
        console.print(f"[red]Outlier nodes (more than {pct:g}% worse than the median):[/red]")
        for o in outliers:
            console.print(f"  [red]{o.node}[/red] {o.group} {o.metric}={o.value:.4g} "
                          f"(median {o.median:.4g}, {o.pct_worse:.0f}% worse)")
    elif groups and any(len(b) > 1 for b in groups.values()):
        console.print(f"[green]No outlier nodes (all within {pct:g}% of the median)[/green]")


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
# make-skel
# ---------------------------------------------------------------------------

@cli.command("make-skel")
@click.option("--skelname", default="setvars", show_default=True,
              help="Skeleton template name (matches skeleton_<name>.in in templates/)")
@click.option("--ppn", default=1, show_default=True, type=int,
              help="Processes per node for substitution")
@click.option("--numprocs", "--procs", default=1, show_default=True, type=int,
              help="Number of processes for substitution")
@click.option("--ident", default=None,
              help="Run identifier substituted into the script (default: <cluster>1)")
@click.option("--outdir", default=".", show_default=True, type=click.Path(),
              help="Directory to write generated scripts into")
@click.option("--dry-run", is_flag=True, help="Print scripts without writing")
@click.option("--config", default=None)
@click.option("--cbenchtest", default=None, envvar="CBENCHTEST")
def make_skel(
    skelname: str,
    ppn: int,
    numprocs: int,
    ident: str | None,
    outdir: str,
    dry_run: bool,
    config: str | None,
    cbenchtest: str | None,
) -> None:
    """Generate skeleton batch and interactive job scripts from a template.

    Available skeleton templates are listed in $CBENCHOME/templates/skeleton_*.in.
    Defaults to 'setvars' which expands every common Cbench substitution token.
    """
    cfg = _cfg(config)
    cbenchtest = cbenchtest or os.environ.get("CBENCHTEST", ".")
    ident = ident or f"{cfg.cluster_name}1"
    numnodes = max(1, math.ceil(numprocs / ppn))
    walltime = cfg.default_walltime
    launch_cmd = launchers.build_launch_cmd(numprocs, ppn, numnodes, cfg)
    outdir_p = Path(outdir)

    jobname = f"{skelname}-{ppn}ppn-{numprocs}"
    written: list[str] = []

    for rtype in ("batch", "interactive"):
        try:
            raw = templates.build_job_template("skeleton", skelname, rtype, cfg)
        except FileNotFoundError as e:
            console.print(f"[yellow]No skeleton_{skelname}.in template found — "
                          f"check $CBENCHOME/templates/[/yellow]")
            raise SystemExit(1) from e

        script = templates.substitute(
            raw,
            numprocs=numprocs,
            ppn=ppn,
            numnodes=numnodes,
            walltime=walltime,
            jobname=jobname,
            benchmark=skelname,
            testset="skeleton",
            ident=ident,
            run_type=rtype,
            launch_cmd=launch_cmd,
            cfg=cfg,
            cbenchtest=cbenchtest,
        )

        ext = schedulers.extension(cfg) if rtype == "batch" else ".sh"
        filename = f"{jobname}{ext}"

        if dry_run:
            console.rule(filename)
            console.print(script)
        else:
            outdir_p.mkdir(parents=True, exist_ok=True)
            dest = outdir_p / filename
            dest.write_text(script)
            if rtype == "interactive":
                dest.chmod(dest.stat().st_mode | 0o755)
            written.append(filename)

    if not dry_run:
        for f in written:
            console.print(f"[green]Wrote:[/green] {outdir_p / f}")


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
    match: str | None,
    target_status: str,
    config: str | None,
    cbenchtest: str | None,
) -> None:
    """Remove job directories whose parse status matches --status (default: ERROR).

    By default runs in preview mode — pass --force to actually delete.
    """
    _cfg(config)  # load for the side effect of validating cluster.yaml
    cbenchtest = cbenchtest or os.environ.get("CBENCHTEST", ".")
    ident_dir = _safe_path(cbenchtest, testset, ident)
    match_re = _safe_regex(match, "--match")
    status_re = _safe_regex(target_status, "--status")

    if not ident_dir.exists():
        console.print(f"[red]Directory not found: {ident_dir}[/red]")
        raise SystemExit(1)

    to_remove: list[Path] = []

    for job_dir in sorted(ident_dir.iterdir()):
        if not job_dir.is_dir():
            continue
        jobname = job_dir.name
        if match_re and not match_re.search(jobname):
            continue

        parts = jobname.rsplit("-", 2)
        if len(parts) < 3:
            continue
        benchmark = parts[0]

        stdout_file, stderr_file = _job_output_files(job_dir)
        if stdout_file is None:
            # No output file — treat as not-started, not an error
            continue
        stdout = stdout_file.read_text(errors="replace")
        stderr = stderr_file.read_text(errors="replace") if stderr_file else ""

        parser = get_parser(benchmark)
        if parser is None:
            continue
        parsed = parser.parse(stdout, stderr)

        if status_re and status_re.search(parsed.status):
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
@click.option("--until", default=None, help="ISO date string upper bound, e.g. 2025-12-31")
@click.option("--limit", default=100, type=int)
@click.option("--output", default="table",
              type=click.Choice(["table", "json", "csv", "prometheus"]))
@click.option("--aggregate", is_flag=True, help="Show mean/min/max per metric grouped by benchmark")
@click.option("--trend", is_flag=True,
              help="Show metric values across idents over time (requires --benchmark and --metric)")
@click.option("--metric", default=None, help="Metric name for --trend")
@click.option("--cbenchtest", default=None, envvar="CBENCHTEST")
def query_cmd(
    benchmark: str | None,
    cluster: str | None,
    testset: str | None,
    ident: str | None,
    status: str | None,
    since: str | None,
    until: str | None,
    limit: int,
    output: str,
    aggregate: bool,
    trend: bool,
    metric: str | None,
    cbenchtest: str | None,
) -> None:
    """Query stored benchmark results from the SQLite database."""
    import csv as csv_mod
    import io
    import statistics as stats

    cbenchtest = cbenchtest or os.environ.get("CBENCHTEST", ".")
    db_path = _db_path(cbenchtest)
    if not db_path.exists():
        console.print(f"[red]No results database found at {db_path}[/red]")
        raise SystemExit(1)

    db = ResultsDB(db_path)

    # -- trend mode --
    if trend:
        if not benchmark or not metric:
            console.print("[red]--trend requires --benchmark and --metric[/red]")
            raise SystemExit(1)
        trend_rows = db.trend(
            benchmark=benchmark,
            metric=metric,
            cluster=cluster,
            testset=testset,
            since=since,
            until=until,
            limit=limit,
        )
        if output == "json":
            click.echo(json.dumps(trend_rows, indent=2))
            return
        if output == "csv":
            buf = io.StringIO()
            writer = csv_mod.writer(buf)
            writer.writerow(["ident", "parsed_at", "value", "units", "count"])
            for r in trend_rows:
                writer.writerow([r["ident"], (r["parsed_at"] or "")[:19],
                                  f"{r['value']:.6g}", r["units"], r["count"]])
            click.echo(buf.getvalue(), nl=False)
            return
        # table
        t = Table(title=f"Trend: {benchmark} / {metric}", show_lines=False)
        t.add_column("Ident", style="cyan")
        t.add_column("Parsed At", style="dim")
        t.add_column("Value", justify="right")
        t.add_column("Units", style="dim")
        t.add_column("Δ%", justify="right")
        t.add_column("N", justify="right")
        prev_val = None
        for r in trend_rows:
            val = r["value"]
            if prev_val is not None and prev_val != 0:
                delta = (val - prev_val) / abs(prev_val) * 100
                delta_str = f"[green]+{delta:.1f}%[/green]" if delta >= 0 else f"[red]{delta:.1f}%[/red]"
            else:
                delta_str = "—"
            t.add_row(
                r["ident"], (r["parsed_at"] or "")[:19],
                f"{val:.4g}", r["units"], delta_str, str(r["count"]),
            )
            prev_val = val
        console.print(t)
        return

    rows = db.query(
        benchmark=benchmark,
        cluster=cluster,
        testset=testset,
        ident=ident,
        status=status,
        since=since,
        until=until,
        limit=limit,
    )

    # -- prometheus output --
    if output == "prometheus":
        from datetime import datetime as _dt

        def _prom_label(s: str) -> str:
            return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

        lines = [
            "# HELP cbench_metric_value Cbench benchmark metric value",
            "# TYPE cbench_metric_value gauge",
        ]
        for row in rows:
            ts_ms = ""
            if row["parsed_at"]:
                try:
                    dt = _dt.fromisoformat(row["parsed_at"].replace("Z", "+00:00"))
                    ts_ms = str(int(dt.timestamp() * 1000))
                except ValueError as e:
                    raise AssertionError(
                        f"Corrupt parsed_at timestamp {row['parsed_at']!r} in results DB "
                        f"(benchmark={row['benchmark']}, ident={row['ident']}): {e}"
                    ) from e
            for m_name, mv in row.get("metrics", {}).items():
                labels = ",".join([
                    f'benchmark="{_prom_label(row["benchmark"])}"',
                    f'cluster="{_prom_label(row["cluster"])}"',
                    f'testset="{_prom_label(row["testset"])}"',
                    f'ident="{_prom_label(row["ident"])}"',
                    f'metric="{_prom_label(m_name)}"',
                ])
                line = f"cbench_metric_value{{{labels}}} {mv['value']}"
                if ts_ms:
                    line += f" {ts_ms}"
                lines.append(line)
        click.echo("\n".join(lines))
        return

    if aggregate:
        # Group metric values by (benchmark, metric)
        agg: dict[tuple[str, str], list[float]] = {}
        agg_units: dict[tuple[str, str], str] = {}
        for row in rows:
            bm = row["benchmark"]
            for metric, mv in row.get("metrics", {}).items():
                key = (bm, metric)
                agg.setdefault(key, []).append(mv["value"])
                agg_units[key] = mv.get("units", "")

        if output == "json":
            result = []
            for (bm, metric), vals in sorted(agg.items()):
                result.append({
                    "benchmark": bm, "metric": metric,
                    "mean": stats.mean(vals), "min": min(vals), "max": max(vals),
                    "count": len(vals), "units": agg_units[(bm, metric)],
                })
            click.echo(json.dumps(result, indent=2))
            return

        if output == "csv":
            buf = io.StringIO()
            writer = csv_mod.writer(buf)
            writer.writerow(["benchmark", "metric", "mean", "min", "max", "count", "units"])
            for (bm, metric), vals in sorted(agg.items()):
                writer.writerow([bm, metric,
                                  f"{stats.mean(vals):.6g}", f"{min(vals):.6g}", f"{max(vals):.6g}",
                                  len(vals), agg_units[(bm, metric)]])
            click.echo(buf.getvalue(), nl=False)
            return

        t = Table(title="Cbench Aggregated Results", show_lines=False)
        t.add_column("Benchmark", style="cyan")
        t.add_column("Metric")
        t.add_column("Mean", justify="right")
        t.add_column("Min", justify="right")
        t.add_column("Max", justify="right")
        t.add_column("N", justify="right")
        t.add_column("Units", style="dim")
        for (bm, metric), vals in sorted(agg.items()):
            t.add_row(
                bm, metric,
                f"{stats.mean(vals):.4g}", f"{min(vals):.4g}", f"{max(vals):.4g}",
                str(len(vals)), agg_units[(bm, metric)],
            )
        console.print(t)
        return

    if output == "json":
        click.echo(json.dumps(rows, indent=2))
        return

    if output == "csv":
        buf = io.StringIO()
        writer = csv_mod.writer(buf)
        writer.writerow(["id", "cluster", "testset", "ident", "jobname",
                          "benchmark", "numprocs", "status", "metric", "value", "units", "parsed_at"])
        for row in rows:
            metrics = row.get("metrics", {})
            if metrics:
                for metric, mv in metrics.items():
                    writer.writerow([
                        row["id"], row["cluster"], row["testset"], row["ident"],
                        row["jobname"], row["benchmark"], row["numprocs"],
                        row["status"], metric, mv["value"], mv.get("units", ""),
                        (row["parsed_at"] or "")[:19],
                    ])
            else:
                writer.writerow([
                    row["id"], row["cluster"], row["testset"], row["ident"],
                    row["jobname"], row["benchmark"], row["numprocs"],
                    row["status"], "", "", "", (row["parsed_at"] or "")[:19],
                ])
        click.echo(buf.getvalue(), nl=False)
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
