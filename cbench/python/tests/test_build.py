"""Tests for cbench build framework and CLI."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, call

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
    "iozone", "fio",
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

    # Patch wget_tarball to skip download and use our crafted tarball
    from unittest.mock import patch
    import urllib.request

    def fake_retrieve(url, dest_file):
        import shutil
        shutil.copy(str(tarball_path), dest_file)

    from cbench.builders._util import wget_tarball
    with patch.object(urllib.request, "urlretrieve", side_effect=fake_retrieve):
        import pytest as _pytest
        with _pytest.raises(RuntimeError, match="escapes destination"):
            wget_tarball("https://example.com/evil.tar.gz", dest, force=True, dry_run=False)


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
