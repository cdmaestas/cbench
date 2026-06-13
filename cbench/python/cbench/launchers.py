"""MPI job launch command builders.

Each builder takes (numprocs, ppn, numnodes, cfg) and returns the
launch command prefix string inserted at JOBLAUNCH_CMD_HERE in templates.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cbench.config import ClusterConfig


def _cmd(cfg: "ClusterConfig") -> str:
    return cfg.joblaunch_cmd or cfg.joblaunch_method


def openmpi_build(numprocs: int, ppn: int, numnodes: int, cfg: "ClusterConfig") -> str:
    cmd = _cmd(cfg) if cfg.joblaunch_cmd else "orterun"
    extra = cfg.joblaunch_extraargs
    return f"{cmd} -npernode {ppn} -np {numprocs} {extra}".strip()


def mpiexec_build(numprocs: int, ppn: int, numnodes: int, cfg: "ClusterConfig") -> str:
    cmd = _cmd(cfg) if cfg.joblaunch_cmd else "mpiexec"
    extra = cfg.joblaunch_extraargs
    return f"{cmd} -pernode -np {numprocs} {extra}".strip()


def slurm_build(numprocs: int, ppn: int, numnodes: int, cfg: "ClusterConfig") -> str:
    cmd = _cmd(cfg) if cfg.joblaunch_cmd else "srun"
    extra = cfg.joblaunch_extraargs
    return f"{cmd} -n {numprocs} --ntasks-per-node {ppn} {extra}".strip()


def yod_build(numprocs: int, ppn: int, numnodes: int, cfg: "ClusterConfig") -> str:
    cmd = _cmd(cfg) if cfg.joblaunch_cmd else "yod"
    extra = cfg.joblaunch_extraargs
    return f"{cmd} -sz {numprocs} {extra}".strip()


def alps_build(numprocs: int, ppn: int, numnodes: int, cfg: "ClusterConfig") -> str:
    cmd = _cmd(cfg) if cfg.joblaunch_cmd else "aprun"
    extra = cfg.joblaunch_extraargs
    return f"{cmd} -n {numprocs} -N {ppn} {extra}".strip()


_LAUNCHERS = {
    "openmpi": openmpi_build,
    "mpiexec": mpiexec_build,
    "slurm": slurm_build,
    "yod": yod_build,
    "alps": alps_build,
}


def build_launch_cmd(numprocs: int, ppn: int, numnodes: int, cfg: "ClusterConfig") -> str:
    builder = _LAUNCHERS.get(cfg.joblaunch_method)
    if builder is None:
        raise ValueError(f"Unknown joblaunch_method: {cfg.joblaunch_method!r}")
    return builder(numprocs, ppn, numnodes, cfg)
