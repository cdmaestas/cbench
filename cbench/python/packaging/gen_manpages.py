#!/usr/bin/env python3
"""Generate man pages for the cbench CLI using click-man.

Usage:
    python3 gen_manpages.py <output-dir>

Produces one .1 file per Click command/subcommand under <output-dir>.
The Makefile installs click-man into a temporary --target dir and sets
PYTHONPATH so cbench is importable without a system-wide install.
"""

import sys
from pathlib import Path

target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("man/man1")
target.mkdir(parents=True, exist_ok=True)

try:
    from click_man.core import write_man_pages
except ImportError:
    sys.exit("click-man is not installed. Run: pip install click-man>=0.8")

from cbench.cli.main import cli

write_man_pages("cbench", cli, target_dir=str(target))
print(f"Man pages written to {target}/")
