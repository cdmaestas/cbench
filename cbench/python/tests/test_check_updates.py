"""`cbench build check-updates` (backlog #11b): report newer upstream versions
of benchmark sources without downloading them (cbench.upstream)."""
from __future__ import annotations

import re
import shutil
import subprocess

import pytest
from click.testing import CliRunner

from cbench import upstream
from cbench.builders import REGISTRY
from cbench.cli.main import cli

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


# ---------------------------------------------------------------------------
# versions and tags
# ---------------------------------------------------------------------------

def test_version_ordering():
    ordered = ["1.03e", "1.90b", "1.91", "2.00", "2.00a"]
    shuffled = ["2.00", "1.91", "2.00a", "1.03e", "1.90b"]
    assert sorted(shuffled, key=upstream.version_key) == ordered
    assert upstream.version_key("3_511") > upstream.version_key("3_506")
    assert upstream.version_key("3.4.4") > upstream.version_key("3.4.2")
    assert upstream.version_key("7.5.2") > upstream.version_key("7.3")
    assert upstream.newest([]) is None


@pytest.mark.parametrize(("tags", "expect"), [
    (["fio-3.41", "fio-3.43", "fio-3.42"], "fio-3.43"),
    (["4.0.0rc1", "3.3.0", "4.0.0", "4.1.0rc2"], "4.0.0"),        # pre-releases skipped
    (["io500-isc20", "io500-sc23", "1.2"], "1.2"),                 # "500" is not a version
    (["IMB-v2021.3", "IMB-v2021.11", "IMB-v2019.6"], "IMB-v2021.11"),
    (["io500-isc20", "latest"], None),
    ([], None),
])
def test_latest_tag(tags, expect):
    assert upstream.latest_tag(tags) == expect


# ---------------------------------------------------------------------------
# pinned tarballs
# ---------------------------------------------------------------------------

_PAT = r"NPB(?P<v>\d+(?:\.\d+)+)\.tar\.gz"
_URL = "https://www.nas.nasa.gov/assets/npb/NPB3.4.2.tar.gz"


def test_tarball_update_available(monkeypatch):
    monkeypatch.setattr(upstream, "fetch_page",
                        lambda url: '<a href="NPB3.4.4.tar.gz"> <a href="NPB3.4.2.tar.gz"> NPB3.3.1.tar.gz')
    c = upstream.check_tarball("npb", _URL, "https://example.org/npb", _PAT)
    assert (c.current, c.latest, c.status) == ("3.4.2", "3.4.4", upstream.UPDATE)
    assert "pinned in cbench/builders/npb.py" in c.detail


def test_tarball_up_to_date(monkeypatch):
    monkeypatch.setattr(upstream, "fetch_page", lambda url: "NPB3.4.2.tar.gz NPB3.3.1.tar.gz")
    c = upstream.check_tarball("npb", _URL, "https://example.org/npb", _PAT)
    assert (c.latest, c.status) == ("3.4.2", upstream.UP_TO_DATE)


def test_tarball_lookup_failures_are_reported(monkeypatch):
    def boom(url):
        raise OSError("Name or service not known")
    monkeypatch.setattr(upstream, "fetch_page", boom)
    c = upstream.check_tarball("npb", _URL, "https://example.org/npb", _PAT)
    assert c.status == upstream.FAILED and "Name or service not known" in c.detail
    monkeypatch.setattr(upstream, "fetch_page", lambda url: "<html>moved</html>")
    c = upstream.check_tarball("npb", _URL, "https://example.org/npb", _PAT)
    assert c.status == upstream.FAILED and "page changed?" in c.detail


def test_fetch_page_refuses_non_https():
    with pytest.raises(RuntimeError, match="non-https"):
        upstream.fetch_page("http://example.org/")


@pytest.mark.parametrize("name", ["bonnie", "hpl", "iozone", "npb", "osu"])
def test_every_pinned_tarball_parses_its_own_url(name):
    b = REGISTRY[name]
    assert b.latest_page.startswith("https://")
    m = re.search(b.latest_pattern, b.source_url.rsplit("/", 1)[-1])
    assert m and m.group("v"), f"{name}: latest_pattern doesn't match its pinned source_url"


def test_unversioned_sources_are_skipped_with_a_reason(tmp_path):
    for name in ("stream", "gpfsperf"):
        c = upstream.check_builder(REGISTRY[name](), tmp_path)
        assert c.status == upstream.SKIPPED and c.detail


# ---------------------------------------------------------------------------
# git sources (real local repositories, no network)
# ---------------------------------------------------------------------------

def _git(*args, cwd=None):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repos(tmp_path):
    work = tmp_path / "work"
    _git("init", "-q", "-b", "main", str(work))
    for cfg in (("user.email", "t@example.org"), ("user.name", "t")):
        _git("config", *cfg, cwd=work)
    (work / "f").write_text("1\n")
    _git("add", "f", cwd=work)
    _git("commit", "-q", "-m", "one", cwd=work)
    _git("tag", "v1.0", cwd=work)
    _git("tag", "v1.1rc1", cwd=work)
    upstream_url = str(tmp_path / "upstream.git")
    _git("clone", "-q", "--bare", str(work), upstream_url)
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    return work, upstream_url, srcdir


@needs_git
def test_git_not_built_here(repos):
    _work, url, srcdir = repos
    c = upstream.check_git("x", url, srcdir)
    assert c.status == upstream.NOT_HERE and c.current == "-" and "latest release tag v1.0" in c.detail


@needs_git
def test_git_up_to_date_then_update_available(repos):
    work, url, srcdir = repos
    _git("clone", "-q", "--depth=1", f"file://{url}", str(srcdir / "x"))
    _git("remote", "set-url", "origin", url, cwd=srcdir / "x")   # as the builders record it
    c = upstream.check_git("x", url, srcdir)
    assert c.status == upstream.UP_TO_DATE and c.current == c.latest
    (work / "f").write_text("2\n")
    _git("commit", "-q", "-am", "two", cwd=work)
    _git("push", "-q", url, "main", cwd=work)
    c = upstream.check_git("x", url, srcdir)
    assert c.status == upstream.UPDATE and c.current != c.latest
    assert "`cbench build update x`" in c.detail


@needs_git
def test_git_unreachable_remote_is_reported(tmp_path):
    c = upstream.check_git("x", str(tmp_path / "missing.git"), tmp_path)
    assert c.status == upstream.FAILED and c.detail


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_cli_table_and_summary(tmp_path, monkeypatch):
    from cbench.cli import build as build_mod
    monkeypatch.setattr(build_mod.console, "width", 250)
    fake = {"npb": upstream.Check("npb", "tarball", "3.4.2", "3.4.4", upstream.UPDATE, "pinned"),
            "hpl": upstream.Check("hpl", "tarball", "2.3", "2.3", upstream.UP_TO_DATE)}
    monkeypatch.setattr(upstream, "check_builder", lambda b, src: fake[b.name])
    res = CliRunner().invoke(cli, ["build", "check-updates", "npb", "hpl",
                                   "--prefix", str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert re.search(r"npb\s+tarball\s+3\.4\.2\s+3\.4\.4\s+update available", res.output)
    assert re.search(r"hpl\s+tarball\s+2\.3\s+2\.3\s+up to date", res.output)
    assert "1 update(s) available" in res.output


def test_cli_unknown_builder(tmp_path):
    res = CliRunner().invoke(cli, ["build", "check-updates", "nosuch", "--prefix", str(tmp_path)])
    assert res.exit_code != 0 and "unknown builder(s): nosuch" in res.output
