from __future__ import annotations

import os
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


# ---------------------------------------------------------------------------
# Cluster config schema — validated on every load_config() call
# ---------------------------------------------------------------------------

_VALID_BATCH_METHODS = ["slurm", "torque", "pbspro", "lsf", "moab", "local"]
_VALID_LAUNCH_METHODS = ["openmpi", "mpiexec", "slurm", "alps", "yod"]
_VALID_REMOTE_METHODS = ["pdsh", "ssh"]
_VALID_RCMD_MODULES = ["ssh", "exec"]
_VALID_IO_PROFILES = ["auto", "ai", "general", "hpc", "streaming"]  # cbench.fioprofile
#: deprecated cluster.yaml key -> current key (both accepted; not both at once)
_KEY_ALIASES = {"fio_profile": "io_profile", "fio_seq_bs": "io_seq_bs"}
_VALID_FILTER_MODULES = ["openmpi", "slurm", "torque", "mvapich", "mpiexec", "cray", "misc"]

_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "cluster_name": {"type": "string", "minLength": 1, "pattern": r"^[A-Za-z0-9_\-]+$"},
        "max_nodes": {"type": "integer", "minimum": 1},
        "procs_per_node": {"type": "integer", "minimum": 1},
        "max_procs": {"type": "integer", "minimum": 1},
        "max_ppn_procs": {
            "type": "object",
            "additionalProperties": {"type": "integer", "minimum": 1},
        },
        "memory_per_node_mb": {"type": "integer", "minimum": 1},
        "memory_per_processor_mb": {"type": "integer", "minimum": 1},
        "default_walltime": {
            "type": "string",
            "pattern": r"^\d+:\d{2}:\d{2}$",
            "description": "HH:MM:SS format",
        },
        "walltime_method": {"type": "integer", "enum": [0, 1]},
        "walltime_steptime": {"type": "integer", "minimum": 0},
        "extra_job_nodes": {"type": "integer", "minimum": 0},
        "memory_util_factors": {
            "type": "array",
            "items": {"type": "number", "exclusiveMinimum": 0, "maximum": 1},
            "minItems": 1,
        },
        "joblaunch_method": {"type": "string", "enum": _VALID_LAUNCH_METHODS},
        "joblaunch_cmd": {"type": "string"},
        "joblaunch_extraargs": {"type": "string"},
        "batch_method": {"type": "string", "enum": _VALID_BATCH_METHODS},
        "batch_cmd": {"type": "string"},
        "batch_extraargs": {"type": "string"},
        "remotecmd_method": {"type": "string", "enum": _VALID_REMOTE_METHODS},
        "remotecmd_extraargs": {"type": "string"},
        # pdsh rcmd module used by `cbench nodecheck` (pdsh -R <module>)
        "remotecmd_rcmd": {"type": "string", "enum": _VALID_RCMD_MODULES},
        # local command template for the pdsh exec module; must contain %h
        "remotecmd_exec_cmd": {"type": "string"},
        # named IO target directories, e.g. {parallel: /gpfs/scratch, node-local: /tmp}
        "io_targets": {
            "type": "object",
            "propertyNames": {"pattern": r"^[A-Za-z0-9_\-]+$"},
            "additionalProperties": {"type": "string", "pattern": r"^/"},
        },
        # IO workload profile (cbench.fioprofile): sets the sequential block /
        # record / transfer size for fio, iozone, gpfsperf and IOR;
        # io_seq_bs overrides it exactly. fio_* names are deprecated aliases.
        "io_profile": {"type": "string", "enum": _VALID_IO_PROFILES},
        "io_seq_bs": {"type": "string", "pattern": r"^\d+[kKmMgG]$"},
        "fio_profile": {"type": "string", "enum": _VALID_IO_PROFILES},
        "fio_seq_bs": {"type": "string", "pattern": r"^\d+[kKmMgG]$"},
        # per-job time cap for the fio data jobs
        "fio_runtime_s": {"type": "integer", "minimum": 1},
        # IO thread/job count for every IO benchmark (iosizing.io_threads):
        # all CPUs of the chosen basis, optionally capped
        "io_threads_max": {"type": "integer", "minimum": 1},
        "io_threads_basis": {"type": "string", "enum": ["logical", "physical"]},
        "parse_filter_include": {
            "type": "array",
            "items": {"type": "string", "enum": _VALID_FILTER_MODULES},
        },
        "nodehwtest_xhpl_ppn": {"type": "integer", "minimum": 1},
        "nodehwtest_npb_longjobs": {"type": "boolean"},
        "nodehwtest_stress_minutes": {"type": "integer", "minimum": 1},
        "nodehwtest_local_filesystems": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
}


def _validate_config(data: dict, source: Path) -> None:
    """Validate raw YAML data against _SCHEMA and raise ConfigError on failure."""
    try:
        import jsonschema
    except ImportError as e:
        # jsonschema is a hard dependency (pyproject.toml); if it's missing the
        # install is broken and silently skipping validation would let invalid
        # cluster.yaml files through unchecked.
        raise AssertionError(
            "jsonschema is not installed — cluster.yaml validation cannot run. "
            "Reinstall the package: pip install -e cbench/python"
        ) from e

    validator = jsonschema.Draft7Validator(_SCHEMA)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    if not errors:
        return

    lines = [f"Invalid cluster.yaml ({source}):"]
    for err in errors:
        path = " → ".join(str(p) for p in err.absolute_path) or "(root)"
        lines.append(f"  {path}: {err.message}")
    raise ConfigError("\n".join(lines))


class ConfigError(ValueError):
    """Raised when cluster.yaml fails schema validation."""


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class ClusterConfig:
    cluster_name: str = "test"
    max_nodes: int = 1
    procs_per_node: int = 8
    max_procs: int = 8
    max_ppn_procs: dict[str, int] = field(default_factory=dict)
    memory_per_node_mb: int = 2048
    memory_per_processor_mb: int = 256
    default_walltime: str = "04:00:00"
    walltime_method: int = 0
    walltime_steptime: int = 10
    extra_job_nodes: int = 0
    memory_util_factors: list[float] = field(default_factory=lambda: [0.25, 0.80])
    joblaunch_method: str = "openmpi"
    joblaunch_cmd: str = ""
    joblaunch_extraargs: str = ""
    batch_method: str = "slurm"
    batch_cmd: str = ""
    batch_extraargs: str = ""
    remotecmd_method: str = "pdsh"
    remotecmd_extraargs: str = "-f 700"
    remotecmd_rcmd: str = "ssh"
    remotecmd_exec_cmd: str = ""
    io_targets: dict[str, str] = field(default_factory=dict)
    fio_runtime_s: int = 300
    io_profile: str = "auto"
    io_seq_bs: str = ""
    io_threads_max: Optional[int] = None
    io_threads_basis: str = "logical"
    parse_filter_include: list[str] = field(
        default_factory=lambda: ["openmpi", "slurm", "mpiexec", "torque", "mvapich", "misc"]
    )
    nodehwtest_xhpl_ppn: int = 1
    nodehwtest_npb_longjobs: bool = False
    nodehwtest_stress_minutes: int = 120
    nodehwtest_local_filesystems: list[str] = field(default_factory=list)
    # Keys that were explicitly present in the loaded cluster.yaml (vs built-in
    # defaults). Not a YAML key — set by load_config(); the schema rejects it.
    explicit_keys: frozenset = field(default_factory=frozenset, repr=False, compare=False)

    def __post_init__(self) -> None:
        env_cluster = os.environ.get("CBENCHCLUSTER")
        if env_cluster:
            self.cluster_name = env_cluster

        if not self.max_ppn_procs:
            self.max_ppn_procs = {
                str(ppn): ppn * self.max_nodes
                for ppn in [1, 2, 4, self.procs_per_node]
            }

    @property
    def ppn_levels(self) -> list[int]:
        return sorted(int(k) for k in self.max_ppn_procs)


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_config(path: Optional[str | Path] = None) -> ClusterConfig:
    """Load cluster configuration from a YAML file.

    Search order:
      1. Explicit ``path`` argument
      2. ``CBENCHOME/cluster.yaml``
      3. ``CBENCHTEST/cluster.yaml``
      4. ``./cluster.yaml``
    Falls back to defaults if no file is found.

    Raises ``ConfigError`` if the file exists but fails schema validation.
    """
    candidates: list[Path] = []
    if path:
        candidates.append(Path(path))
    for env in ("CBENCHOME", "CBENCHSTANDALONEDIR", "CBENCHTEST"):
        val = os.environ.get(env)
        if val:
            candidates.append(Path(val) / "cluster.yaml")
    candidates.append(Path("cluster.yaml"))

    for candidate in candidates:
        if candidate.exists():
            with candidate.open() as fh:
                data = yaml.safe_load(fh) or {}
            # Normalise max_ppn_procs keys to strings (YAML may parse them as int)
            if "max_ppn_procs" in data:
                data["max_ppn_procs"] = {str(k): v for k, v in data["max_ppn_procs"].items()}
            _validate_config(data, candidate)
            for old, new in _KEY_ALIASES.items():
                if old in data:
                    if new in data:
                        raise ConfigError(f"{candidate}: set {new} or its deprecated alias {old}, "
                                          "not both")
                    warnings.warn(f"{candidate}: {old} is deprecated, use {new}",
                                  DeprecationWarning, stacklevel=2)
                    data[new] = data.pop(old)
            cfg = ClusterConfig(**{k: v for k, v in data.items() if k in ClusterConfig.__dataclass_fields__})
            cfg.explicit_keys = frozenset(data)
            return cfg

    return ClusterConfig()
