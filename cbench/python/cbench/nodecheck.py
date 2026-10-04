"""Node precheck: gather per-node facts, verify homogeneity, write a facts file.

`cbench nodecheck` runs a small probe script on every node of a pool (via pdsh,
or a serial ssh loop when pdsh is unavailable), parses the ``host: key=value``
output, checks that the pool is homogeneous, and writes
``$CBENCHTEST/nodefacts/<name>.json``. `gen-jobs` consumes that file so IO
sizing and IOPS proc counts reflect the real compute nodes rather than the
submit host it runs on.

Homogeneity policy:
  * logical CPU count (``processor`` lines in /proc/cpuinfo) must match exactly
  * MemTotal must agree within MEM_TOLERANCE (identical nodes differ by a few MB)
  * CPU model mismatch is a warning only
  * every IO target must exist on every node with the same fstype (hard error)
  * an unreachable node is a hard error (it cannot be verified)

With ``allow_heterogeneous`` the CPU/memory mismatch is downgraded to a warning
and consumers pick conservative values: IO sizing uses the MAX MemTotal (so
cache-defeat holds on every node), non-IO sizing uses the MIN MemTotal, and the
CPU count uses the MIN everywhere.
"""

from __future__ import annotations

import base64
import json
import os
import re
import shlex
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from cbench.hostlist import compress

SCHEMA_VERSION = 2          # v2 adds per-node physical cores ("cores")
SUPPORTED_SCHEMA_VERSIONS = (1, 2)
MEM_TOLERANCE = 0.02
STALE_DAYS = 30
CONNECT_TIMEOUT = 10
COMMAND_TIMEOUT = 120

_NAME_RE = re.compile(r"^[A-Za-z0-9_\-]+$")
_SHARED_FSTYPES = {"gpfs", "lustre", "panfs", "beegfs", "ceph", "glusterfs", "cifs", "smb3", "smbfs"}
_SENTINEL = "cbench_probe=ok"


class NodecheckError(Exception):
    """A precheck that cannot proceed or a facts file that cannot be used."""


# ---------------------------------------------------------------------------
# probe script + transport
# ---------------------------------------------------------------------------

def build_probe_script(targets: dict[str, str]) -> str:
    """Return the POSIX sh probe run on each node (prints key=value lines)."""
    lines = [
        'echo "cpus=$(grep -c ^processor /proc/cpuinfo)"',
        # physical cores = distinct (physical id, core id) pairs; 0 where
        # cpuinfo lacks them (some ARM/VMs) and logical CPUs are all we know
        "echo \"cores=$(awk -F': *' '/^physical id/{p=$2} /^core id/{print p\":\"$2}' "
        "/proc/cpuinfo | sort -u | wc -l | tr -d ' ')\"",
        "echo \"memtotal_kb=$(awk '/^MemTotal:/{print $2}' /proc/meminfo)\"",
        "echo \"model=$(awk -F': ' '/^model name/{print $2; exit}' /proc/cpuinfo)\"",
    ]
    for name, path in sorted(targets.items()):
        q = shlex.quote(path)
        lines += [
            f"if [ -d {q} ]; then",
            f"  fs=$(findmnt -n -o FSTYPE -T {q} 2>/dev/null | head -1)",
            f'  [ -n "$fs" ] || fs=$(stat -f -c %T {q} 2>/dev/null)',
            f"  free=$(df -Pk {q} 2>/dev/null | awk 'NR==2{{print $4}}')",
            "else",
            "  fs=MISSING; free=0",
            "fi",
            f'echo "target.{name}.fstype=${{fs:-MISSING}}"',
            f'echo "target.{name}.free_kb=${{free:-0}}"',
        ]
    lines.append(f'echo "{_SENTINEL}"')
    return "\n".join(lines) + "\n"


def _b64(script: str) -> str:
    return base64.b64encode(script.encode()).decode()


def remote_shell_command(script: str) -> str:
    """Command string for a remote login shell (ssh / pdsh -R ssh).

    The script travels base64-encoded inside single quotes, so it survives any
    login shell (bash, tcsh) and pdsh's joining of arguments with spaces.
    """
    return "sh -c " + shlex.quote(f"echo {_b64(script)} | base64 -d | sh")


def exec_command_suffix(script: str) -> list[str]:
    """argv tail for pdsh -R exec. Contains no literal whitespace inside the
    sh -c payload (${IFS} is expanded by sh), so it works whether pdsh passes
    the arguments through or re-splits them on whitespace."""
    return ["sh", "-c", f"echo${{IFS}}{_b64(script)}|base64${{IFS}}-d|sh"]


def build_pdsh_argv(
    hosts_expr: str, script: str, *, rcmd: str, exec_cmd: str, extraargs: str
) -> list[str]:
    argv = ["pdsh", "-R", rcmd, "-t", str(CONNECT_TIMEOUT), "-u", str(COMMAND_TIMEOUT)]
    argv += shlex.split(extraargs) if extraargs else []
    argv += ["-w", hosts_expr]
    if rcmd == "exec":
        if "%h" not in exec_cmd:
            raise NodecheckError(
                "remotecmd_rcmd is 'exec' but remotecmd_exec_cmd does not contain %h "
                "(e.g. 'srun -N1 -n1 -w %h'); without it every host would run locally"
            )
        # The exec template must pass argv through unchanged (srun, docker exec,
        # env, ...). ssh/rsh re-join argv into a shell string, which splits the
        # probe pipeline in the wrong place — and -R ssh already covers them.
        first = os.path.basename(shlex.split(exec_cmd)[0]) if exec_cmd.strip() else ""
        if first in {"ssh", "rsh", "mrsh"}:
            raise NodecheckError(
                f"remotecmd_exec_cmd starts with '{first}'; use remotecmd_rcmd: ssh instead "
                "(exec templates must pass argv through, e.g. 'srun -N1 -n1 -w %h')"
            )
        argv += shlex.split(exec_cmd) + exec_command_suffix(script)
    else:
        argv.append(remote_shell_command(script))
    return argv


def check_pdsh_rcmd(rcmd: str, runner: Callable = subprocess.run) -> None:
    """Verify pdsh is installed and provides the requested rcmd module."""
    try:
        res = runner(["pdsh", "-V"], capture_output=True, text=True, timeout=30)
    except FileNotFoundError as e:
        raise NodecheckError(
            "pdsh is not installed. Install pdsh (plus pdsh-rcmd-ssh / pdsh-rcmd-exec) "
            "or set remotecmd_method: ssh in cluster.yaml"
        ) from e
    text = (res.stdout or "") + (res.stderr or "")
    m = re.search(r"rcmd modules:\s*([^\n(]+)", text)
    modules = [x.strip() for x in m.group(1).split(",")] if m else []
    if rcmd not in modules:
        raise NodecheckError(
            f"pdsh rcmd module '{rcmd}' is not available (have: {', '.join(modules) or 'none'}). "
            f"Install the pdsh-rcmd-{rcmd} package."
        )


def run_pdsh(argv: list[str], runner: Callable = subprocess.run) -> tuple[str, str]:
    try:
        res = runner(argv, capture_output=True, text=True, timeout=COMMAND_TIMEOUT + 300)
    except subprocess.TimeoutExpired as e:
        raise NodecheckError(f"pdsh did not finish within {COMMAND_TIMEOUT + 300}s") from e
    # pdsh exits nonzero when any host fails; unreachable hosts are detected
    # from the parsed output instead.
    return res.stdout or "", res.stderr or ""


def run_ssh_loop(hosts: list[str], script: str, runner: Callable = subprocess.run) -> tuple[str, str]:
    """Serial ssh fallback; emits pdsh-style 'host: line' output."""
    out: list[str] = []
    err: list[str] = []
    cmd = remote_shell_command(script)
    for host in hosts:
        try:
            res = runner(
                ["ssh", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={CONNECT_TIMEOUT}", host, cmd],
                capture_output=True, text=True, timeout=COMMAND_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            err.append(f"{host}: timed out after {COMMAND_TIMEOUT}s")
            continue
        out += [f"{host}: {line}" for line in (res.stdout or "").splitlines()]
        if res.returncode != 0:
            err.append(f"{host}: ssh exited {res.returncode}: {(res.stderr or '').strip()}")
    return "\n".join(out), "\n".join(err)


# ---------------------------------------------------------------------------
# parsing + analysis
# ---------------------------------------------------------------------------

def parse_output(text: str) -> dict[str, dict[str, str]]:
    """Parse 'host: key=value' lines into {host: {key: value}}."""
    facts: dict[str, dict[str, str]] = {}
    for line in text.splitlines():
        host, sep, rest = line.partition(": ")
        host = host.strip()
        if not sep or not host or " " in host or "@" in host:
            continue  # not a host-prefixed line (e.g. pdsh@node: diagnostics)
        if rest.strip() == _SENTINEL:
            facts.setdefault(host, {})["_complete"] = "1"
            continue
        key, eq, value = rest.partition("=")
        if eq:
            facts.setdefault(host, {})[key.strip()] = value.strip()
    return facts


def _is_shared(fstype: str) -> bool:
    return fstype in _SHARED_FSTYPES or fstype.startswith("nfs") or fstype.startswith("fuse.")


def _int(value: str | None) -> int | None:
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _groups_by(values: dict[str, object]) -> str:
    """'48: zima[1-4]; 16: zimabg[1-2]' for a {host: value} map."""
    inv: dict[object, list[str]] = {}
    for host, v in values.items():
        inv.setdefault(v, []).append(host)
    ordered = sorted(inv.items(), key=lambda kv: (-len(kv[1]), str(kv[0])))
    return "; ".join(f"{v}: {compress(hs)}" for v, hs in ordered)


def analyze(
    expected: list[str],
    per_host: dict[str, dict[str, str]],
    targets: dict[str, str],
    *,
    allow_heterogeneous: bool = False,
) -> dict:
    """Return {'aggregate': ..., 'verdict': ..., 'responded': [...]}."""
    errors: list[str] = []
    warnings: list[str] = []

    responded = sorted(
        h for h in expected
        if per_host.get(h, {}).get("_complete") == "1" and _int(per_host[h].get("cpus")) is not None
    )
    unreachable = [h for h in expected if h not in responded]
    if unreachable:
        errors.append(
            f"unreachable or incomplete probe on {compress(unreachable)} — fix the node(s) "
            "or exclude them with --ignore"
        )

    aggregate: dict = {"cpus": None, "cores": None, "memtotal_kb": None, "models": [], "targets": {}}
    heterogeneous = False

    if responded:
        cpus = {h: _int(per_host[h]["cpus"]) for h in responded}
        mem = {h: _int(per_host[h].get("memtotal_kb")) or 0 for h in responded}
        models = {h: per_host[h].get("model", "") for h in responded}
        aggregate["cpus"] = {"min": min(cpus.values()), "max": max(cpus.values())}
        cores = {h: _int(per_host[h].get("cores")) or 0 for h in responded}
        if all(cores.values()):
            aggregate["cores"] = {"min": min(cores.values()), "max": max(cores.values())}
        aggregate["memtotal_kb"] = {"min": min(mem.values()), "max": max(mem.values())}
        aggregate["models"] = sorted(set(models.values()))

        if len(set(cpus.values())) > 1:
            heterogeneous = True
            errors_or_warn = f"CPU count differs: {_groups_by(cpus)}"
            (warnings if allow_heterogeneous else errors).append(errors_or_warn)
        elif aggregate["cores"] and aggregate["cores"]["min"] != aggregate["cores"]["max"]:
            # same logical count, different physical cores: SMT on some nodes only
            heterogeneous = True
            msg = f"physical core count differs (SMT setting?): {_groups_by(cores)}"
            (warnings if allow_heterogeneous else errors).append(msg)
        mmax = aggregate["memtotal_kb"]["max"]
        if mmax and (mmax - aggregate["memtotal_kb"]["min"]) / mmax > MEM_TOLERANCE:
            heterogeneous = True
            gib = {h: f"{v / 1048576:.1f}GiB" for h, v in mem.items()}
            msg = f"MemTotal differs by more than {MEM_TOLERANCE:.0%}: {_groups_by(gib)}"
            (warnings if allow_heterogeneous else errors).append(msg)
        if len(aggregate["models"]) > 1:
            warnings.append(f"CPU model differs: {_groups_by(models)}")

        if heterogeneous:
            if allow_heterogeneous:
                warnings.append(
                    "heterogeneous node set allowed — conservative values: IO sizing uses "
                    f"max MemTotal ({mmax} kB), non-IO sizing uses min MemTotal "
                    f"({aggregate['memtotal_kb']['min']} kB), CPU count uses min "
                    f"({aggregate['cpus']['min']})"
                )
            else:
                errors.append(
                    "node set is heterogeneous — run nodecheck per hardware type, exclude "
                    "outliers with --ignore, or pass --allow-heterogeneous"
                )

        for name, path in sorted(targets.items()):
            fs = {h: per_host[h].get(f"target.{name}.fstype", "MISSING") or "MISSING" for h in responded}
            free = {h: _int(per_host[h].get(f"target.{name}.free_kb")) or 0 for h in responded}
            missing = [h for h, v in fs.items() if v == "MISSING"]
            if missing:
                errors.append(f"IO target '{name}' ({path}) missing on {compress(missing)}")
            present = {h: v for h, v in fs.items() if v != "MISSING"}
            if len(set(present.values())) > 1:
                errors.append(f"IO target '{name}' ({path}) has mixed fstypes: {_groups_by(present)}")
            uniform = next(iter(set(present.values()))) if len(set(present.values())) == 1 else None
            aggregate["targets"][name] = {
                "path": path,
                "fstype": uniform,
                "shared": bool(uniform and _is_shared(uniform)),
                "free_kb_min": min(free.values()),
            }

    verdict = {
        "ok": not errors,
        "heterogeneous": heterogeneous,
        "errors": errors,
        "warnings": warnings,
    }
    return {"aggregate": aggregate, "verdict": verdict, "responded": responded}


def group_summary(per_host: dict[str, dict[str, str]], responded: list[str], targets: dict[str, str]) -> list[dict]:
    """dshbak -c style grouping: hosts with identical facts collapse together."""
    groups: dict[tuple, list[str]] = {}
    for h in responded:
        f = per_host[h]
        key = (
            f.get("cpus", ""),
            f.get("cores", ""),
            f.get("model", ""),
            tuple(f.get(f"target.{n}.fstype", "MISSING") for n in sorted(targets)),
        )
        groups.setdefault(key, []).append(h)
    rows = []
    for (cpus, cores, model, fstypes), hosts in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        mems = [(_int(per_host[h].get("memtotal_kb")) or 0) / 1048576 for h in hosts]
        mem = f"{min(mems):.1f}" if max(mems) - min(mems) < 0.05 else f"{min(mems):.1f}-{max(mems):.1f}"
        rows.append({
            "hosts": compress(hosts),
            "count": len(hosts),
            "cpus": cpus,
            "cores": cores if cores not in ("", "0") else "?",
            "mem_gib": mem,
            "model": model,
            "targets": dict(zip(sorted(targets), fstypes)),
        })
    return rows


# ---------------------------------------------------------------------------
# facts file
# ---------------------------------------------------------------------------

def facts_path(cbenchtest: str | Path, name: str) -> Path:
    if not _NAME_RE.match(name):
        raise NodecheckError(f"Invalid facts name {name!r} (allowed: letters, digits, _ and -)")
    base = (Path(cbenchtest) / "nodefacts").resolve()
    path = (base / f"{name}.json").resolve()
    if not path.is_relative_to(base):
        raise NodecheckError(f"facts name {name!r} escapes {base}")
    return path


def build_facts(
    *,
    name: str,
    nodelist: str,
    ignored: list[str],
    transport: dict,
    allow_heterogeneous: bool,
    per_host: dict[str, dict[str, str]],
    result: dict,
    now: datetime | None = None,
) -> dict:
    now = now or datetime.now(timezone.utc)
    responded = result["responded"]
    return {
        "schema_version": SCHEMA_VERSION,
        "name": name,
        "created": now.isoformat(),
        "nodelist": nodelist,
        "ignored": compress(ignored) if ignored else "",
        "hosts": responded,
        "transport": transport,
        "allow_heterogeneous": allow_heterogeneous,
        "per_host": {h: {k: v for k, v in per_host[h].items() if not k.startswith("_")} for h in responded},
        "aggregate": result["aggregate"],
        "verdict": result["verdict"],
    }


def write_facts(path: Path, facts: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def load_facts(
    cbenchtest: str | Path, name_or_path: str, now: datetime | None = None
) -> tuple[dict, list[str]]:
    """Load a facts file; return (facts, warnings). Refuses failed checks."""
    p = Path(name_or_path)
    path = p if (p.suffix == ".json" or "/" in name_or_path) else facts_path(cbenchtest, name_or_path)
    if not path.exists():
        raise NodecheckError(f"node facts file not found: {path} (run `cbench nodecheck` first)")
    try:
        facts = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise NodecheckError(f"node facts file {path} is not valid JSON: {e}") from e
    if facts.get("schema_version") not in SUPPORTED_SCHEMA_VERSIONS:
        raise NodecheckError(
            f"node facts file {path} has schema_version {facts.get('schema_version')!r}, "
            f"expected one of {SUPPORTED_SCHEMA_VERSIONS} — re-run `cbench nodecheck`"
        )
    if not facts.get("verdict", {}).get("ok"):
        raise NodecheckError(
            f"node facts file {path} records a FAILED check: "
            + "; ".join(facts.get("verdict", {}).get("errors", []))
        )
    warnings: list[str] = []
    created = datetime.fromisoformat(facts["created"])
    now = now or datetime.now(timezone.utc)
    if now - created > timedelta(days=STALE_DAYS):
        warnings.append(
            f"node facts {path.name} are {(now - created).days} days old (>{STALE_DAYS}) — "
            "consider re-running `cbench nodecheck`"
        )
    return facts, warnings
