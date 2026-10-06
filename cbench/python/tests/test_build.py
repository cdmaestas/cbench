"""Tests for cbench build framework and CLI."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from cbench.builders import REGISTRY, get_builder, BuildConfig
from cbench.cli.main import cli


# ---------------------------------------------------------------------------
# Registry completeness
# ---------------------------------------------------------------------------

_EXPECTED_BUILDERS = [
    "stream", "imb", "osu", "ior", "hpl", "npb",
    "hpcc", "amg", "hpccg", "mpibench", "mpigraph", "bonnie", "graph500",
    "iozone", "fio", "gpfsperf", "io500",
]

@pytest.mark.parametrize("name", _EXPECTED_BUILDERS)
def test_builder_registered(name):
    assert name in REGISTRY, f"Builder '{name}' not registered"


@pytest.mark.parametrize("name", _EXPECTED_BUILDERS)
def test_builder_has_description(name):
    cls = REGISTRY[name]
    assert cls.description, f"Builder '{name}' missing description"


def test_get_builder_returns_instance():
    b = get_builder("stream")
    assert b is not None
    assert b.name == "stream"


def test_get_builder_unknown_returns_none():
    assert get_builder("no_such_benchmark") is None


# ---------------------------------------------------------------------------
# BuildConfig defaults
# ---------------------------------------------------------------------------

def test_build_config_defaults():
    cfg = BuildConfig()
    assert cfg.mpicc == "mpicc"
    assert cfg.jobs == 4
    assert cfg.blas_lib == ""


# ---------------------------------------------------------------------------
# check_requires
# ---------------------------------------------------------------------------

def test_check_requires_returns_list():
    for name in _EXPECTED_BUILDERS:
        b = get_builder(name)
        result = b.check_requires()
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# build list CLI
# ---------------------------------------------------------------------------

def test_build_list():
    runner = CliRunner()
    result = runner.invoke(cli, ["build", "list"])
    assert result.exit_code == 0
    for name in _EXPECTED_BUILDERS:
        assert name in result.output


# ---------------------------------------------------------------------------
# build run --dry-run (no network/disk access)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", _EXPECTED_BUILDERS)
def test_build_dry_run(tmp_path, name):
    runner = CliRunner()
    result = runner.invoke(cli, [
        "build", "run", name,
        "--prefix", str(tmp_path / "prefix"),
        "--srcdir", str(tmp_path / "src"),
        "--dry-run",
    ])
    # dry-run must not fail due to missing tools or network
    # it may fail if check_requires blocks it, but exit 0 or 1 is acceptable;
    # what matters is no unhandled exception (no traceback)
    assert "Traceback" not in (result.output or "")
    if result.exception and not isinstance(result.exception, SystemExit):
        raise result.exception


# ---------------------------------------------------------------------------
# build all --dry-run
# ---------------------------------------------------------------------------

def test_build_all_dry_run(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, [
        "build", "all",
        "--prefix", str(tmp_path / "prefix"),
        "--srcdir", str(tmp_path / "src"),
        "--dry-run",
    ])
    assert "Traceback" not in (result.output or "")
    assert "Summary" in result.output


# ---------------------------------------------------------------------------
# build run — unknown benchmark
# ---------------------------------------------------------------------------

def test_build_unknown(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, [
        "build", "run", "no_such_benchmark",
        "--prefix", str(tmp_path),
        "--dry-run",
    ])
    assert result.exit_code != 0
    assert "Unknown benchmark" in result.output


# ---------------------------------------------------------------------------
# _util helpers
# ---------------------------------------------------------------------------

def test_run_helper_dry_run(tmp_path):
    from cbench.builders._util import run
    # Should not execute the command
    run(["false"], cwd=tmp_path, dry_run=True)   # would fail if actually run


def test_run_helper_raises_on_failure(tmp_path):
    from cbench.builders._util import run
    with pytest.raises(RuntimeError, match="Command failed"):
        run(["false"], cwd=tmp_path, dry_run=False)


def test_require_finds_missing():
    from cbench.builders._util import require
    missing = require("this_tool_does_not_exist_abc123")
    assert "this_tool_does_not_exist_abc123" in missing


def test_require_finds_present():
    from cbench.builders._util import require
    missing = require("python3")
    assert "python3" not in missing


# ---------------------------------------------------------------------------
# install_bins helper
# ---------------------------------------------------------------------------

def test_install_bins_copies(tmp_path):
    from cbench.builders._util import install_bins
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "mybinary").write_text("#!/bin/sh\necho hi\n")
    (src_dir / "mybinary").chmod(0o755)

    dst_dir = tmp_path / "bin"
    installed = install_bins(src_dir, dst_dir, ["mybinary"], dry_run=False)
    assert installed == ["mybinary"]
    assert (dst_dir / "mybinary").exists()


def test_install_bins_missing_warns(tmp_path, capsys):
    from cbench.builders._util import install_bins
    installed = install_bins(tmp_path, tmp_path / "bin", ["ghost"], dry_run=False)
    assert installed == []


def test_install_bins_dry_run(tmp_path):
    from cbench.builders._util import install_bins
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "bin_a").write_text("x")
    installed = install_bins(src_dir, tmp_path / "bin", ["bin_a"], dry_run=True)
    # dry_run: returns list but does not create the destination dir
    assert "bin_a" in installed
    assert not (tmp_path / "bin" / "bin_a").exists()


# ---------------------------------------------------------------------------
# BuildLock
# ---------------------------------------------------------------------------

def test_wget_tarball_rejects_zip_slip(tmp_path):
    """wget_tarball must raise RuntimeError if a member escapes dest_dir."""
    import tarfile as tf_mod
    import io

    # Build a malicious tarball in memory with a traversal member
    buf = io.BytesIO()
    with tf_mod.open(fileobj=buf, mode="w:gz") as tf:
        info = tf_mod.TarInfo(name="../../evil.txt")
        data = b"pwned"
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
    buf.seek(0)

    tarball_path = tmp_path / "evil.tar.gz"
    tarball_path.write_bytes(buf.getvalue())

    dest = tmp_path / "dest"
    dest.mkdir()

    # Patch the download helper to skip the network and use our crafted tarball
    import cbench.builders._util as util_mod

    def fake_download(url, dest_file):
        import shutil
        shutil.copy(str(tarball_path), dest_file)

    from cbench.builders._util import wget_tarball
    with patch.object(util_mod, "download", side_effect=fake_download):
        import pytest as _pytest
        with _pytest.raises(RuntimeError, match="escapes destination"):
            wget_tarball("https://example.com/evil.tar.gz", dest, force=True, dry_run=False)


def test_download_rejects_non_https(tmp_path):
    from cbench.builders._util import download
    import pytest as _pytest
    with _pytest.raises(RuntimeError, match="non-https"):
        download("http://example.com/x.tar.gz", tmp_path / "never-written")


def test_wget_tarball_rejects_escaping_symlink(tmp_path):
    """A symlink member pointing outside dest_dir must be rejected."""
    import tarfile as tf_mod
    import io

    buf = io.BytesIO()
    with tf_mod.open(fileobj=buf, mode="w:gz") as tf:
        info = tf_mod.TarInfo(name="pkg/link")
        info.type = tf_mod.SYMTYPE
        info.linkname = "../../../etc/passwd"
        tf.addfile(info)
    buf.seek(0)

    tarball_path = tmp_path / "evil-link.tar.gz"
    tarball_path.write_bytes(buf.getvalue())
    dest = tmp_path / "dest"
    dest.mkdir()

    import cbench.builders._util as util_mod

    def fake_download(url, dest_file):
        import shutil
        shutil.copy(str(tarball_path), dest_file)

    from cbench.builders._util import wget_tarball
    with patch.object(util_mod, "download", side_effect=fake_download):
        import pytest as _pytest
        with _pytest.raises(RuntimeError, match="link member"):
            wget_tarball("https://example.com/evil-link.tar.gz", dest, force=True, dry_run=False)


def test_build_lock_initially_empty(tmp_path):
    from cbench.cli.build import BuildLock
    lock = BuildLock(tmp_path)
    assert not lock._data


def test_build_lock_record_and_hit(tmp_path):
    from cbench.cli.build import BuildLock
    from cbench.builders import BuildConfig
    cfg = BuildConfig()
    lock = BuildLock(tmp_path)
    prefix_bin = tmp_path / "bin"
    prefix_bin.mkdir()
    (prefix_bin / "mybin").write_text("x")

    lock.record("stream", "https://example.com/stream.c", cfg, ["mybin"])

    lock2 = BuildLock(tmp_path)  # reload from disk
    assert lock2.is_cached("stream", "https://example.com/stream.c", cfg, prefix_bin)


def test_build_lock_miss_wrong_url(tmp_path):
    from cbench.cli.build import BuildLock
    from cbench.builders import BuildConfig
    cfg = BuildConfig()
    lock = BuildLock(tmp_path)
    prefix_bin = tmp_path / "bin"
    prefix_bin.mkdir()
    (prefix_bin / "mybin").write_text("x")

    lock.record("stream", "https://example.com/stream.c", cfg, ["mybin"])
    assert not lock.is_cached("stream", "https://other.com/stream.c", cfg, prefix_bin)


def test_build_lock_miss_changed_config(tmp_path):
    from cbench.cli.build import BuildLock
    from cbench.builders import BuildConfig
    cfg1 = BuildConfig(mpicc="mpicc")
    cfg2 = BuildConfig(mpicc="mpiicc")
    lock = BuildLock(tmp_path)
    prefix_bin = tmp_path / "bin"
    prefix_bin.mkdir()
    (prefix_bin / "mybin").write_text("x")

    lock.record("imb", "https://github.com/intel/mpi-benchmarks.git", cfg1, ["mybin"])
    assert not lock.is_cached("imb", "https://github.com/intel/mpi-benchmarks.git", cfg2, prefix_bin)


def test_build_lock_miss_missing_binary(tmp_path):
    from cbench.cli.build import BuildLock
    from cbench.builders import BuildConfig
    cfg = BuildConfig()
    lock = BuildLock(tmp_path)
    prefix_bin = tmp_path / "bin"
    prefix_bin.mkdir()

    lock.record("stream", "https://example.com/stream.c", cfg, ["mybin"])
    # mybin does not exist on disk
    assert not lock.is_cached("stream", "https://example.com/stream.c", cfg, prefix_bin)


def test_build_lock_remove(tmp_path):
    from cbench.cli.build import BuildLock
    from cbench.builders import BuildConfig
    cfg = BuildConfig()
    lock = BuildLock(tmp_path)
    prefix_bin = tmp_path / "bin"
    prefix_bin.mkdir()
    (prefix_bin / "mybin").write_text("x")

    lock.record("stream", "https://example.com/stream.c", cfg, ["mybin"])
    lock.remove("stream")
    assert "stream" not in lock._data


def test_build_lock_persists_across_instances(tmp_path):
    from cbench.cli.build import BuildLock
    from cbench.builders import BuildConfig
    cfg = BuildConfig()
    prefix_bin = tmp_path / "bin"
    prefix_bin.mkdir()
    (prefix_bin / "b1").write_text("x")
    (prefix_bin / "b2").write_text("x")

    BuildLock(tmp_path).record("ior", "https://github.com/hpc/ior.git", cfg, ["b1", "b2"])

    lock2 = BuildLock(tmp_path)
    assert lock2.is_cached("ior", "https://github.com/hpc/ior.git", cfg, prefix_bin)


def test_builder_has_source_url():
    from cbench.builders import REGISTRY
    for name, cls in REGISTRY.items():
        assert cls.source_url, f"Builder '{name}' missing source_url"


def test_build_list_shows_cache_column(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["build", "list", "--prefix", str(tmp_path)])
    assert result.exit_code == 0
    assert "Cached" in result.output


def test_build_all_parallel_dry_run(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, [
        "build", "all",
        "--prefix", str(tmp_path / "prefix"),
        "--srcdir", str(tmp_path / "src"),
        "--parallel", "4",
        "--dry-run",
    ])
    assert "Traceback" not in (result.output or "")
    assert "Summary" in result.output


def test_build_lock_thread_safe(tmp_path):
    """Concurrent record() calls must not corrupt the lock file."""
    from cbench.builders import BuildConfig
    cfg = BuildConfig()
    prefix_bin = tmp_path / "bin"
    prefix_bin.mkdir()
    for i in range(5):
        (prefix_bin / f"bin{i}").write_text("x")

    from cbench.cli.build import BuildLock
    lock = BuildLock(tmp_path)
    import threading

    def record(i):
        lock.record(f"bench{i}", f"https://example.com/{i}", cfg, [f"bin{i}"])

    threads = [threading.Thread(target=record, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    lock2 = BuildLock(tmp_path)
    assert len(lock2._data) == 5


# ---------------------------------------------------------------------------
# build update
# ---------------------------------------------------------------------------

def test_build_update_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["build", "update", "--help"])
    assert result.exit_code == 0
    assert "update" in result.output.lower()


def test_build_update_dry_run_all(tmp_path):
    """build update --dry-run over all benchmarks should not crash."""
    runner = CliRunner()
    result = runner.invoke(cli, [
        "build", "update",
        "--prefix", str(tmp_path / "prefix"),
        "--srcdir", str(tmp_path / "src"),
        "--dry-run",
    ])
    assert "Traceback" not in (result.output or ""), result.output
    assert "Update Summary" in result.output


def test_build_update_unknown_benchmark(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, [
        "build", "update", "nosuchbenchmark",
        "--prefix", str(tmp_path / "prefix"),
        "--srcdir", str(tmp_path / "src"),
        "--dry-run",
    ])
    assert result.exit_code != 0
    assert "Unknown benchmark" in result.output


def test_update_source_no_git_repo(tmp_path):
    """update_source returns False when source dir is not a git repo."""
    from cbench.builders.stream import StreamBuilder
    builder = StreamBuilder()
    # StreamBuilder uses srcdir/stream, exists but no .git
    srcdir = tmp_path / "src"
    (srcdir / "stream").mkdir(parents=True)
    changed = builder.update_source(srcdir, dry_run=False)
    assert changed is False


def test_update_source_dry_run(tmp_path):
    """update_source in dry-run mode returns False without running git."""
    from cbench.builders.stream import StreamBuilder
    builder = StreamBuilder()
    srcdir = tmp_path / "src"
    (srcdir / "stream" / ".git").mkdir(parents=True)
    changed = builder.update_source(srcdir, dry_run=True)
    assert changed is False


def test_update_source_absent_dir(tmp_path):
    """update_source returns False when the source directory doesn't exist yet."""
    from cbench.builders.stream import StreamBuilder
    builder = StreamBuilder()
    srcdir = tmp_path / "src"
    srcdir.mkdir()
    changed = builder.update_source(srcdir, dry_run=False)
    assert changed is False


def test_bonnie_builds_as_gnu_cxx14(tmp_path, monkeypatch):
    """bonnie++ 2.00a fails under C++17 (GCC >= 11): 'reference to data is ambiguous'."""
    import cbench.builders.bonnie as bonnie_mod
    calls = []
    monkeypatch.setattr(bonnie_mod, "run", lambda cmd, **kw: calls.append(cmd))
    monkeypatch.setattr(bonnie_mod, "install_bins", lambda *a, **kw: ["bonnie++", "zcav"])
    get_builder("bonnie").build(tmp_path, tmp_path / "pfx", BuildConfig(), dry_run=False)
    configure = calls[0]
    assert configure[0] == "./configure"
    # must be inside CXX: bonnie's Makefile uses `CXX=@CXX@ $(CFLAGS)`, never CXXFLAGS
    assert "CXX=c++ -std=gnu++14" in configure
    assert not any(a.startswith("CXXFLAGS=") for a in configure)


def test_install_bins_in_place_does_not_fail(tmp_path):
    """ior/fio `make install` into prefix/bin, then install_bins(bin -> bin)."""
    from cbench.builders._util import install_bins
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "ior").write_text("#!/bin/sh\n")
    assert install_bins(bindir, bindir, ["ior"], dry_run=False) == ["ior"]
    assert (bindir / "ior").stat().st_mode & 0o755 == 0o755


# ---------------------------------------------------------------------------
# gpfsperf (built from the GPFS samples)
# ---------------------------------------------------------------------------

def _fake_samples(tmp_path):
    samples = tmp_path / "samples"
    samples.mkdir()
    for f in ("gpfsperf.c", "irreg.c", "irreg.h", "makefile", "README"):
        (samples / f).write_text("x")
    (samples / "gpfsperf").write_text("prebuilt")   # shipped binary
    return samples


def test_gpfsperf_fetch_copies_sources_not_prebuilt_binary(tmp_path, monkeypatch):
    import cbench.builders.gpfsperf as mod
    b = get_builder("gpfsperf")
    monkeypatch.setattr(b, "samples_dir", _fake_samples(tmp_path))
    src = b.fetch(tmp_path / "src")
    assert (src / "gpfsperf.c").exists() and (src / "makefile").exists()
    assert not (src / "gpfsperf").exists()
    assert mod.GpfsperfBuilder.optional


def test_gpfsperf_build_runs_the_gpfsperf_target(tmp_path, monkeypatch):
    import cbench.builders.gpfsperf as mod
    calls = []
    monkeypatch.setattr(mod, "run", lambda cmd, **kw: calls.append(cmd))
    monkeypatch.setattr(mod, "install_bins", lambda src, dst, names, **kw: names)
    monkeypatch.setattr(mod.shutil, "which", lambda name: None)       # no MPI here
    out = get_builder("gpfsperf").build(tmp_path, tmp_path / "pfx", BuildConfig(cc="gcc"))
    assert calls == [["make", "gpfsperf", "CC=gcc"]] and out == ["gpfsperf"]


def _gpfsperf_build(tmp_path, monkeypatch, *, have_mpicc, **extra):
    import cbench.builders.gpfsperf as mod
    calls = []
    monkeypatch.setattr(mod, "run", lambda cmd, **kw: calls.append(cmd))
    monkeypatch.setattr(mod, "install_bins", lambda src, dst, names, **kw: names)
    monkeypatch.setattr(mod.shutil, "which", lambda name: f"/opt/mpi/bin/{name}" if have_mpicc else None)
    cfg = BuildConfig(cc="gcc", mpicc="mpicc", extra=extra)
    return calls, get_builder("gpfsperf").build(tmp_path, tmp_path / "pfx", cfg)


def test_gpfsperf_also_builds_mpi_version_without_mpich_lib(tmp_path, monkeypatch):
    calls, out = _gpfsperf_build(tmp_path, monkeypatch, have_mpicc=True)
    assert calls == [["make", "gpfsperf", "CC=gcc"],
                     ["make", "gpfsperf-mpi", "MPCC=mpicc", "MPLIBS="]]
    assert out == ["gpfsperf", "gpfsperf-mpi"]


def test_gpfsperf_mpi_options(tmp_path, monkeypatch):
    calls, out = _gpfsperf_build(tmp_path, monkeypatch, have_mpicc=True, mplibs="-lmpich",
                                 cflags="-O2 -DGPFS_LINUX")
    assert calls[1] == ["make", "gpfsperf-mpi", "MPCC=mpicc", "MPLIBS=-lmpich",
                        "CFLAGS=-O2 -DGPFS_LINUX"]
    calls, out = _gpfsperf_build(tmp_path, monkeypatch, have_mpicc=True, mpi="no")
    assert out == ["gpfsperf"] and len(calls) == 1
    with pytest.raises(RuntimeError, match="mpicc not found"):
        _gpfsperf_build(tmp_path, monkeypatch, have_mpicc=False, mpi="yes")


def test_gpfsperf_requires_gpfs_samples(tmp_path, monkeypatch):
    b = get_builder("gpfsperf")
    monkeypatch.setattr(b, "samples_dir", tmp_path / "nope")
    assert any("GPFS not installed" in m for m in b.check_requires())
    monkeypatch.setattr(b, "samples_dir", _fake_samples(tmp_path))
    assert not any("GPFS" in m for m in b.check_requires())


def test_build_all_skips_optional_builder_without_prereqs(tmp_path, monkeypatch):
    from click.testing import CliRunner
    from cbench.cli.main import cli
    import cbench.builders.gpfsperf as mod
    import cbench.cli.build as build_mod
    monkeypatch.setattr(mod.GpfsperfBuilder, "samples_dir", tmp_path / "nope")
    monkeypatch.setattr(build_mod, "_run_one", lambda name, *a, **kw: True)
    res = CliRunner().invoke(cli, ["build", "all", "--prefix", str(tmp_path / "p"),
                                   "--srcdir", str(tmp_path / "s"), "--dry-run"])
    assert res.exit_code == 0, res.output
    assert "SKIPPED" in res.output and "gpfsperf" in res.output


def test_gpfsperf_build_cflags_override(tmp_path, monkeypatch):
    import cbench.builders.gpfsperf as mod
    calls = []
    monkeypatch.setattr(mod, "run", lambda cmd, **kw: calls.append(cmd))
    monkeypatch.setattr(mod, "install_bins", lambda src, dst, names, **kw: names)
    cfg = BuildConfig(cc="gcc", extra={"cflags": "-O2 -DGPFS_LINUX -DRDMA"})
    get_builder("gpfsperf").build(tmp_path, tmp_path / "pfx", cfg)
    assert calls == [["make", "gpfsperf", "CC=gcc", "CFLAGS=-O2 -DGPFS_LINUX -DRDMA"]]


def _readonly_tarball(tmp_path):
    """A tarball like iozone's: a read-only file inside a read-only directory."""
    import io
    import tarfile as tf_mod
    buf = io.BytesIO()
    with tf_mod.open(fileobj=buf, mode="w:gz") as tf:
        d = tf_mod.TarInfo("pkg-1.0/src")
        d.type, d.mode = tf_mod.DIRTYPE, 0o555
        tf.addfile(d)
        f = tf_mod.TarInfo("pkg-1.0/src/Changes.txt")
        data = b"v1\n"
        f.size, f.mode = len(data), 0o444
        tf.addfile(f, io.BytesIO(data))
    path = tmp_path / "pkg-1.0.tar.gz"
    path.write_bytes(buf.getvalue())
    return path


def test_wget_tarball_reuses_extracted_tree_and_force_replaces_readonly(tmp_path):
    """Re-running a build must not re-extract over read-only files (zima:
    iozone 'Permission denied: .../Changes.txt'); --force replaces the tree."""
    import shutil
    import cbench.builders._util as util_mod
    from cbench.builders._util import wget_tarball

    src = _readonly_tarball(tmp_path)
    dest = tmp_path / "dest"
    with patch.object(util_mod, "download", side_effect=lambda url, d: shutil.copy(src, d)):
        top = wget_tarball("https://example.com/pkg-1.0.tar.gz", dest, force=False, dry_run=False)
        assert (top / "src" / "Changes.txt").read_text() == "v1\n"
        # second build: extraction skipped, no PermissionError
        assert wget_tarball("https://example.com/pkg-1.0.tar.gz", dest,
                            force=False, dry_run=False) == top
        # --force: read-only tree removed and re-extracted
        assert wget_tarball("https://example.com/pkg-1.0.tar.gz", dest,
                            force=True, dry_run=False) == top
        assert (top / "src" / "Changes.txt").exists()
    util_mod._rmtree_writable(top)   # leave tmp_path removable


def test_wget_tarball_force_never_removes_outside_dest(tmp_path):
    """A hostile first member ('../x') must be rejected before any removal:
    the reuse/--force logic must never act on dest's parent."""
    import io
    import shutil
    import tarfile as tf_mod
    import cbench.builders._util as util_mod
    from cbench.builders._util import wget_tarball
    import pytest as _pytest

    buf = io.BytesIO()
    with tf_mod.open(fileobj=buf, mode="w:gz") as tf:
        info = tf_mod.TarInfo("../sibling.txt")
        info.size = 1
        tf.addfile(info, io.BytesIO(b"x"))
    evil = tmp_path / "evil.tar.gz"
    evil.write_bytes(buf.getvalue())
    keep = tmp_path / "keep-me.txt"
    keep.write_text("precious")
    dest = tmp_path / "dest"
    dest.mkdir()
    with patch.object(util_mod, "download", side_effect=lambda url, d: shutil.copy(evil, d)):
        with _pytest.raises(RuntimeError):
            wget_tarball("https://example.com/evil.tar.gz", dest, force=True, dry_run=False)
    assert keep.read_text() == "precious" and dest.is_dir()


def test_wget_tarball_rejects_dot_top_entry(tmp_path):
    """A tarball whose first entry is './file' has no top-level directory."""
    import io
    import shutil
    import tarfile as tf_mod
    import cbench.builders._util as util_mod
    from cbench.builders._util import wget_tarball
    import pytest as _pytest

    buf = io.BytesIO()
    with tf_mod.open(fileobj=buf, mode="w:gz") as tf:
        info = tf_mod.TarInfo("./file.txt")
        info.size = 1
        tf.addfile(info, io.BytesIO(b"x"))
    src = tmp_path / "flat.tar.gz"
    src.write_bytes(buf.getvalue())
    dest = tmp_path / "dest"
    with patch.object(util_mod, "download", side_effect=lambda url, d: shutil.copy(src, d)):
        with _pytest.raises(RuntimeError, match="top-level entry"):
            wget_tarball("https://example.com/flat.tar.gz", dest, force=True, dry_run=False)
    assert dest.is_dir()


def test_iozone_uses_a_pre_placed_tgz_without_downloading(tmp_path, monkeypatch):
    """Offline hosts (zimabg1 has no internet): drop the tarball into
    <srcdir>/iozone/ and the builder extracts it instead of downloading."""
    import io
    import tarfile as _tarfile

    import cbench.builders._util as util
    import cbench.builders.iozone as mod

    name = mod._TARBALL_URL.rsplit("/", 1)[1]
    assert name == "iozone3_511.tgz"
    dest = tmp_path / "src" / "iozone"
    dest.mkdir(parents=True)
    with _tarfile.open(dest / name, "w:gz") as tf:
        for member in ("iozone3_511/src/current/makefile", "iozone3_511/src/current/iozone.c"):
            data = b"x\n"
            info = _tarfile.TarInfo(member)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))

    def no_download(*a, **kw):
        raise AssertionError("must not download when the tarball is already there")

    monkeypatch.setattr(util, "download", no_download)
    src = get_builder("iozone").fetch(tmp_path / "src")
    assert src == dest / "iozone3_511" / "src" / "current"
    assert (src / "makefile").is_file() and (src / "iozone.c").is_file()


# ---------------------------------------------------------------------------
# NPB: make.def comes from NPB's own template
# ---------------------------------------------------------------------------

# the variable lines of NPB3.4.4/NPB3.4-MPI/config/make.def.template
_NPB_TEMPLATE = """\
#  This is the NPB make.def template
MPIFC = mpif90
FLINK\t= $(MPIFC)
FMPI_LIB =
FMPI_INC =
FFLAGS\t= -O3
FLINKFLAGS = $(FFLAGS)
MPICC = mpicc
CLINK\t= $(MPICC)
CFLAGS\t= -O3
CLINKFLAGS = $(CFLAGS)
CC\t= gcc -g
BINDIR\t= ../bin
RAND   = randi8
"""


def _npb_src(tmp_path, template=_NPB_TEMPLATE):
    src = tmp_path / "NPB3.4-MPI"
    (src / "config").mkdir(parents=True)
    if template is not None:
        (src / "config" / "make.def.template").write_text(template)
    return src


def test_npb_make_def_overrides_compilers_and_keeps_template_vars(tmp_path):
    from cbench.builders.npb import _write_make_def
    src = _npb_src(tmp_path)
    _write_make_def(src, BuildConfig(mpicc="/opt/mpi/bin/mpicc", mpif90="/opt/mpi/bin/mpif90",
                                     cflags="-O2", fflags="-O2 -march=native"))
    md = (src / "config" / "make.def").read_text()
    assert "MPIFC = /opt/mpi/bin/mpif90\n" in md and "MPICC = /opt/mpi/bin/mpicc\n" in md
    assert "FFLAGS = -O2 -march=native\n" in md and "CFLAGS = -O2\n" in md
    assert "FLINK\t= $(MPIFC)" in md and "BINDIR\t= ../bin" in md     # kept from the template
    assert "MPIF77" not in md


def test_npb_make_def_needs_the_template(tmp_path):
    from cbench.builders.npb import _write_make_def
    with pytest.raises(RuntimeError, match="not an NPB 3.4 MPI source tree"):
        _write_make_def(_npb_src(tmp_path, template=None), BuildConfig())
    src = _npb_src(tmp_path / "b", template=_NPB_TEMPLATE.replace("MPIFC = mpif90\n", ""))
    with pytest.raises(RuntimeError, match="no MPIFC line"):
        _write_make_def(src, BuildConfig())


def test_npb_pins_3_4_4_and_builds_each_suite(tmp_path, monkeypatch):
    import cbench.builders.npb as mod
    assert mod._TARBALL_URL.endswith("/NPB3.4.4.tar.gz")
    calls = []
    monkeypatch.setattr(mod, "run", lambda cmd, **kw: calls.append(cmd))
    monkeypatch.setattr(mod, "install_bins", lambda src, dst, names, **kw: names)
    src = _npb_src(tmp_path)
    out = get_builder("npb").build(src, tmp_path / "pfx",
                                   BuildConfig(jobs=2, extra={"suites": "ep is", "class": "a"}))
    assert calls == [["make", "EP", "CLASS=A", "-j2"], ["make", "IS", "CLASS=A", "-j2"]]
    assert out == ["ep.A.x", "is.A.x"]                 # NPB 3.4's own (lowercase) names
