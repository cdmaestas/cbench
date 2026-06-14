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
