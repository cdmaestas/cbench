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
    sys.exit('click-man is not installed. Run: pip install "click-man>=0.4"')

from importlib.metadata import PackageNotFoundError, version  # noqa: E402

import click  # noqa: E402

from cbench.cli.main import cli  # noqa: E402 — deliberately after the click-man check

try:
    cbench_version = version("cbench")
except PackageNotFoundError:
    # without it every page's footer reads "None"
    sys.exit("cbench is not installed (importlib.metadata can't find its version)")


def first_sentence(text: str) -> str:
    """The help text's first sentence, unwrapped: the man page NAME line.
    Click would cut it at 45 characters with "..."."""
    para = " ".join(text.strip().split("\n\n", 1)[0].split())
    end = para.find(". ")
    return para if end == -1 else para[:end + 1]


def prepare(cmd: click.Command) -> None:
    """Full NAME lines, and no "\\b" lines: Click's don't-rewrap marker for
    --help, which click-man would copy into the page as a raw control character."""
    if cmd.help:
        cmd.help = "\n".join(line for line in cmd.help.splitlines() if line.strip() != "\b")
        if not cmd.short_help:
            cmd.short_help = first_sentence(cmd.help)
    if isinstance(cmd, click.Group):
        for sub in cmd.commands.values():
            prepare(sub)


prepare(cli)
write_man_pages("cbench", cli, version=cbench_version, target_dir=str(target))
print(f"Man pages written to {target}/")
