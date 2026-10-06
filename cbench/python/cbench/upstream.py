"""Check benchmark sources for newer upstream versions (`cbench build check-updates`).

Report only: nothing is downloaded or rebuilt. Moving a pinned tarball to a new
version stays a code change (and a PR), so it gets tested first; git sources
are updated with `cbench build update`.

* git builders (``source_url`` is a git repo): ``git ls-remote`` gives the
  remote HEAD and the release tags. The HEAD is compared with the local clone
  under the source dir (found by its ``origin`` URL), and the newest release
  tag is shown too, since the builders clone the branch head rather than a
  release.
* pinned tarballs (builders with ``latest_page`` and ``latest_pattern``): the
  project's download page is read and the newest version matching the
  pattern is compared with the version in ``source_url``.
* anything else (a single source file, sources shipped with GPFS) is listed
  as not checked, with the reason.

A failed lookup (no network, a changed page) is reported, never fatal.
"""

from __future__ import annotations

import re
import subprocess
import urllib.request
from dataclasses import dataclass
from pathlib import Path

TIMEOUT = 20
_PRERELEASE = re.compile(r"(rc|alpha|beta|pre|dev|test)\d*", re.IGNORECASE)
#: a release tag's version: dotted (or underscored) numbers at the END of the
#: tag ("fio-3.43", "IMB-v2021.11", "4.0.0"); a lone number is not enough, so
#: "io500-isc20" or the "500" in "io500" are not taken for versions
_TAG_VERSION = re.compile(r"\d+(?:[._]\d+)+[a-z]?$")

UP_TO_DATE = "up to date"
UPDATE = "update available"
NOT_HERE = "not built here"
FAILED = "couldn't check"
SKIPPED = "not checked"


@dataclass
class Check:
    name: str
    kind: str            # "git", "tarball", or "-"
    current: str         # local commit / pinned version / "-"
    latest: str          # remote commit / newest version / "-"
    status: str
    detail: str = ""


def version_key(version: str) -> tuple:
    """Natural sort key: '1.90b' < '1.91' < '2.00' < '2.00a'; '3_511' > '3_506'."""
    parts = re.findall(r"\d+|[a-z]+", version.lower())
    return tuple((1, int(p)) if p.isdigit() else (0, p) for p in parts)


def newest(versions: list[str]) -> str | None:
    return max(versions, key=version_key) if versions else None


# ---------------------------------------------------------------------------
# network / git (thin wrappers, patched in tests)
# ---------------------------------------------------------------------------

def fetch_page(url: str) -> str:
    if not url.startswith("https://"):
        raise RuntimeError(f"refusing non-https URL {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "cbench-check-updates"})  # noqa: S310 — https enforced above
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # noqa: S310 # nosec B310 — https enforced above
        return resp.read().decode("utf-8", errors="replace")


def git(*args: str, cwd: Path | None = None) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          timeout=TIMEOUT, check=False)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr.strip() or f"git {args[0]} failed").splitlines()[-1])
    return proc.stdout


# ---------------------------------------------------------------------------
# git sources
# ---------------------------------------------------------------------------

def _norm(url: str) -> str:
    return url.rstrip("/").removesuffix(".git").lower()


def local_clone(url: str, srcdir: Path) -> Path | None:
    """The clone of ``url`` under ``srcdir`` (one or two levels down)."""
    for gitdir in [*srcdir.glob("*/.git"), *srcdir.glob("*/*/.git")]:
        repo = gitdir.parent
        try:
            if _norm(git("remote", "get-url", "origin", cwd=repo).strip()) == _norm(url):
                return repo
        except (RuntimeError, OSError, subprocess.TimeoutExpired):
            continue
    return None


def latest_tag(tag_names: list[str]) -> str | None:
    """Newest release tag: tags carrying a version, pre-releases excluded."""
    releases = [t for t in tag_names if _TAG_VERSION.search(t) and not _PRERELEASE.search(t)]
    return max(releases, key=lambda t: version_key(_TAG_VERSION.search(t).group(0)),
               default=None)


def check_git(name: str, url: str, srcdir: Path) -> Check:
    try:
        heads = git("ls-remote", url, "HEAD").split()
        remote = heads[0] if heads else ""
        tags = [line.split("refs/tags/", 1)[1]
                for line in git("ls-remote", "--tags", "--refs", url).splitlines()
                if "refs/tags/" in line]
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        return Check(name, "git", "-", "-", FAILED, str(exc))
    tag = latest_tag(tags)
    detail = f"latest release tag {tag}" if tag else "no release tags"
    repo = local_clone(url, srcdir)
    if repo is None:
        return Check(name, "git", "-", remote[:10], NOT_HERE, detail)
    try:
        local = git("rev-parse", "HEAD", cwd=repo).strip()
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as exc:
        return Check(name, "git", "-", remote[:10], FAILED, f"{repo}: {exc}")
    if local == remote:
        return Check(name, "git", local[:10], remote[:10], UP_TO_DATE, detail)
    return Check(name, "git", local[:10], remote[:10], UPDATE,
                 f"{detail}; `cbench build update {name}` pulls the branch head")


# ---------------------------------------------------------------------------
# pinned tarballs
# ---------------------------------------------------------------------------

def check_tarball(name: str, url: str, page: str, pattern: str) -> Check:
    rx = re.compile(pattern)
    m = rx.search(url.rsplit("/", 1)[-1])
    pinned = m.group("v") if m else "?"
    try:
        found = [m.group("v") for m in rx.finditer(fetch_page(page))]
    except Exception as exc:  # noqa: BLE001 — any network/HTTP error is reported, not fatal
        return Check(name, "tarball", pinned, "-", FAILED, f"{page}: {exc}")
    latest = newest(found)
    if latest is None:
        return Check(name, "tarball", pinned, "-", FAILED,
                     f"no versions found on {page} (page changed?)")
    if version_key(latest) > version_key(pinned):
        return Check(name, "tarball", pinned, latest, UPDATE,
                     f"pinned in cbench/builders/{name}.py; listed on {page}")
    return Check(name, "tarball", pinned, latest, UP_TO_DATE, "")


def is_git(url: str) -> bool:
    return url.endswith(".git")


def check_builder(builder, srcdir: Path) -> Check:
    name, url = builder.name, builder.source_url
    if getattr(builder, "latest_page", "") and getattr(builder, "latest_pattern", ""):
        return check_tarball(name, url, builder.latest_page, builder.latest_pattern)
    if is_git(url):
        return check_git(name, url, srcdir)
    reason = getattr(builder, "update_note", "") or "no version listing to compare"
    return Check(name, "-", "-", "-", SKIPPED, reason)
