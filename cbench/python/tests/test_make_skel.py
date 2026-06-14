"""Tests for cbench make-skel command."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from cbench.cli.main import cli

runner = CliRunner()


def test_make_skel_help():
    result = runner.invoke(cli, ["make-skel", "--help"])
    assert result.exit_code == 0
    assert "--skelname" in result.output
    assert "--numprocs" in result.output


def test_make_skel_dry_run(tmp_path):
    result = runner.invoke(cli, [
        "make-skel", "--skelname", "setvars",
        "--ppn", "4", "--numprocs", "16",
        "--outdir", str(tmp_path), "--dry-run",
    ])
    assert result.exit_code == 0
    # Should print the script content, not write files
    assert "NUM_PROCS" in result.output or "16" in result.output
    # No files written in dry-run
    assert list(tmp_path.iterdir()) == []


def test_make_skel_writes_files(tmp_path):
    result = runner.invoke(cli, [
        "make-skel", "--skelname", "setvars",
        "--ppn", "1", "--numprocs", "1",
        "--outdir", str(tmp_path),
    ])
    assert result.exit_code == 0
    files = list(tmp_path.iterdir())
    assert len(files) == 2  # batch + interactive
    names = {f.name for f in files}
    # One .sh interactive, one batch (extension depends on config)
    assert any(n.endswith(".sh") for n in names)


def test_make_skel_interactive_executable(tmp_path):
    runner.invoke(cli, [
        "make-skel", "--skelname", "setvars",
        "--outdir", str(tmp_path),
    ])
    sh = next((f for f in tmp_path.iterdir() if f.suffix == ".sh"), None)
    assert sh is not None
    assert sh.stat().st_mode & 0o111  # executable bit set


def test_make_skel_tokens_substituted(tmp_path):
    runner.invoke(cli, [
        "make-skel", "--skelname", "setvars",
        "--ppn", "4", "--numprocs", "8",
        "--ident", "myrun",
        "--outdir", str(tmp_path),
    ])
    sh = next((f for f in tmp_path.iterdir() if f.suffix == ".sh"), None)
    assert sh is not None
    content = sh.read_text()
    # TOKEN_HERE style tokens should all be substituted
    assert "_HERE" not in content


def test_make_skel_unknown_skelname(tmp_path):
    result = runner.invoke(cli, [
        "make-skel", "--skelname", "nosuchtemplate",
        "--outdir", str(tmp_path),
    ])
    assert result.exit_code != 0


def test_make_skel_hello_template(tmp_path):
    result = runner.invoke(cli, [
        "make-skel", "--skelname", "hello",
        "--outdir", str(tmp_path),
    ])
    assert result.exit_code == 0
    assert len(list(tmp_path.iterdir())) == 2
