"""Job script template building and substitution.

Loads the original ``*.in`` template files and performs keyword substitution
equivalent to the Perl ``std_substitute()`` function (cbench.pl:2474).

Uses Jinja2 for substitution after converting ``TOKEN_HERE`` → ``{{ TOKEN }}``.
"""

from __future__ import annotations

import math
import os
import re
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from jinja2 import Environment, Undefined

if TYPE_CHECKING:
    from cbench.config import ClusterConfig

# Run sizes matching the Perl @run_sizes array in cbench.pl
RUN_SIZES = [
    1, 2, 4, 8, 9, 16, 25, 32, 36, 49, 64, 72, 81, 96, 100, 110, 112, 121,
    128, 144, 168, 196, 200, 225, 240, 256, 288, 320, 324, 336, 360, 392,
    400, 441, 480, 484, 500, 512, 576, 600, 625, 648, 676, 720, 784, 800,
    900, 960, 1000, 1024, 1152, 1200, 1296, 1440, 1600, 1764, 2000, 2048,
    2304, 2500, 2916, 3000, 3136, 3600, 4000, 4096,
]


def _templates_dir() -> Path:
    for env in ("CBENCHOME", "CBENCHSTANDALONEDIR"):
        val = os.environ.get(env)
        if val:
            p = Path(val) / "templates"
            if p.is_dir():
                return p
    # Try relative to this file's repo layout
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "templates"
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("Cannot locate cbench templates/ directory")


def _load_template_text(name: str) -> str:
    """Load raw text of a template file (*.in) from the templates/ dir."""
    path = _templates_dir() / name
    return path.read_text()


def _here_to_jinja(text: str) -> str:
    """Convert ``TOKEN_HERE`` markers to ``{{ TOKEN }}`` Jinja2 variables."""
    return re.sub(r"\b([A-Z][A-Z0-9_]+)_HERE\b", r"{{ \1 }}", text)


def _make_env() -> Environment:
    return Environment(
        variable_start_string="{{ ",
        variable_end_string=" }}",
        undefined=Undefined,
        keep_trailing_newline=True,
    )


# ---------------------------------------------------------------------------
# Walltime helpers (port of walltime logic from cbench_gen_jobs.pl)
# ---------------------------------------------------------------------------

def _parse_walltime(wt: str) -> int:
    """Parse HH:MM:SS → total minutes."""
    parts = wt.split(":")
    h, m, s = int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0
    return h * 60 + m + s // 60


def _format_walltime(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    return f"{h:02d}:{m:02d}:00"


def compute_walltime(numprocs: int, run_sizes: list[int], cfg: "ClusterConfig") -> str:
    if cfg.walltime_method == 0:
        return cfg.default_walltime
    base = _parse_walltime(cfg.default_walltime)
    try:
        idx = sorted(run_sizes).index(numprocs)
    except ValueError:
        idx = 0
    return _format_walltime(base + idx * cfg.walltime_steptime)


# ---------------------------------------------------------------------------
# Template assembly
# ---------------------------------------------------------------------------

_BATCH_HEADERS = {
    "slurm": "slurm_header.in",
    "torque": "torque_header.in",
    "cletorque": "torque_header.in",
    "pbspro": "torque_header.in",
    "lsf": "lsf_header.in",
    "moab": "torque_header.in",
    "loadleveler": "torque_header.in",
}

_OPTIONAL_TEMPLATES = [
    "preamble_header.in",
    "common_footer.in",
]


def build_job_template(
    testset: str,
    benchmark: str,
    run_type: str,
    cfg: "ClusterConfig",
) -> str:
    """Assemble and return the raw (un-substituted) template text.

    Mirrors ``build_job_templates()`` in cbench.pl:812.
    Concatenates: batch_header + preamble? + common_header + benchmark.in + common_footer?
    """
    parts: list[str] = []

    if run_type == "batch":
        header_file = _BATCH_HEADERS.get(cfg.batch_method)
        if header_file:
            parts.append(_load_template_text(header_file))
    else:
        parts.append(_load_template_text("interactive_header.in"))

    # Optional preamble
    try:
        parts.append(_load_template_text("preamble_header.in"))
    except FileNotFoundError:
        pass

    parts.append(_load_template_text("common_header.in"))

    # Benchmark-specific template: testset_benchmark.in
    parts.append(_load_template_text(f"{testset}_{benchmark}.in"))

    try:
        parts.append(_load_template_text("common_footer.in"))
    except FileNotFoundError:
        pass

    return "\n".join(parts)


def substitute(
    template_text: str,
    *,
    numprocs: int,
    ppn: int,
    numnodes: int,
    walltime: str,
    jobname: str,
    benchmark: str,
    testset: str,
    ident: str,
    run_type: str,
    launch_cmd: str,
    cfg: "ClusterConfig",
    cbenchtest: str = "",
    omp_threads: int = 1,
    extra: Optional[dict] = None,
) -> str:
    """Perform keyword substitution on assembled template text.

    Mirrors ``std_substitute()`` in cbench.pl:2474.
    """
    from cbench import schedulers

    cbenchtest_path = cbenchtest or os.environ.get("CBENCHTEST", "")
    testset_path = str(Path(cbenchtest_path) / testset) if cbenchtest_path else testset
    bin_path = str(Path(cbenchtest_path) / "bin") if cbenchtest_path else "bin"

    # Build scheduler-specific nodespec (empty for most cases in gen phase)
    slurm_nodespec = f"-N {numnodes} --ntasks-per-node {ppn}"

    vars: dict = {
        # Resource counts
        "NUM_PROCS": str(numprocs),
        "NUM_NODES": str(numnodes),
        "NUM_PPN": str(ppn),
        "NUM_THREADS_PER_PROCESS": str(omp_threads),
        # Walltime
        "WALLTIME": walltime,
        # Job identity
        "JOBNAME": jobname,
        "BENCHMARK_NAME": benchmark,
        "TESTSET_NAME": testset,
        "IDENT": ident,
        # Paths
        "BENCH_HOME": os.environ.get("CBENCHOME", ""),
        "BENCH_TEST": cbenchtest_path,
        "CBENCHTEST": cbenchtest_path,
        "TESTSET_PATH": testset_path,
        "CBENCHTEST_BIN": bin_path,
        "TESTDIR": cbenchtest_path,
        "SCRATCHDIR": cbenchtest_path,
        "JOBSCRIPT": f"{jobname}.{schedulers.extension(cfg).lstrip('.')}",
        # Launch
        "JOBLAUNCH_CMD": launch_cmd,
        "JOBLAUNCHMETHOD": cfg.joblaunch_method,
        # Batch scheduler-specific
        "SLURM_NODESPEC": slurm_nodespec,
        "TORQUE_NODESPEC": f"{numnodes}:ppn={ppn}",
        # Run type
        "RUN_TYPE": run_type.upper(),
        # Misc
        "MEM_UTIL_FACTORS": ",".join(str(f) for f in cfg.memory_util_factors),
        "PREAMBLE": "",
        "XHPL_BIN": str(Path(bin_path) / "xhpl"),
        "HPCC_BIN": str(Path(bin_path) / "hpcc"),
    }
    if extra:
        vars.update(extra)

    jinja_text = _here_to_jinja(template_text)
    env = _make_env()
    tmpl = env.from_string(jinja_text)
    return tmpl.render(**vars)
