from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


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
    parse_filter_include: list[str] = field(
        default_factory=lambda: ["openmpi", "slurm", "mpiexec", "torque", "mvapich", "misc"]
    )
    nodehwtest_xhpl_ppn: int = 1
    nodehwtest_npb_longjobs: bool = False
    nodehwtest_stress_minutes: int = 120
    nodehwtest_local_filesystems: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # CBENCHCLUSTER env var overrides the config file value
        env_cluster = os.environ.get("CBENCHCLUSTER")
        if env_cluster:
            self.cluster_name = env_cluster

        # Derive max_ppn_procs if not supplied
        if not self.max_ppn_procs:
            self.max_ppn_procs = {
                str(ppn): ppn * self.max_nodes
                for ppn in [1, 2, 4, self.procs_per_node]
            }

    @property
    def ppn_levels(self) -> list[int]:
        return sorted(int(k) for k in self.max_ppn_procs)


def load_config(path: Optional[str | Path] = None) -> ClusterConfig:
    """Load cluster configuration from a YAML file.

    Search order:
      1. Explicit ``path`` argument
      2. ``CBENCHOME/cluster.yaml``
      3. ``CBENCHTEST/cluster.yaml``
      4. ``./cluster.yaml``
    Falls back to defaults if no file is found.
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
            # Convert max_ppn_procs keys to strings (YAML may parse them as int)
            if "max_ppn_procs" in data:
                data["max_ppn_procs"] = {str(k): v for k, v in data["max_ppn_procs"].items()}
            return ClusterConfig(**{k: v for k, v in data.items() if k in ClusterConfig.__dataclass_fields__})

    return ClusterConfig()
