"""cbench build — fetch and compile HPC benchmarks.

Usage:
  cbench build list
  cbench build <name> [options]
  cbench build all [options]
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

console = Console()


def _default_prefix() -> str:
    return os.environ.get("CBENCHTEST", ".")


def _default_srcdir(prefix: str) -> str:
    return str(Path(prefix) / "src")


# ---------------------------------------------------------------------------
# build group
# ---------------------------------------------------------------------------

@click.group("build")
def build_group() -> None:
    """Fetch and compile HPC benchmark software."""


# ---------------------------------------------------------------------------
# build list
# ---------------------------------------------------------------------------

@build_group.command("list")
def build_list() -> None:
    """List available benchmark builders."""
    from cbench.builders import REGISTRY

    tbl = Table(show_header=True, box=None, padding=(0, 2))
    tbl.add_column("Name", style="bold cyan")
    tbl.add_column("Description")

    for name, cls in sorted(REGISTRY.items()):
        tbl.add_row(name, cls.description)

    console.print(tbl)


# ---------------------------------------------------------------------------
# shared options factory
# ---------------------------------------------------------------------------

def _build_options(f):
    """Decorator that attaches shared build options to a command."""
    decorators = [
        click.option("--prefix", default=None,
                     help="Install prefix (default: $CBENCHTEST or .)"),
        click.option("--srcdir", default=None,
                     help="Source download directory (default: <prefix>/src)"),
        click.option("--cc", default="cc", show_default=True),
        click.option("--cxx", default="c++", show_default=True),
        click.option("--fc", default="gfortran", show_default=True),
        click.option("--mpicc", default="mpicc", show_default=True),
        click.option("--mpicxx", default="mpicxx", show_default=True),
        click.option("--mpif90", default="mpif90", show_default=True),
        click.option("--cflags", default="-O3", show_default=True),
        click.option("--fflags", default="-O3", show_default=True),
        click.option("--jobs", default=4, show_default=True, type=int,
                     help="Parallel make jobs"),
        click.option("--blas-lib", default="",
                     help="BLAS link flags (required for hpl/hpcc), e.g. -lopenblas"),
        click.option("--blas-inc", default="",
                     help="BLAS include directory (optional)"),
        click.option("--extra", default=None, multiple=True,
                     help="Builder-specific KEY=VALUE pairs (repeatable)"),
        click.option("--force", is_flag=True,
                     help="Re-download and rebuild even if already present"),
        click.option("--dry-run", is_flag=True,
                     help="Print commands without executing"),
    ]
    for d in reversed(decorators):
        f = d(f)
    return f


def _make_cfg(kwargs: dict):
    from cbench.builders import BuildConfig
    extra: dict = {}
    for kv in (kwargs.get("extra") or []):
        if "=" in kv:
            k, v = kv.split("=", 1)
            extra[k.strip()] = v.strip()
        else:
            extra[kv.strip()] = True
    return BuildConfig(
        cc=kwargs["cc"],
        cxx=kwargs["cxx"],
        fc=kwargs["fc"],
        mpicc=kwargs["mpicc"],
        mpicxx=kwargs["mpicxx"],
        mpif90=kwargs["mpif90"],
        cflags=kwargs["cflags"],
        fflags=kwargs["fflags"],
        jobs=kwargs["jobs"],
        blas_lib=kwargs["blas_lib"],
        blas_inc=kwargs["blas_inc"],
        extra=extra,
    )


def _resolve_dirs(prefix_opt: Optional[str], srcdir_opt: Optional[str]):
    prefix = Path(prefix_opt or _default_prefix())
    srcdir = Path(srcdir_opt or _default_srcdir(str(prefix)))
    return prefix, srcdir


def _run_one(name: str, prefix: Path, srcdir: Path, cfg, *, force: bool, dry_run: bool) -> bool:
    """Fetch + build one benchmark.  Returns True on success."""
    from cbench.builders import get_builder

    builder = get_builder(name)
    if builder is None:
        console.print(f"[red]Unknown benchmark:[/red] {name}")
        return False

    missing = builder.check_requires()
    if missing:
        console.print(
            f"[red]Missing prerequisites for {name}:[/red] {', '.join(missing)}\n"
            f"Install them and retry."
        )
        return False

    console.rule(f"[bold cyan]{name}[/bold cyan] — {builder.description}")

    try:
        console.print("[bold]Fetch[/bold]")
        src = builder.fetch(srcdir, force=force, dry_run=dry_run)

        console.print("[bold]Build[/bold]")
        installed = builder.build(src, prefix, cfg, dry_run=dry_run)

        if installed:
            console.print(
                f"\n[green]Installed {len(installed)} binary/binaries:[/green] "
                + ", ".join(installed)
            )
        return True

    except RuntimeError as exc:
        console.print(f"[red]Build failed:[/red] {exc}")
        return False
    except Exception as exc:
        console.print(f"[red]Unexpected error:[/red] {exc}")
        return False


# ---------------------------------------------------------------------------
# build <name>
# ---------------------------------------------------------------------------

@build_group.command("run")
@click.argument("benchmark")
@_build_options
def build_one(benchmark: str, prefix, srcdir, **kwargs) -> None:
    """Fetch and build a single benchmark by name."""
    cfg = _make_cfg(kwargs)
    prefix_p, srcdir_p = _resolve_dirs(prefix, srcdir)
    ok = _run_one(benchmark, prefix_p, srcdir_p, cfg,
                  force=kwargs["force"], dry_run=kwargs["dry_run"])
    if not ok:
        sys.exit(1)


# ---------------------------------------------------------------------------
# build all
# ---------------------------------------------------------------------------

@build_group.command("all")
@_build_options
def build_all(prefix, srcdir, **kwargs) -> None:
    """Fetch and build all available benchmarks."""
    from cbench.builders import REGISTRY

    cfg = _make_cfg(kwargs)
    prefix_p, srcdir_p = _resolve_dirs(prefix, srcdir)
    force = kwargs["force"]
    dry_run = kwargs["dry_run"]

    results: dict[str, bool] = {}
    for name in sorted(REGISTRY):
        results[name] = _run_one(name, prefix_p, srcdir_p, cfg,
                                 force=force, dry_run=dry_run)

    console.rule("[bold]Summary[/bold]")
    for name, ok in sorted(results.items()):
        status = "[green]OK[/green]" if ok else "[red]FAILED[/red]"
        console.print(f"  {status}  {name}")

    if not all(results.values()):
        sys.exit(1)
