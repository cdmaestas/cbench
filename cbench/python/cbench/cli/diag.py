"""cbench diag — apply parse filters to output files and report error aggregates.

Combines the functionality of output_parse_customparse.pl and
diag_output_parse.pl into a single command.

Usage examples:
  cbench diag file1.out file2.out
  cbench diag --testset bandwidth --ident run1
  cbench diag file.out --source-only --threshold 2
  cbench diag file.out --output json
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from cbench.parse_filters import build_filter_set, apply_filters, AVAILABLE as FILTER_MODULES

console = Console()

# Regex to extract src→dest from OMPI error messages produced by the openmpi filter.
# e.g. "OMPI error 'RETRY EXCEEDED ERROR' with status 12 (an966 to bn274)"
_OMPI_SRC_DEST_RE = re.compile(
    r"OMPI error '([^']+)' with status \d+ \((\S+) to (\S+)\)"
)


def _classify(message: str) -> tuple[str, Optional[str], Optional[str]]:
    """Return (error_type, src_node, dst_node) from a filter match string."""
    m = _OMPI_SRC_DEST_RE.search(message)
    if m:
        label = "OMPI_ERROR_" + m.group(1).strip().replace(" ", "_")
        return label, m.group(2), m.group(3)
    return message, None, None


def _scan_file(
    path: Path,
    filters: dict[str, str],
) -> list[tuple[str, str, Optional[str], Optional[str]]]:
    """Return list of (filename, error_type, src, dst) tuples for a single file."""
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return []
    hits = []
    for msg in apply_filters(filters, text):
        error_type, src, dst = _classify(msg)
        hits.append((path.name, error_type, src, dst))
    return hits


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.command("diag")
@click.argument("files", nargs=-1, type=click.Path(exists=True))
@click.option("--testset", default=None, help="Scan all output files in this testset")
@click.option("--ident", default=None, help="Test identifier to scan (used with --testset)")
@click.option("--cbenchtest", default=None, envvar="CBENCHTEST")
@click.option("--filters", "filter_names", default=None,
              help="Comma-separated filter modules (default: all)")
@click.option("--threshold", default=1, show_default=True, type=int,
              help="Minimum hit count to display")
@click.option("--source-only", is_flag=True, help="Show source nodes only")
@click.option("--dest-only", is_flag=True, help="Show destination nodes only")
@click.option("--source-dest-only", is_flag=True,
              help="Show only src↔dst pairs (suppress bare source/dest entries)")
@click.option("--all-matches", is_flag=True,
              help="Report every occurrence (default: deduplicate per file)")
@click.option("--output", default="table", type=click.Choice(["table", "json"]))
@click.option("--config", default=None)
def diag_cmd(
    files: tuple[str, ...],
    testset: Optional[str],
    ident: Optional[str],
    cbenchtest: Optional[str],
    filter_names: Optional[str],
    threshold: int,
    source_only: bool,
    dest_only: bool,
    source_dest_only: bool,
    all_matches: bool,
    output: str,
    config: Optional[str],
) -> None:
    """Apply parse filters to output files and report aggregated errors."""
    from cbench.config import load_config
    cfg = load_config(config)
    cbenchtest = cbenchtest or os.environ.get("CBENCHTEST", ".")

    # Build filter set
    if filter_names:
        names = [n.strip() for n in filter_names.split(",") if n.strip()]
    else:
        names = [n for n in cfg.parse_filter_include if n in FILTER_MODULES]
    if not names:
        names = FILTER_MODULES
    active_filters = build_filter_set(names)

    # Collect files to scan
    paths: list[Path] = [Path(f) for f in files]

    if testset:
        ident = ident or f"{cfg.cluster_name}1"
        base = Path(cbenchtest).resolve()
        ident_dir = (base / testset / ident).resolve()
        if not str(ident_dir).startswith(str(base)):
            raise click.UsageError(
                f"Path traversal detected: testset/ident escapes CBENCHTEST"
            )
        if not ident_dir.exists():
            console.print(f"[red]Directory not found: {ident_dir}[/red]")
            raise SystemExit(1)
        for job_dir in sorted(ident_dir.iterdir()):
            if not job_dir.is_dir():
                continue
            paths += list(job_dir.glob("*.o*")) + list(job_dir.glob("slurm-*.out"))

    if not paths:
        console.print("[yellow]No files to scan.[/yellow]")
        raise SystemExit(0)

    # Scan all files
    # Aggregation structure:
    #   counts[error_type][key] = int
    # where key is one of:  "SOURCE:node", "DEST:node", "SOURCE::node<->DEST::node"
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    raw_hits: list[dict] = []

    seen: set[tuple[str, str]] = set()  # (filename, error_type) for dedup

    for path in paths:
        for fname, error_type, src, dst in _scan_file(path, active_filters):
            dedup_key = (fname, error_type)
            if not all_matches and dedup_key in seen:
                continue
            seen.add(dedup_key)

            raw_hits.append({"file": fname, "error": error_type, "src": src, "dst": dst})

            if src:
                counts[error_type][f"SOURCE:{src}"] += 1
            if dst:
                counts[error_type][f"DEST:{dst}"] += 1
            if src and dst:
                counts[error_type][f"SOURCE::{src}<->DEST::{dst}"] += 1
            if not src and not dst:
                counts[error_type][fname] += 1

    if not counts:
        console.print("[green]No filter matches found.[/green]")
        return

    if output == "json":
        result = []
        for error_type, nodes in sorted(counts.items()):
            entry: dict = {"error_type": error_type, "hits": []}
            for key, cnt in sorted(nodes.items()):
                if cnt < threshold:
                    continue
                if source_only and "DEST:" in key and "SOURCE::" not in key:
                    continue
                if dest_only and "SOURCE:" in key and "SOURCE::" not in key:
                    continue
                if source_dest_only and "SOURCE::" not in key:
                    continue
                entry["hits"].append({"node": key, "count": cnt})
            if entry["hits"]:
                result.append(entry)
        console.print(json.dumps(result, indent=2))
        return

    # Table output
    for error_type, nodes in sorted(counts.items()):
        console.print(f"\n[bold red]{error_type}[/bold red]")
        tbl = Table(show_header=True, box=None, padding=(0, 2))
        tbl.add_column("Node / Pair")
        tbl.add_column("Count", justify="right")

        any_rows = False
        for key, cnt in sorted(nodes.items()):
            if cnt < threshold:
                continue
            if source_only and "DEST:" in key and "SOURCE::" not in key:
                continue
            if dest_only and "SOURCE:" in key and "SOURCE::" not in key:
                continue
            if source_dest_only and "SOURCE::" not in key:
                continue
            tbl.add_row(f"[blue]{key}[/blue]", f"[yellow]{cnt}[/yellow]")
            any_rows = True

        if any_rows:
            console.print(tbl)
