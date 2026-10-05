"""Shared helpers for benchmark builders."""

from __future__ import annotations

import os
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

from rich.console import Console

#: Timeout (seconds) for benchmark source downloads.
DOWNLOAD_TIMEOUT = 120

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


def git_pull(dest: Path, *, dry_run: bool) -> bool:
    """Run `git pull` in *dest* and return True if HEAD changed.

    Returns False if *dest* is not a git repo or if --dry-run.
    """
    if dry_run:
        console.print(f"  [dim]DRYRUN: git pull in {dest}[/dim]")
        return False
    git_dir = dest / ".git"
    if not git_dir.exists():
        return False
    before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=dest, capture_output=True, text=True
    ).stdout.strip()
    console.print(f"  [cyan]git pull[/cyan] in {dest}")
    result = subprocess.run(["git", "pull", "--ff-only"], cwd=dest)
    if result.returncode != 0:
        raise RuntimeError(f"git pull --ff-only failed in {dest} (exit {result.returncode})")
    after = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=dest, capture_output=True, text=True
    ).stdout.strip()
    changed = before != after
    if changed:
        console.print(f"  [green]Updated:[/green] {before[:8]} → {after[:8]}")
    else:
        console.print("  [dim]Already up to date.[/dim]")
    return changed


def download(url: str, dest: Path) -> None:
    """Download *url* to *dest* with a timeout (urlretrieve has none)."""
    if not url.startswith("https://"):
        raise RuntimeError(f"Refusing non-https download URL: {url}")
    with urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT) as resp:  # noqa: S310 # nosec B310 — https enforced above
        with open(dest, "wb") as fh:
            shutil.copyfileobj(resp, fh)


def _rmtree_writable(path: Path) -> None:
    """rmtree that also removes read-only entries (some tarballs, e.g.
    iozone's, ship 0444 files and read-only directories)."""
    def _retry(func, p, _exc):
        os.chmod(os.path.dirname(p), stat.S_IRWXU)
        os.chmod(p, stat.S_IRWXU)
        func(p)
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_retry)
    else:  # onerror is deprecated from 3.12
        shutil.rmtree(path, onerror=_retry)


def wget_tarball(url: str, dest_dir: Path, *, force: bool, dry_run: bool) -> Path:
    """Download a tarball to *dest_dir* and extract it.

    Returns the path of the top-level directory inside the tarball.
    Skips the download if the tarball already exists and not force, and skips
    extraction if its top-level directory already exists and not force
    (re-extracting over a previous tree fails on read-only files). With force,
    the old tree is removed first.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = url.split("/")[-1]
    tarball = dest_dir / filename

    if not tarball.exists() or force:
        console.print(f"  [cyan]wget[/cyan] {url}")
        if not dry_run:
            download(url, tarball)
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
        # Validate every member stays inside dest_dir (prevents zip-slip).
        # is_relative_to (not str.startswith) so /a/b does not match /a/bc.
        # This runs BEFORE anything below touches the filesystem: a hostile
        # first member like "../../x" would otherwise make top_dir the parent.
        dest_resolved = dest_dir.resolve()
        for member in tf.getmembers():
            member_path = (dest_dir / member.name).resolve()
            if not member_path.is_relative_to(dest_resolved):
                raise RuntimeError(
                    f"Refusing to extract tarball: member {member.name!r} "
                    f"escapes destination directory"
                )
            if member.issym() or member.islnk():
                link_target = (member_path.parent / member.linkname).resolve()
                if not link_target.is_relative_to(dest_resolved):
                    raise RuntimeError(
                        f"Refusing to extract tarball: link member {member.name!r} "
                        f"targets {member.linkname!r} outside destination"
                    )
        top_dir = dest_dir / top
        top_resolved = top_dir.resolve()
        if top in (Path(), Path(), Path("..")) or top_resolved == dest_resolved \
                or not top_resolved.is_relative_to(dest_resolved):
            raise RuntimeError(f"Refusing to extract tarball: top-level entry {str(top)!r} "
                               "is not a directory inside the destination")
        if top_dir.exists():
            if not force:
                console.print(f"  [green]Already extracted:[/green] {top_dir}")
                return top_dir
            _rmtree_writable(top_dir)
        console.print(f"  [cyan]tar x[/cyan] {tarball.name}")
        # Python >= 3.12 (and 3.8.17/3.9.17+/3.10.12+/3.11.4+ backports, e.g.
        # RHEL 9's 3.9) has extraction filters; "data" adds the stdlib's own
        # checks on top of ours and silences the 3.12+ deprecation warning.
        if hasattr(tarfile, "data_filter"):
            tf.extractall(dest_dir, filter="data")  # noqa: S202 # nosec B202 — members validated above
        else:
            tf.extractall(dest_dir)  # noqa: S202 # nosec B202 — members validated above

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
            # Builders whose `make install` already lands in prefix/bin (ior,
            # fio) pass src_dir == prefix_bin; copying a file onto itself raises
            # SameFileError and would fail a successful build.
            if not (dst.exists() and src.resolve() == dst.resolve()):
                shutil.copy2(src, dst)
            dst.chmod(0o755)
        installed.append(name)
    return installed
