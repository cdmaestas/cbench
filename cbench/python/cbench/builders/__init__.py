"""Benchmark build framework.

Each builder subclasses BenchmarkBuilder, sets ``name`` and ``description``,
and implements ``fetch()`` and ``build()``.  Auto-registration via
__init_subclass__ mirrors the parser registry pattern.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

REGISTRY: dict[str, type["BenchmarkBuilder"]] = {}


@dataclass
class BuildConfig:
    """Compiler and toolchain settings for a build."""
    cc: str = "cc"
    cxx: str = "c++"
    fc: str = "gfortran"
    mpicc: str = "mpicc"
    mpicxx: str = "mpicxx"
    mpif90: str = "mpif90"
    cflags: str = "-O3"
    fflags: str = "-O3"
    jobs: int = 4
    blas_lib: str = ""      # e.g. "-lopenblas" or "-L/path/to/blas -lblas"
    blas_inc: str = ""      # include dir for BLAS headers (HPL/HPCC)
    extra: dict = field(default_factory=dict)  # builder-specific knobs


class BenchmarkBuilder:
    """Base class for benchmark builders.

    Subclasses register into REGISTRY by setting ``name``.
    """

    name: str = ""
    description: str = ""

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if cls.name:
            REGISTRY[cls.name] = cls

    def fetch(self, srcdir: Path, *, force: bool = False, dry_run: bool = False) -> Path:
        """Download or clone the benchmark source into srcdir.

        Returns the path to the top-level source directory for this benchmark.
        """
        raise NotImplementedError

    def build(
        self,
        src: Path,
        prefix: Path,
        cfg: BuildConfig,
        *,
        dry_run: bool = False,
    ) -> list[str]:
        """Build from *src* and install binaries under *prefix/bin/*.

        Returns the list of binary names installed.
        """
        raise NotImplementedError

    def check_requires(self) -> list[str]:
        """Return list of missing system prerequisites (empty = all present)."""
        return []


def get_builder(name: str) -> "BenchmarkBuilder | None":
    cls = REGISTRY.get(name)
    return cls() if cls else None


# Auto-import all builder modules so their classes register themselves.
from cbench.builders import (  # noqa: F401 E402
    stream, imb, osu, ior, hpl, npb,
    hpcc, amg, hpccg, mpibench, mpigraph, bonnie, graph500,
    iozone,
)
