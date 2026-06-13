"""Batch scheduler adapters.

Each adapter implements:
  submit_cmd(script, cfg) -> str        command string to submit a job
  nodespec(nodelist, cfg) -> str        node specification fragment
  query(regex, cfg) -> dict             {'RUNNING': n, 'QUEUED': n, 'TOTAL': n, ...jobname: state}
  extension(cfg) -> str                 script file extension (.slurm, .pbs, ...)
"""

from __future__ import annotations

import re
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cbench.config import ClusterConfig


# ---------------------------------------------------------------------------
# SLURM
# ---------------------------------------------------------------------------

def slurm_submit_cmd(script: str, cfg: "ClusterConfig") -> str:
    cmd = cfg.batch_cmd or "sbatch"
    extra = cfg.batch_extraargs
    return f"{cmd} {extra} {script}".strip()


def slurm_nodespec(nodelist: list[str], cfg: "ClusterConfig") -> str:
    return f"-w {','.join(nodelist)}" if nodelist else ""


def slurm_query(regex: str, cfg: "ClusterConfig") -> dict:
    cmd = cfg.batch_cmd or "squeue"
    try:
        out = subprocess.check_output(
            [cmd, "--noheader", "-o", "%j %T"], text=True, stderr=subprocess.DEVNULL
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"RUNNING": 0, "QUEUED": 0, "TOTAL": 0}

    result: dict = {"RUNNING": 0, "QUEUED": 0, "TOTAL": 0}
    pat = re.compile(regex) if regex else None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        name, state = parts[0], parts[1].upper()
        if pat and not pat.search(name):
            continue
        simplified = "RUNNING" if state == "RUNNING" else "QUEUED"
        result[simplified] = result.get(simplified, 0) + 1
        result["TOTAL"] += 1
        result[name] = simplified.lower()
    return result


def slurm_extension(cfg: "ClusterConfig") -> str:
    return ".slurm"


# ---------------------------------------------------------------------------
# Torque / PBS
# ---------------------------------------------------------------------------

def torque_submit_cmd(script: str, cfg: "ClusterConfig") -> str:
    cmd = cfg.batch_cmd or "qsub"
    extra = cfg.batch_extraargs
    return f"{cmd} {extra} {script}".strip()


def torque_nodespec(nodelist: list[str], cfg: "ClusterConfig") -> str:
    return f"-l nodes={'+'.join(nodelist)}" if nodelist else ""


def torque_query(regex: str, cfg: "ClusterConfig") -> dict:
    cmd = cfg.batch_cmd or "qstat"
    try:
        out = subprocess.check_output([cmd, "-a"], text=True, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"RUNNING": 0, "QUEUED": 0, "TOTAL": 0}

    result: dict = {"RUNNING": 0, "QUEUED": 0, "TOTAL": 0}
    pat = re.compile(regex) if regex else None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 10:
            continue
        name, state = parts[3], parts[9].upper()
        if pat and not pat.search(name):
            continue
        simplified = "RUNNING" if state == "R" else "QUEUED"
        result[simplified] = result.get(simplified, 0) + 1
        result["TOTAL"] += 1
        result[name] = simplified.lower()
    return result


def torque_extension(cfg: "ClusterConfig") -> str:
    return ".pbs"


# ---------------------------------------------------------------------------
# LSF
# ---------------------------------------------------------------------------

def lsf_submit_cmd(script: str, cfg: "ClusterConfig") -> str:
    cmd = cfg.batch_cmd or "bsub"
    extra = cfg.batch_extraargs
    return f"{cmd} {extra} < {script}".strip()


def lsf_nodespec(nodelist: list[str], cfg: "ClusterConfig") -> str:
    return ""


def lsf_query(regex: str, cfg: "ClusterConfig") -> dict:
    return {"RUNNING": 0, "QUEUED": 0, "TOTAL": 0}


def lsf_extension(cfg: "ClusterConfig") -> str:
    return ".lsf"


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_SCHEDULERS: dict[str, dict] = {
    "slurm": {
        "submit": slurm_submit_cmd,
        "nodespec": slurm_nodespec,
        "query": slurm_query,
        "extension": slurm_extension,
    },
    "torque": {
        "submit": torque_submit_cmd,
        "nodespec": torque_nodespec,
        "query": torque_query,
        "extension": torque_extension,
    },
    "cletorque": {
        "submit": torque_submit_cmd,
        "nodespec": torque_nodespec,
        "query": torque_query,
        "extension": torque_extension,
    },
    "pbspro": {
        "submit": torque_submit_cmd,
        "nodespec": torque_nodespec,
        "query": torque_query,
        "extension": torque_extension,
    },
    "lsf": {
        "submit": lsf_submit_cmd,
        "nodespec": lsf_nodespec,
        "query": lsf_query,
        "extension": lsf_extension,
    },
    "moab": {
        "submit": torque_submit_cmd,
        "nodespec": torque_nodespec,
        "query": torque_query,
        "extension": torque_extension,
    },
}


def _get(cfg: "ClusterConfig") -> dict:
    adapter = _SCHEDULERS.get(cfg.batch_method)
    if adapter is None:
        raise ValueError(f"Unknown batch_method: {cfg.batch_method!r}")
    return adapter


def submit_cmd(script: str, cfg: "ClusterConfig") -> str:
    return _get(cfg)["submit"](script, cfg)


def nodespec(nodelist: list[str], cfg: "ClusterConfig") -> str:
    return _get(cfg)["nodespec"](nodelist, cfg)


def query(regex: str, cfg: "ClusterConfig") -> dict:
    return _get(cfg)["query"](regex, cfg)


def extension(cfg: "ClusterConfig") -> str:
    return _get(cfg)["extension"](cfg)
