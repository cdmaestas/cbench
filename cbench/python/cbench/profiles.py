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

Custom profiles come from ``io_profiles`` in cluster.yaml::

    io_profiles:
      scratch-check:
        description: fio and IOR against the parallel filesystem
        default_groups: [parallel]          # default: every group
        groups:
          parallel:
            target: parallel                # io_targets key every member writes to
            suffix: par                     # job names fio-par-...; default: group name
            members: [iometadata_fio, io_ior1mNtoN]   # <home testset>_<benchmark>

In a custom group the target decides where every member writes (fio on GPFS,
or on an extra ``io_targets.nvme``), with sizing and free-space caps from that
target; built-in groups keep each benchmark's usual target (``target=None`` on
the member). A custom profile may not reuse a built-in name.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Member:
    home: str        # testset whose template is used, e.g. "iometadata"
    benchmark: str   # template benchmark name, e.g. "fio"


@dataclass(frozen=True)
class Group:
    target: str                    # io_targets key the group writes to
    suffix: str                    # job-name qualifier: fio -> fio-<suffix>
    members: tuple[Member, ...]
    #: custom groups send every member to ``target``; built-in groups leave
    #: each benchmark on its usual target (iosizing.target_name_for)
    route_members: bool = False


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
            # multi-node gpfsperf-mpi, one job per node count; opt-in like gpfs
            "gpfs-mpi": Group("gpfs", "gpfsmpi", (
                Member("iogpfs", "gpfsperfmpi"),
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


def custom_profiles(io_profiles: dict, templates_dir: Path | None = None) -> dict[str, Profile]:
    """Profiles from cluster.yaml ``io_profiles`` (structure already checked by
    the config schema). Raises ProfileError for a built-in name, an unknown
    default group, a member with no template, or two members that would get
    the same job name."""
    out: dict[str, Profile] = {}
    for name, spec in (io_profiles or {}).items():
        if name in PROFILES:
            raise ProfileError(f"io_profiles.{name} reuses a built-in profile name; rename it "
                               f"(built-in: {', '.join(sorted(PROFILES))})")
        groups: dict[str, Group] = {}
        job_names: dict[str, str] = {}
        for gname, g in spec["groups"].items():
            suffix = g.get("suffix") or gname
            members = []
            for ref in g["members"]:
                home, _, bench = ref.partition("_")
                if templates_dir is not None and not (templates_dir / f"{ref}.in").is_file():
                    raise ProfileError(f"io_profiles.{name}.groups.{gname}: no template {ref}.in "
                                       f"in {templates_dir}")
                job = f"{bench}-{suffix}"
                if job in job_names:
                    raise ProfileError(f"io_profiles.{name}: {ref} in group '{gname}' and "
                                       f"{job_names[job]} would both be named {job}-*; give the "
                                       "groups different suffixes")
                job_names[job] = f"group '{gname}'"
                members.append(Member(home, bench))
            groups[gname] = Group(g["target"], suffix, tuple(members), route_members=True)
        defaults = tuple(spec.get("default_groups") or groups)
        unknown = [g for g in defaults if g not in groups]
        if unknown:
            raise ProfileError(f"io_profiles.{name}.default_groups: unknown group(s) "
                               f"{', '.join(unknown)}; available: {', '.join(groups)}")
        out[name] = Profile(spec.get("description", "custom profile from cluster.yaml"),
                            groups, defaults)
    return out


def get_profile(name: str, io_profiles: dict | None = None,
                templates_dir: Path | None = None) -> Profile:
    """A built-in profile, or a custom one from cluster.yaml ``io_profiles``."""
    available = {**PROFILES, **custom_profiles(io_profiles or {}, templates_dir)}
    try:
        return available[name]
    except KeyError:
        raise ProfileError(
            f"unknown profile {name!r}; available: {', '.join(sorted(available))}"
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
