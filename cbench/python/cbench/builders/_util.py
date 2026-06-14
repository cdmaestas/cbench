"""Shared helpers for benchmark builders."""

from __future__ import annotations

import shlex
import shutil
import subprocess
import tarfile
import urllib.request
from pathlib import Path

from rich.console import Console

console = Console()


def _display(cmd: list[str]) -> str:
    return " ".join(shlex.quote(a) for a in cmd)


def run(cmd: list[str], *, cwd: Path, dry_run: bool, env: dict | None = None) -> None:
    """Run a command, printing it first.  Raises RuntimeError on failure."""
    console.print(f"  [dim]$ {_display(cmd)}[/dim]")
    if dry_run:
        return
    result = subprocess.run(cmd, cwd=cwd, env=env)
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed (exit {result.returncode}): {_display(cmd)}"
        )


def require(*tools: str) -> list[str]:
    """Return names of tools not found on PATH."""
    return [t for t in tools if not shutil.which(t)]


def git_clone(url: str, dest: Path, *, force: bool, dry_run: bool) -> None:
    """Clone *url* into *dest*, skipping if already present (unless force)."""
    if dest.exists() and not force:
        console.print(f"  [green]Already cloned:[/green] {dest}")
        return
    if dest.exists() and force:
        console.print(f"  [yellow]Removing existing source:[/yellow] {dest}")
        if not dry_run:
            shutil.rmtree(dest)
    console.print(f"  [cyan]git clone[/cyan] {url}")
    run(["git", "clone", "--depth=1", url, str(dest)], cwd=dest.parent, dry_run=dry_run)


def wget_tarball(url: str, dest_dir: Path, *, force: bool, dry_run: bool) -> Path:
    """Download a tarball to *dest_dir* and extract it.

    Returns the path of the top-level directory inside the tarball.
    Skips the download if the tarball already exists and not force.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = url.split("/")[-1]
    tarball = dest_dir / filename

    if not tarball.exists() or force:
        console.print(f"  [cyan]wget[/cyan] {url}")
        if not dry_run:
            urllib.request.urlretrieve(url, tarball)
    else:
        console.print(f"  [green]Already downloaded:[/green] {tarball}")

    if dry_run:
        # Return a plausible guess at the extracted dir name
        stem = filename
        for ext in (".tar.gz", ".tgz", ".tar.bz2", ".tar.xz"):
            if stem.endswith(ext):
                stem = stem[: -len(ext)]
        return dest_dir / stem

    with tarfile.open(tarball) as tf:
        top = Path(tf.getnames()[0].split("/")[0])
        console.print(f"  [cyan]tar x[/cyan] {tarball.name}")
        tf.extractall(dest_dir)

    return dest_dir / top


def install_bins(src_dir: Path, prefix_bin: Path, names: list[str], *, dry_run: bool) -> list[str]:
    """Copy named binaries from *src_dir* to *prefix_bin*."""
    prefix_bin.mkdir(parents=True, exist_ok=True)
    installed = []
    for name in names:
        src = src_dir / name
        if not src.exists():
            console.print(f"  [yellow]Warning: binary not found after build: {src}[/yellow]")
            continue
        dst = prefix_bin / name
        console.print(f"  [green]install[/green] {dst}")
        if not dry_run:
            shutil.copy2(src, dst)
            dst.chmod(0o755)
        installed.append(name)
    return installed
