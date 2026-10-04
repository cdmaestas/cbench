"""IO profiles: named bundles of benchmarks generated together as one testset.

A profile is a *virtual testset*: `cbench gen-jobs --profile io-default` renders
each member from its existing template (``<home testset>_<benchmark>.in``) but
writes every job under ``$CBENCHTEST/<profile>/<ident>/``, so start-jobs,
parse and query work unchanged with ``--testset <profile>``.

Members are grouped by the IO target class they exercise. Job names carry the
group (``fio-local-1ppn-1``) so one benchmark can appear in several groups;
``parsers.get_parser`` resolves ``fio-local`` back to the fio parser.

A group whose target is not available (``io_targets`` entry unset; for
``gpfs``, no ``io_targets.gpfs`` and no GPFS ``parallel`` target in the node
facts) is skipped with a warning.
Only the profile's default groups are generated unless ``--group`` names
others (or ``all``).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Member:
    home: str        # testset whose template is used, e.g. "iometadata"
    benchmark: str   # template benchmark name, e.g. "fio"


@dataclass(frozen=True)
class Group:
    target: str                    # io_targets key the group writes to
    suffix: str                    # job-name qualifier: fio -> fio-<suffix>
    members: tuple[Member, ...]


@dataclass(frozen=True)
class Profile:
    description: str
    groups: dict
    default_groups: tuple[str, ...]


PROFILES: dict[str, Profile] = {
    "io-default": Profile(
        description="node-local data/metadata IO by default; parallel and gpfs groups opt-in",
        groups={
            "node-local": Group("node-local", "local", (
                Member("iometadata", "fio"),
                Member("iometadata", "bonnie"),
                Member("iolocal", "iozone"),
            )),
            "parallel": Group("parallel", "parallel", (
                Member("io", "ior1mNtoN"),
                Member("iometadata", "mdtest"),
            )),
            # target: io_targets.gpfs, else io_targets.parallel when nodecheck
            # saw it is GPFS (iosizing._gpfs_alias)
            "gpfs": Group("gpfs", "gpfs", (
                Member("iogpfs", "gpfsperf"),
            )),
        },
        default_groups=("node-local",),
    ),
    "io500": Profile(
        description="IO500 on the parallel target, one job per node count at ppn = IO threads",
        groups={
            "parallel": Group("parallel", "parallel", (Member("io500", "io500"),)),
        },
        default_groups=("parallel",),
    ),
}


class ProfileError(Exception):
    """Unknown profile/group, or nothing left to generate."""


def get_profile(name: str) -> Profile:
    try:
        return PROFILES[name]
    except KeyError:
        raise ProfileError(
            f"unknown profile {name!r}; available: {', '.join(sorted(PROFILES))}"
        ) from None


def select_groups(profile: Profile, requested: tuple[str, ...]) -> list[str]:
    """Group names to generate: the profile defaults, ``all``, or the named ones."""
    if not requested:
        return list(profile.default_groups)
    if "all" in requested:
        return list(profile.groups)
    unknown = [g for g in requested if g not in profile.groups]
    if unknown:
        raise ProfileError(
            f"unknown group(s) {', '.join(unknown)}; available: all, {', '.join(profile.groups)}"
        )
    return list(dict.fromkeys(requested))


def job_benchmark(member: Member, group: Group) -> str:
    """Benchmark name used in the job name: ``<benchmark>-<group suffix>``."""
    return f"{member.benchmark}-{group.suffix}"
