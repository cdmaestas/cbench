"""Parse filters for detecting errors in benchmark job output.

Each filter module exposes a ``FILTERS`` dict mapping a regex pattern (str)
to a message template (str).  Template strings may reference ``$1``, ``$2``,
... to substitute regex capture groups — same convention as the original Perl
modules.

Usage::

    from cbench.parse_filters import build_filter_set, apply_filters

    filters = build_filter_set(["openmpi", "slurm", "misc"])
    errors  = apply_filters(filters, stdout_text)
"""

from __future__ import annotations

import re
import importlib
from typing import Iterator

# Registry: name -> module attribute dict
_MODULES: dict[str, str] = {
    "cray": "cbench.parse_filters.cray",
    "misc": "cbench.parse_filters.misc",
    "mpiexec": "cbench.parse_filters.mpiexec",
    "mvapich": "cbench.parse_filters.mvapich",
    "openmpi": "cbench.parse_filters.openmpi",
    "slurm": "cbench.parse_filters.slurm",
    "torque": "cbench.parse_filters.torque",
}

AVAILABLE = list(_MODULES.keys())


def build_filter_set(names: list[str]) -> dict[str, str]:
    """Return a merged pattern→template dict from the requested filter modules."""
    merged: dict[str, str] = {}
    for name in names:
        if name not in _MODULES:
            raise ValueError(f"Unknown parse filter module: {name!r}. Available: {AVAILABLE}")
        mod = importlib.import_module(_MODULES[name])
        merged.update(mod.FILTERS)
    return merged


def _expand_template(template: str, m: re.Match) -> str:
    """Replace $1, $2, ... in template with regex capture groups."""
    result = template
    for i, group in enumerate(m.groups(), start=1):
        result = result.replace(f"${i}", group or "")
    return result


def apply_filters(filters: dict[str, str], text: str) -> list[str]:
    """Scan *text* line-by-line and return a list of matched error strings."""
    errors: list[str] = []
    for line in text.splitlines():
        for pattern, template in filters.items():
            m = re.search(pattern, line)
            if m:
                errors.append(_expand_template(template, m))
                break  # first matching filter wins per line
    return errors
