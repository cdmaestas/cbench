import os
import tempfile
from pathlib import Path

import pytest

from cbench.config import ClusterConfig, load_config


def test_defaults():
    cfg = ClusterConfig()
    assert cfg.cluster_name == "test"
    assert cfg.procs_per_node == 8
    assert cfg.batch_method == "slurm"


def test_load_yaml(tmp_path):
    yaml_content = """
cluster_name: mycluster
max_nodes: 4
procs_per_node: 16
max_procs: 64
default_walltime: "02:00:00"
batch_method: torque
joblaunch_method: mpiexec
memory_util_factors: [0.5, 0.9]
"""
    cfg_file = tmp_path / "cluster.yaml"
    cfg_file.write_text(yaml_content)
    cfg = load_config(cfg_file)
    assert cfg.cluster_name == "mycluster"
    assert cfg.max_nodes == 4
    assert cfg.batch_method == "torque"
    assert cfg.memory_util_factors == [0.5, 0.9]


def test_env_override(tmp_path, monkeypatch):
    yaml_content = "cluster_name: original\n"
    cfg_file = tmp_path / "cluster.yaml"
    cfg_file.write_text(yaml_content)
    monkeypatch.setenv("CBENCHCLUSTER", "override")
    cfg = load_config(cfg_file)
    assert cfg.cluster_name == "override"


def test_fallback_to_defaults_when_no_file():
    cfg = load_config("/nonexistent/path/cluster.yaml")
    assert cfg.cluster_name == "test"


def test_ppn_levels():
    cfg = ClusterConfig(max_ppn_procs={"1": 4, "2": 8, "4": 16})
    assert cfg.ppn_levels == [1, 2, 4]
