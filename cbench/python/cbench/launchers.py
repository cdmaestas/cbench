"""MPI job launch command builders.

Each builder takes (numprocs, ppn, numnodes, cfg) and returns the
launch command prefix string inserted at JOBLAUNCH_CMD_HERE in templates.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cbench.config import ClusterConfig


def _cmd(cfg: ClusterConfig) -> str:
    return cfg.joblaunch_cmd or cfg.joblaunch_method


#: Open MPI launcher when joblaunch_cmd is unset: common_header.in sets
#: CBENCH_OMPI_RUN on the job's node (orterun on Open MPI <= 4, else mpirun;
#: Open MPI 5 has no orterun); orterun if the header didn't run.
OMPI_DEFAULT_CMD = "${CBENCH_OMPI_RUN:-orterun}"


def openmpi_build(numprocs: int, ppn: int, numnodes: int, cfg: ClusterConfig) -> str:
    cmd = _cmd(cfg) if cfg.joblaunch_cmd else OMPI_DEFAULT_CMD
    extra = cfg.joblaunch_extraargs
    # --map-by ppr:N:node works on Open MPI 1.8+; -npernode is deprecated in 5
    return f"{cmd} --map-by ppr:{ppn}:node -np {numprocs} {extra}".strip()


def mpiexec_build(numprocs: int, ppn: int, numnodes: int, cfg: ClusterConfig) -> str:
    cmd = _cmd(cfg) if cfg.joblaunch_cmd else "mpiexec"
    extra = cfg.joblaunch_extraargs
    return f"{cmd} -pernode -np {numprocs} {extra}".strip()


def slurm_build(numprocs: int, ppn: int, numnodes: int, cfg: ClusterConfig) -> str:
    cmd = _cmd(cfg) if cfg.joblaunch_cmd else "srun"
    extra = cfg.joblaunch_extraargs
    return f"{cmd} -n {numprocs} --ntasks-per-node {ppn} {extra}".strip()


def yod_build(numprocs: int, ppn: int, numnodes: int, cfg: ClusterConfig) -> str:
    cmd = _cmd(cfg) if cfg.joblaunch_cmd else "yod"
    extra = cfg.joblaunch_extraargs
    return f"{cmd} -sz {numprocs} {extra}".strip()


def alps_build(numprocs: int, ppn: int, numnodes: int, cfg: ClusterConfig) -> str:
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


def build_launch_cmd(numprocs: int, ppn: int, numnodes: int, cfg: ClusterConfig) -> str:
    builder = _LAUNCHERS.get(cfg.joblaunch_method)
    if builder is None:
        raise ValueError(f"Unknown joblaunch_method: {cfg.joblaunch_method!r}")
    return builder(numprocs, ppn, numnodes, cfg)
