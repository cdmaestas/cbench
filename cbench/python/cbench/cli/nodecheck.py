"""cbench nodecheck — gather node facts across a pool and verify homogeneity.

Usage:
  cbench nodecheck --nodelist 'zima[1-4]' [--ignore NODES] [--name NAME]
  cbench nodecheck --partition PART      [--allow-heterogeneous]
"""

from __future__ import annotations

import subprocess
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from cbench import nodecheck as nc
from cbench.hostlist import compress, expand

console = Console()


def _partition_nodes(partition: str) -> str:
    try:
        res = subprocess.run(
            ["sinfo", "-h", "-p", partition, "-o", "%N"],
            capture_output=True, text=True, timeout=60,
        )
    except FileNotFoundError as e:
        raise click.UsageError("sinfo not found — --partition requires Slurm") from e
    nodes = ",".join(line.strip() for line in res.stdout.splitlines() if line.strip())
    if res.returncode != 0 or not nodes:
        raise click.UsageError(
            f"could not list nodes for partition '{partition}': {res.stderr.strip() or 'no nodes'}"
        )
    return nodes


@click.command("nodecheck")
@click.option("--nodelist", default=None, help="pdsh/Slurm hostlist, e.g. 'zima[1-4],zimad'")
@click.option("--partition", default=None, help="Slurm partition to check (uses sinfo; slurm only)")
@click.option("--ignore", "ignore_nodes", default=None, help="Hostlist of nodes to exclude")
@click.option("--name", default=None, help="Facts name (default: cluster_name from cluster.yaml)")
@click.option("--allow-heterogeneous", is_flag=True,
              help="Accept CPU/memory mismatch (warn; consumers use conservative min/max values)")
@click.option("--cbenchtest", default=None, envvar="CBENCHTEST",
              help="Test tree root; facts go to <cbenchtest>/nodefacts/ (default: .)")
@click.option("--config", default=None)
def nodecheck_cmd(
    nodelist: Optional[str],
    partition: Optional[str],
    ignore_nodes: Optional[str],
    name: Optional[str],
    allow_heterogeneous: bool,
    cbenchtest: Optional[str],
    config: Optional[str],
) -> None:
    """Probe every node in a pool and verify it is homogeneous.

    Collects logical CPU count, MemTotal, CPU model, and each configured
    io_target's fstype + free space, then writes <cbenchtest>/nodefacts/<name>.json
    for gen-jobs. Exits nonzero on heterogeneity (unless --allow-heterogeneous),
    a missing/mismatched IO target, or an unreachable node.
    """
    from cbench.config import load_config

    cfg = load_config(config)

    if bool(nodelist) == bool(partition):
        raise click.UsageError("give exactly one of --nodelist or --partition")
    if partition:
        if cfg.batch_method != "slurm":
            raise click.UsageError(
                f"--partition requires batch_method: slurm (cluster.yaml has '{cfg.batch_method}')"
            )
        nodelist = _partition_nodes(partition)

    try:
        hosts = expand(nodelist)
        ignored = expand(ignore_nodes) if ignore_nodes else []
    except ValueError as e:
        raise click.UsageError(str(e)) from e
    ignored = [h for h in ignored if h in hosts]
    hosts = [h for h in hosts if h not in set(ignored)]
    if not hosts:
        raise click.UsageError("no nodes left to check after applying --ignore")

    name = name or cfg.cluster_name
    cbenchtest = cbenchtest or "."
    try:
        path = nc.facts_path(cbenchtest, name)
        script = nc.build_probe_script(cfg.io_targets)
        if cfg.remotecmd_method == "pdsh":
            nc.check_pdsh_rcmd(cfg.remotecmd_rcmd)
            argv = nc.build_pdsh_argv(
                compress(hosts), script,
                rcmd=cfg.remotecmd_rcmd, exec_cmd=cfg.remotecmd_exec_cmd,
                extraargs=cfg.remotecmd_extraargs,
            )
            transport = {"method": "pdsh", "rcmd": cfg.remotecmd_rcmd}
            console.print(f"Probing {len(hosts)} node(s) via pdsh -R {cfg.remotecmd_rcmd}: {compress(hosts)}")
            stdout, stderr = nc.run_pdsh(argv)
        else:
            transport = {"method": "ssh", "rcmd": None}
            console.print(f"Probing {len(hosts)} node(s) via ssh: {compress(hosts)}")
            stdout, stderr = nc.run_ssh_loop(hosts, script)
    except nc.NodecheckError as e:
        raise click.ClickException(str(e)) from e

    per_host = nc.parse_output(stdout)
    result = nc.analyze(hosts, per_host, cfg.io_targets, allow_heterogeneous=allow_heterogeneous)

    rows = nc.group_summary(per_host, result["responded"], cfg.io_targets)
    if rows:
        tbl = Table(title=f"Node groups ({len(result['responded'])}/{len(hosts)} responded)")
        for col in ("hosts", "n", "cpus", "cores", "MemTotal GiB", "model"):
            tbl.add_column(col)
        for tname in sorted(cfg.io_targets):
            tbl.add_column(f"{tname} fstype")
        for r in rows:
            tbl.add_row(r["hosts"], str(r["count"]), r["cpus"], r["cores"], r["mem_gib"], r["model"],
                        *[r["targets"][t] for t in sorted(cfg.io_targets)])
        console.print(tbl)

    for w in result["verdict"]["warnings"]:
        console.print(f"[yellow]WARNING: {w}[/yellow]")
    for e in result["verdict"]["errors"]:
        console.print(f"[red]ERROR: {e}[/red]")
    if stderr.strip() and not result["verdict"]["ok"]:
        console.print("[dim]remote stderr:[/dim]")
        for line in stderr.strip().splitlines()[:20]:
            console.print(f"[dim]  {line}[/dim]")

    facts = nc.build_facts(
        name=name, nodelist=nodelist, ignored=ignored, transport=transport,
        allow_heterogeneous=allow_heterogeneous, per_host=per_host, result=result,
    )
    nc.write_facts(path, facts)
    status = "PASSED" if result["verdict"]["ok"] else "FAILED"
    console.print(f"nodecheck {status} — facts written to {path}")
    if not result["verdict"]["ok"]:
        raise SystemExit(1)
