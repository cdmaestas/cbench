from pathlib import Path

import pytest

from cbench.config import ClusterConfig, ConfigError, load_config


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


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def _write_yaml(tmp_path, content: str) -> Path:
    p = tmp_path / "cluster.yaml"
    p.write_text(content)
    return p


def test_valid_minimal_yaml(tmp_path):
    p = _write_yaml(tmp_path, "cluster_name: mycluster\nmax_nodes: 2\n")
    cfg = load_config(p)
    assert cfg.cluster_name == "mycluster"


def test_unknown_key_raises(tmp_path):
    p = _write_yaml(tmp_path, "batch_metod: slurm\n")  # typo
    with pytest.raises(ConfigError, match="batch_metod"):
        load_config(p)


def test_wrong_type_integer_raises(tmp_path):
    p = _write_yaml(tmp_path, "procs_per_node: eight\n")
    with pytest.raises(ConfigError, match="procs_per_node"):
        load_config(p)


def test_invalid_batch_method_raises(tmp_path):
    p = _write_yaml(tmp_path, "batch_method: kubernetes\n")
    with pytest.raises(ConfigError, match="batch_method"):
        load_config(p)


def test_invalid_launch_method_raises(tmp_path):
    p = _write_yaml(tmp_path, "joblaunch_method: rsh\n")
    with pytest.raises(ConfigError, match="joblaunch_method"):
        load_config(p)


def test_invalid_walltime_format_raises(tmp_path):
    p = _write_yaml(tmp_path, "default_walltime: '4h'\n")
    with pytest.raises(ConfigError, match="default_walltime"):
        load_config(p)


def test_negative_max_nodes_raises(tmp_path):
    p = _write_yaml(tmp_path, "max_nodes: -1\n")
    with pytest.raises(ConfigError, match="max_nodes"):
        load_config(p)


def test_memory_util_factor_out_of_range_raises(tmp_path):
    p = _write_yaml(tmp_path, "memory_util_factors: [0.5, 1.5]\n")
    with pytest.raises(ConfigError, match="memory_util_factors"):
        load_config(p)


def test_invalid_filter_module_raises(tmp_path):
    p = _write_yaml(tmp_path, "parse_filter_include: [openmpi, badmodule]\n")
    with pytest.raises(ConfigError, match="parse_filter_include"):
        load_config(p)


def test_error_message_names_file(tmp_path):
    p = _write_yaml(tmp_path, "batch_metod: slurm\n")
    with pytest.raises(ConfigError) as exc_info:
        load_config(p)
    assert str(p) in str(exc_info.value)


def test_multiple_errors_all_reported(tmp_path):
    p = _write_yaml(tmp_path, "batch_metod: slurm\nmax_nodes: -5\n")
    with pytest.raises(ConfigError) as exc_info:
        load_config(p)
    msg = str(exc_info.value)
    assert "batch_metod" in msg
    assert "max_nodes" in msg


def test_all_valid_batch_methods(tmp_path):
    for method in ["slurm", "torque", "pbspro", "lsf", "moab", "local"]:
        p = _write_yaml(tmp_path, f"batch_method: {method}\n")
        cfg = load_config(p)
        assert cfg.batch_method == method


def test_cluster_name_special_chars_raises(tmp_path):
    p = _write_yaml(tmp_path, "cluster_name: 'my cluster/bad'\n")
    with pytest.raises(ConfigError, match="cluster_name"):
        load_config(p)


def test_cluster_name_valid_patterns(tmp_path):
    for name in ["mycluster", "my-cluster", "my_cluster", "Cluster01"]:
        p = _write_yaml(tmp_path, f"cluster_name: {name}\n")
        cfg = load_config(p)
        assert cfg.cluster_name == name


def test_all_valid_launch_methods(tmp_path):
    for method in ["openmpi", "mpiexec", "slurm", "alps", "yod"]:
        p = _write_yaml(tmp_path, f"joblaunch_method: {method}\n")
        cfg = load_config(p)
        assert cfg.joblaunch_method == method


# ---------------------------------------------------------------------------
# nodecheck-related keys: io_targets, remotecmd_rcmd, remotecmd_exec_cmd
# ---------------------------------------------------------------------------

def test_io_targets_accepted(tmp_path):
    p = _write_yaml(tmp_path, "io_targets:\n  parallel: /gpfs/scratch\n  node-local: /tmp\n")
    cfg = load_config(p)
    assert cfg.io_targets == {"parallel": "/gpfs/scratch", "node-local": "/tmp"}


def test_io_targets_relative_path_rejected(tmp_path):
    p = _write_yaml(tmp_path, "io_targets:\n  parallel: scratch\n")
    with pytest.raises(ConfigError, match="io_targets"):
        load_config(p)


def test_io_targets_bad_name_rejected(tmp_path):
    p = _write_yaml(tmp_path, "io_targets:\n  'bad name': /tmp\n")
    with pytest.raises(ConfigError, match="io_targets"):
        load_config(p)


def test_remotecmd_rcmd_validated(tmp_path):
    assert load_config(_write_yaml(tmp_path, "remotecmd_rcmd: exec\n")).remotecmd_rcmd == "exec"
    with pytest.raises(ConfigError, match="remotecmd_rcmd"):
        load_config(_write_yaml(tmp_path, "remotecmd_rcmd: rsh\n"))


def test_rcmd_defaults():
    cfg = ClusterConfig()
    assert cfg.remotecmd_rcmd == "ssh" and cfg.remotecmd_exec_cmd == "" and cfg.io_targets == {}


def test_explicit_keys_tracks_file_keys(tmp_path):
    cfg = load_config(_write_yaml(tmp_path, "cluster_name: zima\nmemory_per_node_mb: 7524\n"))
    assert cfg.explicit_keys == {"cluster_name", "memory_per_node_mb"}
    assert "procs_per_node" not in cfg.explicit_keys  # built-in default, not from file
    assert ClusterConfig().explicit_keys == frozenset()


def test_explicit_keys_is_not_a_yaml_key(tmp_path):
    with pytest.raises(ConfigError, match="explicit_keys"):
        load_config(_write_yaml(tmp_path, "explicit_keys: [cluster_name]\n"))
