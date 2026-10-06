"""Builder for NAS Parallel Benchmarks (NPB) MPI suite.

Builds the MPI class-B variants of all standard benchmarks by default.
Override via extra={'class': 'C', 'suites': 'BT CG EP FT IS LU MG SP'}.

Example:
  cbench build npb --extra class=C
  cbench build npb --extra "class=A suites=EP FT"
"""

from __future__ import annotations

from pathlib import Path

from cbench.builders import BenchmarkBuilder, BuildConfig
from cbench.builders._util import console, run, require, wget_tarball, install_bins

_TARBALL_URL = "https://www.nas.nasa.gov/assets/npb/NPB3.4.4.tar.gz"

_DEFAULT_SUITES = ["BT", "CG", "EP", "FT", "IS", "LU", "MG", "SP"]
_DEFAULT_CLASS = "B"


#: make.def lines cbench sets; everything else comes from NPB's own template
_MAKE_DEF_KEYS = ("MPIFC", "MPICC", "FFLAGS", "CFLAGS")


def _write_make_def(src: Path, cfg: BuildConfig) -> None:
    """Write config/make.def for the NPB MPI suite from NPB's own
    config/make.def.template, overriding only the compiler and flag lines.

    NPB 3.4 names the MPI Fortran compiler MPIFC (FLINK = $(MPIFC)) and writes
    binaries to $(BINDIR), both set in the template; a hand-written make.def
    that used MPIF77 and no BINDIR left the Fortran suites without a compiler
    and BINDIR empty (binaries aimed at /)."""
    values = {"MPIFC": cfg.mpif90, "MPICC": cfg.mpicc,
              "FFLAGS": cfg.fflags, "CFLAGS": cfg.cflags}
    config = src / "config"
    config.mkdir(exist_ok=True)
    template = config / "make.def.template"
    if not template.is_file():
        raise RuntimeError(f"{template} not found: not an NPB 3.4 MPI source tree")
    out, seen = [], set()
    for line in template.read_text().splitlines():
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else ""
        if key in values:
            out.append(f"{key} = {values[key]}")
            seen.add(key)
        else:
            out.append(line)
    missing = [k for k in _MAKE_DEF_KEYS if k not in seen]
    if missing:
        raise RuntimeError(f"{template} has no {', '.join(missing)} line(s); NPB layout changed?")
    make_def = config / "make.def"
    make_def.write_text("\n".join(out) + "\n")
    console.print(f"  [cyan]wrote[/cyan] {make_def} (from make.def.template)")


class NpbBuilder(BenchmarkBuilder):
    name = "npb"
    description = "NAS Parallel Benchmarks MPI suite (BT, CG, EP, FT, IS, LU, MG, SP)"
    source_url = _TARBALL_URL
    latest_page = "https://www.nas.nasa.gov/software/npb.html"
    latest_pattern = r"(?<![A-Za-z])NPB(?P<v>\d+(?:\.\d+)+)\.tar\.gz"

    def fetch(self, srcdir: Path, *, force: bool = False, dry_run: bool = False) -> Path:
        top = wget_tarball(_TARBALL_URL, srcdir / "npb", force=force, dry_run=dry_run)
        return top / "NPB3.4-MPI"

    def build(self, src: Path, prefix: Path, cfg: BuildConfig, *, dry_run: bool = False) -> list[str]:
        npb_class = cfg.extra.get("class", _DEFAULT_CLASS).upper()
        suite_str = cfg.extra.get("suites", " ".join(_DEFAULT_SUITES))
        suites = suite_str.upper().split()

        if not dry_run:
            _write_make_def(src, cfg)
        else:
            console.print("  [dim]Would write config/make.def[/dim]")

        installed = []
        for suite in suites:
            run(
                ["make", suite, f"CLASS={npb_class}", f"-j{cfg.jobs}"],
                cwd=src, dry_run=dry_run,
            )
            # NPB 3.4 writes lowercase binaries: bin/ep.B.x, bin/bt.B.x
            binary_name = f"{suite.lower()}.{npb_class}.x"
            installed += install_bins(
                src / "bin", prefix / "bin",
                [binary_name], dry_run=dry_run,
            )

        return installed

    def check_requires(self) -> list[str]:
        return require("mpicc", "mpif90", "make")
