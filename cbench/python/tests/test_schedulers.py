"""Tests for scheduler adapters."""

import pytest

from cbench.config import ClusterConfig
from cbench import schedulers


def _cfg(**kwargs) -> ClusterConfig:
    defaults = dict(
        cluster_name="test", max_nodes=4, procs_per_node=8,
        batch_method="slurm", joblaunch_method="openmpi",
    )
    defaults.update(kwargs)
    return ClusterConfig(**defaults)


# ---------------------------------------------------------------------------
# local scheduler
# ---------------------------------------------------------------------------

def test_local_submit_cmd():
    cfg = _cfg(batch_method="local")
    assert schedulers.submit_cmd("/path/to/job.sh", cfg) == "bash /path/to/job.sh"


def test_local_extension():
    cfg = _cfg(batch_method="local")
    assert schedulers.extension(cfg) == ".sh"


def test_local_query_returns_empty():
    cfg = _cfg(batch_method="local")
    result = schedulers.query("anything", cfg)
    assert result == {"RUNNING": 0, "QUEUED": 0, "TOTAL": 0}


def test_local_nodespec_empty():
    cfg = _cfg(batch_method="local")
    assert schedulers.nodespec(["n1", "n2"], cfg) == ""


# ---------------------------------------------------------------------------
# existing schedulers still work
# ---------------------------------------------------------------------------

def test_slurm_extension():
    assert schedulers.extension(_cfg(batch_method="slurm")) == ".slurm"


def test_torque_extension():
    assert schedulers.extension(_cfg(batch_method="torque")) == ".pbs"


def test_pbspro_extension():
    assert schedulers.extension(_cfg(batch_method="pbspro")) == ".pbs"


def test_lsf_extension():
    assert schedulers.extension(_cfg(batch_method="lsf")) == ".lsf"


def test_moab_extension():
    assert schedulers.extension(_cfg(batch_method="moab")) == ".pbs"


def test_unknown_batch_method_raises():
    cfg = _cfg(batch_method="nosuchscheduler")
    with pytest.raises(ValueError, match="Unknown batch_method"):
        schedulers.submit_cmd("/path/job.sh", cfg)


# ---------------------------------------------------------------------------
# start-jobs integration: local mode runs bash directly
# ---------------------------------------------------------------------------

def test_start_jobs_local_dry_run(tmp_path):
    """cbench start-jobs --interactive prints bash invocation."""
    from click.testing import CliRunner
    from cbench.cli.main import cli

    # interactive mode globs for the batch extension from config (default: .slurm)
    ident_dir = tmp_path / "bandwidth" / "run1" / "xhpl-1ppn-1"
    ident_dir.mkdir(parents=True)
    script = ident_dir / "xhpl-1ppn-1.slurm"
    script.write_text("#!/bin/bash\necho hello\n")

    runner = CliRunner()
    result = runner.invoke(cli, [
        "start-jobs",
        "--testset", "bandwidth",
        "--ident", "run1",
        "--interactive",
        "--cbenchtest", str(tmp_path),
        "--dry-run",
    ])
    assert result.exit_code == 0
    assert "bash" in result.output
