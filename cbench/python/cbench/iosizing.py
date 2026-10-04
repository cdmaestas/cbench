"""Node-aware IO sizing for gen-jobs (consumes `cbench nodecheck` facts).

Rules (settled in design):
  * IO sizes round UP so each node writes >= 2x its RAM (defeats page cache);
    memory sizes round DOWN so they never exceed RAM.
  * IO sizing uses the MAX MemTotal from the facts file (cache-defeat holds on
    every node); CPU counts use the MIN. Thread/job counts for every IO
    benchmark come from io_threads(): all CPUs (logical or physical, per
    io_threads_basis), capped by io_threads_max if set.
  * If the rounded-up size does not fit the target (90% of the free space seen
    by nodecheck), it is capped to fit and a caveat is recorded.
  * Without a facts file, values come from cluster.yaml only if set there
    explicitly — the built-in defaults would silently mis-size jobs.

Template tokens produced (all via substitute(extra=...)):
  IOR_BLOCKSIZE   IOR -b value, e.g. "3840m"
  BONNIE_INSTANCES concurrent bonnie++ instances (= IO threads)
  BONNIE_SIZE_MB  bonnie++ -s per instance (MiB)
  BONNIE_RAM_MB   bonnie++ -r per instance (MiB)
  IO_REQUIRED_KB  space the job needs on its target, checked at run time
  IO_CAVEAT       non-empty when the size was capped (printed as CBENCH CAVEAT)
  IO_TARGET_DIR   configured target dir for the benchmark ("" if none)
  TESTDIR         overridden to the target dir for IOR when one is configured
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

IOR_TRANSFER_MIB = 128      # matches `-t 128m` in io_ior1mNtoN.in
CAPACITY_FRACTION = 0.9

# Which io_targets entry each benchmark writes to.
_TARGET_FOR = {"ior": "parallel", "mdtest": "parallel", "bonnie": "node-local", "fio": "node-local"}


class IOSizingError(Exception):
    """Node values needed for IO sizing are unavailable."""


def _shell_safe(text: str) -> str:
    """Caveats are substituted inside a double-quoted bash string in the job
    script; drop characters that bash would interpret there."""
    return "".join(c for c in text if c not in '"$`\\\n')


@dataclass
class NodeValues:
    cpus: Optional[int]             # MIN logical CPUs per node
    mem_io_kb: Optional[int]        # MAX MemTotal (IO sizing)
    mem_nonio_kb: Optional[int]     # MIN MemTotal (memory-sized benchmarks)
    targets: dict = field(default_factory=dict)  # name -> {path, fstype, shared, free_kb_min}
    source: str = "none"            # "nodefacts:<name>" | "cluster.yaml" | "none"
    warnings: list = field(default_factory=list)
    cores: Optional[int] = None     # MIN physical cores per node (facts v2), if known


def _resolve_targets(cfg, facts_targets: dict, warnings: list) -> dict:
    """cluster.yaml decides WHERE jobs write; facts only contribute free space
    and fstype, and only when nodecheck probed that same path."""
    out = {}
    for name, path in cfg.io_targets.items():
        t = facts_targets.get(name)
        if t and t.get("path") == path:
            out[name] = dict(t)
        else:
            if t:
                warnings.append(
                    f"io_target '{name}' is {path} but the facts file probed {t.get('path')}; "
                    "no free-space cap for it — re-run `cbench nodecheck`"
                )
            elif facts_targets is not None and facts_targets != {}:
                warnings.append(
                    f"io_target '{name}' was not probed by nodecheck; no free-space cap for it"
                )
            out[name] = {"path": path, "free_kb_min": None, "shared": None, "fstype": None}
    return out


def resolve_node_values(cfg, facts: Optional[dict] = None) -> NodeValues:
    """Pick node CPU/memory values from a facts file, else explicit config."""
    warnings: list[str] = []
    if facts:
        agg = facts["aggregate"]
        if facts.get("allow_heterogeneous") and facts.get("verdict", {}).get("heterogeneous"):
            warnings.append(
                f"nodefacts '{facts.get('name')}' is heterogeneous: IO sizing uses max MemTotal "
                f"({agg['memtotal_kb']['max']} kB), CPU counts use min ({agg['cpus']['min']})"
            )
        return NodeValues(
            cpus=agg["cpus"]["min"],
            cores=(agg.get("cores") or {}).get("min"),
            mem_io_kb=agg["memtotal_kb"]["max"],
            mem_nonio_kb=agg["memtotal_kb"]["min"],
            targets=_resolve_targets(cfg, agg.get("targets", {}), warnings),
            source=f"nodefacts:{facts.get('name', '?')}",
            warnings=warnings,
        )
    explicit = getattr(cfg, "explicit_keys", frozenset())
    cpus = cfg.procs_per_node if "procs_per_node" in explicit else None
    mem = cfg.memory_per_node_mb * 1024 if "memory_per_node_mb" in explicit else None
    src = "cluster.yaml" if (cpus or mem) else "none"
    return NodeValues(cpus=cpus, mem_io_kb=mem, mem_nonio_kb=mem,
                      targets=_resolve_targets(cfg, {}, warnings), source=src, warnings=warnings)


_PHYSICAL_FALLBACK = "io_threads_basis is physical but physical cores are unknown"


def cap_threads(count: int, cfg) -> int:
    """Apply the optional ``io_threads_max`` cap (never below 1)."""
    cap = getattr(cfg, "io_threads_max", None)
    return max(1, min(int(count), cap) if cap else int(count))


def io_threads(nv: NodeValues, cfg) -> int:
    """Thread/job count for IO benchmarks (fio jobs, bonnie instances, iozone
    threads, gpfsperf threads, mdtest top ppn): every CPU of the configured
    basis on the smallest node, capped by ``io_threads_max`` if set.

    ``io_threads_basis: physical`` uses physical cores when the facts file
    recorded them (schema v2), else falls back to logical CPUs with a warning
    appended to ``nv.warnings``.
    """
    if not nv.cpus:
        raise IOSizingError(
            "IO thread count needs node CPUs: pass --nodefacts NAME (from `cbench nodecheck`) "
            "or set procs_per_node explicitly in cluster.yaml"
        )
    count = nv.cpus
    if getattr(cfg, "io_threads_basis", "logical") == "physical":
        if nv.cores:
            count = nv.cores
        elif not any(w.startswith(_PHYSICAL_FALLBACK) for w in nv.warnings):
            nv.warnings.append(
                f"{_PHYSICAL_FALLBACK} (facts schema v1, cluster.yaml values, or no core ids in "
                "cpuinfo); using logical CPUs"
            )
    return cap_threads(count, cfg)


def target_name_for(benchmark: str) -> Optional[str]:
    for prefix, name in _TARGET_FOR.items():
        if benchmark.startswith(prefix):
            return name
    return None


def needs_io_sizing(testset: str, benchmark: str) -> bool:
    """IOR throughput tests and bonnie get 2x-memory sizing (iosanity stays small)."""
    if testset == "iosanity":
        return False
    return benchmark.startswith("ior") or benchmark == "bonnie"


def _require_mem(nv: NodeValues, testset: str, benchmark: str) -> int:
    if not nv.mem_io_kb:
        raise IOSizingError(
            f"{testset}_{benchmark} needs node memory for 2x-RAM sizing: pass "
            "--nodefacts NAME (from `cbench nodecheck`) or set memory_per_node_mb "
            "explicitly in cluster.yaml"
        )
    return nv.mem_io_kb


def _free_cap_kb(nv: NodeValues, target: Optional[str]) -> tuple[Optional[int], Optional[bool]]:
    t = nv.targets.get(target or "", {})
    free = t.get("free_kb_min")
    if not free:
        return None, t.get("shared")
    return int(free * CAPACITY_FRACTION), t.get("shared")


def ior_tokens(nv: NodeValues, *, ppn: int, numprocs: int, testset: str, benchmark: str) -> dict:
    """IOR -b so each node writes >= 2x RAM, rounded up to a multiple of -t."""
    mem_kb = _require_mem(nv, testset, benchmark)
    t = IOR_TRANSFER_MIB
    want_mib = 2 * mem_kb / 1024 / ppn
    b_mib = max(t, math.ceil(want_mib / t) * t)
    caveat = ""
    target = target_name_for(benchmark)
    cap_kb, shared = _free_cap_kb(nv, target)
    # aggregate written to the target: whole job on a shared fs, per node on local
    divisor = numprocs if shared else ppn
    if cap_kb is not None and b_mib * divisor * 1024 > cap_kb:
        capped = max(t, (cap_kb // 1024 // divisor) // t * t)
        caveat = (
            f"IOR block size capped to {capped}m (2x RAM needs {b_mib}m per rank) to fit "
            f"target '{target}' free space; results may be cache-influenced"
        )
        b_mib = capped
    tokens = {
        "IOR_BLOCKSIZE": f"{b_mib}m",
        "IO_REQUIRED_KB": str(b_mib * divisor * 1024),
        "IO_CAVEAT": _shell_safe(caveat),
    }
    return {**tokens, **target_tokens(nv, benchmark)}


def bonnie_tokens(nv: NodeValues, cfg, *, testset: str, benchmark: str) -> dict:
    """bonnie++ -s/-r so the concurrent instances (one per IO thread) write 2x
    RAM in aggregate.

    -s rounds up (IO), -r rounds down (memory); bonnie++ requires -s >= 2*-r.
    """
    mem_mib = _require_mem(nv, testset, benchmark) / 1024
    n = io_threads(nv, cfg)
    size = math.ceil(2 * mem_mib / n)
    ram = math.floor(mem_mib / n)
    caveat = ""
    target = target_name_for(benchmark)
    cap_kb, _shared = _free_cap_kb(nv, target)  # bonnie is single-node: per-node space
    if cap_kb is not None and size * n * 1024 > cap_kb:
        capped = max(1, cap_kb // 1024 // n)
        caveat = (
            f"bonnie++ size capped to {capped} MiB x {n} instances (2x RAM needs {size} MiB "
            f"x {n}) to fit target '{target}' free space; results may be cache-influenced"
        )
        size = capped
        ram = min(ram, size // 2)
    tokens = {
        "BONNIE_INSTANCES": str(n),
        "BONNIE_SIZE_MB": str(size),
        "BONNIE_RAM_MB": str(ram),
        "IO_REQUIRED_KB": str(size * n * 1024),
        "IO_CAVEAT": _shell_safe(caveat),
    }
    return {**tokens, **target_tokens(nv, benchmark)}


def fio_tokens(nv: NodeValues, cfg, *, testset: str, benchmark: str) -> tuple[dict, str]:
    """Tokens for iometadata_fio.in, plus a gen-time warning ("" if none).

    numjobs = io_threads (all CPUs, optional cap); the sequential block size comes from the
    fio profile and the target's fstype from the facts file. The run needs
    numjobs x the per-job file at its peak (the target is emptied between
    jobs); the job itself picks the O_DIRECT or buffered size after probing and
    runs its preflight with that. If the free space nodecheck saw cannot hold
    the O_DIRECT peak, the preflight will exit with a NOTICE, so warn now.
    """
    from cbench import fioprofile

    if not nv.cpus:
        raise IOSizingError(
            f"{testset}_{benchmark} sizes its job count from node CPUs: pass --nodefacts NAME "
            "(from `cbench nodecheck`) or set procs_per_node explicitly in cluster.yaml"
        )
    njobs = fioprofile.numjobs(io_threads(nv, cfg))
    target = target_name_for(benchmark)
    fstype = nv.targets.get(target or "", {}).get("fstype")
    profile, seq_bs = fioprofile.seq_block_size(cfg.fio_profile, fstype, cfg.fio_seq_bs)
    need_kb = fioprofile.peak_bytes(njobs) // 1024
    warning = ""
    cap_kb, _shared = _free_cap_kb(nv, target)
    if cap_kb is not None and need_kb > cap_kb:
        warning = (f"fio needs {need_kb} kB ({njobs} jobs x {fioprofile.DATA_SIZE}) on target "
                   f"'{target}' but nodecheck saw {cap_kb} kB usable; the job will exit with a "
                   "NOTICE unless space is freed")
    tokens = {
        "FIO_NUMJOBS": str(njobs),
        "FIO_RUNTIME": str(cfg.fio_runtime_s),
        "FIO_PROFILE": profile,
        "FIO_SEQ_BS": seq_bs,
        "FIO_SIZE_DIRECT_MB": str(fioprofile.DATA_SIZE_BYTES // 1024 ** 2),
        "FIO_SIZE_BUFFERED_MB": str(fioprofile.BUFFERED_FALLBACK_SIZE_BYTES // 1024 ** 2),
        "FIO_MD_NRFILES": str(fioprofile.MD_NRFILES),
        "IO_CAVEAT": "",
    }
    return {**tokens, **target_tokens(nv, benchmark)}, warning


def target_tokens(nv: NodeValues, benchmark: str) -> dict:
    """IO_TARGET_DIR (and TESTDIR for IOR) from the configured io_targets."""
    target = target_name_for(benchmark)
    path = nv.targets.get(target or "", {}).get("path") if target else None
    if not path:
        return {"IO_TARGET_DIR": ""}
    tokens = {"IO_TARGET_DIR": path}
    if benchmark.startswith("ior"):
        tokens["TESTDIR"] = path
    return tokens


def ppn_levels_for_metadata(configured: list[int], procs_per_node: int, cpus: int) -> list[int]:
    """Make the measured CPU count the top ppn level for metadata tests.

    Replaces the config's procs_per_node level with the measured count and drops
    levels above it (they would oversubscribe the nodes); the rest of the sweep stays.
    """
    levels = {v for v in configured if v != procs_per_node and v <= cpus}
    levels.add(cpus)
    return sorted(levels)
