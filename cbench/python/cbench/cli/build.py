"""cbench build — fetch and compile HPC benchmarks.

Usage:
  cbench build list
  cbench build <name> [options]
  cbench build all [options]
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

console = Console()


# ---------------------------------------------------------------------------
# Build lock — tracks what's already been built
# ---------------------------------------------------------------------------

class BuildLock:
    """Persistent JSON file recording successful builds.

    Format::

        {
          "<name>": {
            "source_url": "https://...",
            "config_hash": "<sha256 hex>",
            "built_at": "2025-06-14T12:00:00+00:00",
            "binaries": ["bin1", "bin2"]
          }
        }
    """

    def __init__(self, prefix: Path) -> None:
        self.path = prefix / "build.lock"
        self._lock = threading.Lock()
        self._data: dict = {}
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text())
            except (json.JSONDecodeError, OSError):
                self._data = {}

    @staticmethod
    def _config_hash(cfg) -> str:
        """SHA-256 of the build-affecting config fields."""
        key = json.dumps({
            "cc": cfg.cc, "cxx": cfg.cxx, "fc": cfg.fc,
            "mpicc": cfg.mpicc, "mpicxx": cfg.mpicxx, "mpif90": cfg.mpif90,
            "cflags": cfg.cflags, "fflags": cfg.fflags,
            "blas_lib": cfg.blas_lib, "blas_inc": cfg.blas_inc,
            "extra": cfg.extra,
        }, sort_keys=True)
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def is_cached(self, name: str, source_url: str, cfg, prefix_bin: Path) -> bool:
        """Return True if this benchmark is up-to-date and all binaries exist."""
        entry = self._data.get(name)
        if not entry:
            return False
        if entry.get("source_url") != source_url:
            return False
        if entry.get("config_hash") != self._config_hash(cfg):
            return False
        binaries = entry.get("binaries", [])
        if not binaries:
            return False
        return all((prefix_bin / b).exists() for b in binaries)

    def record(self, name: str, source_url: str, cfg, binaries: list[str]) -> None:
        """Write a successful build entry and flush to disk (thread-safe)."""
        with self._lock:
            self._data[name] = {
                "source_url": source_url,
                "config_hash": self._config_hash(cfg),
                "built_at": datetime.now(timezone.utc).isoformat(),
                "binaries": binaries,
            }
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._data, indent=2))

    def remove(self, name: str) -> None:
        """Remove a stale entry (called before a forced rebuild, thread-safe)."""
        with self._lock:
            self._data.pop(name, None)
            if self.path.exists():
                self.path.write_text(json.dumps(self._data, indent=2))


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
@click.option("--prefix", default=None, help="Install prefix to check for cached builds")
def build_list(prefix: Optional[str]) -> None:
    """List available benchmark builders and their cache status."""
    from cbench.builders import REGISTRY

    prefix_p = Path(prefix or _default_prefix())
    lock = BuildLock(prefix_p)

    tbl = Table(show_header=True, box=None, padding=(0, 2))
    tbl.add_column("Name", style="bold cyan")
    tbl.add_column("Cached", justify="center")
    tbl.add_column("Description")

    for name, cls in sorted(REGISTRY.items()):
        entry = lock._data.get(name)
        if entry:
            built_at = entry.get("built_at", "")[:10]  # date only
            cached_str = f"[green]yes ({built_at})[/green]"
        else:
            cached_str = "[dim]no[/dim]"
        tbl.add_row(name, cached_str, cls.description)

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


def _run_one(
    name: str,
    prefix: Path,
    srcdir: Path,
    cfg,
    *,
    force: bool,
    dry_run: bool,
    lock: "BuildLock | None" = None,
) -> bool:
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

    source_url = builder.source_url
    prefix_bin = prefix / "bin"

    # Cache hit — skip fetch+build unless --force
    if lock and not force and not dry_run:
        if lock.is_cached(name, source_url, cfg, prefix_bin):
            console.print(
                f"[dim]{name}: already built and up-to-date (use --force to rebuild)[/dim]"
            )
            return True

    if force and lock:
        lock.remove(name)

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
            if lock and not dry_run:
                lock.record(name, source_url, cfg, installed)

        return True

    except RuntimeError as exc:
        console.print(f"[red]Build failed:[/red] {exc}")
        return False
    except Exception as exc:
        console.print(f"[red]Unexpected error:[/red] {exc}")
        return False


# ---------------------------------------------------------------------------
# build check
# ---------------------------------------------------------------------------

@build_group.command("check")
@click.argument("benchmark", required=False, default=None)
@click.option("--prefix", default=None, help="Install prefix to search for binaries")
@click.option("--timeout", default=10, show_default=True, type=int,
              help="Seconds to wait per binary invocation")
def build_check(benchmark: Optional[str], prefix: Optional[str], timeout: int) -> None:
    """Verify installed benchmark binaries are present and runnable."""
    from cbench.builders import REGISTRY

    prefix_p = Path(prefix or _default_prefix())
    lock = BuildLock(prefix_p)
    prefix_bin = prefix_p / "bin"

    names = [benchmark] if benchmark else sorted(REGISTRY)

    tbl = Table(show_header=True, box=None, padding=(0, 2))
    tbl.add_column("Name", style="bold cyan")
    tbl.add_column("Binary")
    tbl.add_column("Status", justify="center")
    tbl.add_column("Detail", style="dim")

    any_fail = False
    for name in names:
        entry = lock._data.get(name)
        if not entry:
            tbl.add_row(name, "—", "[yellow]not built[/yellow]", "no cache entry")
            continue
        binaries = entry.get("binaries", [])
        if not binaries:
            tbl.add_row(name, "—", "[yellow]not built[/yellow]", "no binaries recorded")
            continue
        for binary in binaries:
            bin_path = prefix_bin / binary
            if not bin_path.exists():
                tbl.add_row(name, binary, "[red]MISSING[/red]", str(bin_path))
                any_fail = True
                continue
            try:
                proc = subprocess.run(
                    [str(bin_path), "--version"],
                    capture_output=True,
                    timeout=timeout,
                )
                # Negative returncode means killed by signal (e.g. SIGSEGV=-11)
                if proc.returncode < 0:
                    tbl.add_row(name, binary, "[red]CRASHED[/red]",
                                f"signal {-proc.returncode}")
                    any_fail = True
                else:
                    out = (proc.stdout or proc.stderr or b"").decode(errors="replace")
                    detail = out.strip().splitlines()[0][:80] if out.strip() else f"exit {proc.returncode}"
                    tbl.add_row(name, binary, "[green]OK[/green]", detail)
            except subprocess.TimeoutExpired:
                tbl.add_row(name, binary, "[green]OK[/green]", "running (no --version)")
            except OSError as exc:
                tbl.add_row(name, binary, "[red]ERROR[/red]", str(exc))
                any_fail = True

    console.print(tbl)
    if any_fail:
        sys.exit(1)


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
    lock = BuildLock(prefix_p) if not kwargs["dry_run"] else None
    ok = _run_one(benchmark, prefix_p, srcdir_p, cfg,
                  force=kwargs["force"], dry_run=kwargs["dry_run"], lock=lock)
    if not ok:
        sys.exit(1)


# ---------------------------------------------------------------------------
# build all
# ---------------------------------------------------------------------------

@build_group.command("all")
@_build_options
@click.option("--parallel", default=1, show_default=True, type=int,
              help="Number of benchmarks to build concurrently")
def build_all(prefix, srcdir, parallel: int, **kwargs) -> None:
    """Fetch and build all available benchmarks."""
    from cbench.builders import REGISTRY

    cfg = _make_cfg(kwargs)
    prefix_p, srcdir_p = _resolve_dirs(prefix, srcdir)
    force = kwargs["force"]
    dry_run = kwargs["dry_run"]
    lock = BuildLock(prefix_p) if not dry_run else None

    names = sorted(REGISTRY)
    results: dict[str, bool] = {}

    if parallel <= 1:
        for name in names:
            results[name] = _run_one(name, prefix_p, srcdir_p, cfg,
                                     force=force, dry_run=dry_run, lock=lock)
    else:
        console.print(f"[cyan]Building {len(names)} benchmarks with {parallel} workers...[/cyan]")
        with ThreadPoolExecutor(max_workers=parallel) as pool:
            futures = {
                pool.submit(_run_one, name, prefix_p, srcdir_p, cfg,
                            force=force, dry_run=dry_run, lock=lock): name
                for name in names
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    results[name] = future.result()
                except Exception as exc:
                    console.print(f"[red]{name}: unexpected error:[/red] {exc}")
                    results[name] = False

    console.rule("[bold]Summary[/bold]")
    for name, ok in sorted(results.items()):
        status = "[green]OK[/green]" if ok else "[red]FAILED[/red]"
        console.print(f"  {status}  {name}")

    if not all(results.values()):
        sys.exit(1)
