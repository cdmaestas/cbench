"""pdsh/Slurm-style hostlist expansion and compression.

    expand("n[1-3,5],gpu[01-02]")  -> ["n1", "n2", "n3", "n5", "gpu01", "gpu02"]
    compress(["n1", "n2", "n3", "gpu01", "gpu02"]) -> "gpu[01-02],n[1-3]"

``expand(compress(hosts))`` returns the same set of hosts.
"""

from __future__ import annotations

import re

_TRAILING_DIGITS = re.compile(r"^(.*?)(\d+)$")
#: a host name that is safe to write into a job script or scheduler option:
#: letters, digits, '.', '_' and '-', starting and ending alphanumeric
_HOSTNAME = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._\-]*[A-Za-z0-9])?$")


def invalid_hostnames(hosts: list[str]) -> list[str]:
    """The names in ``hosts`` that aren't plain host names (shell syntax,
    spaces, path separators...)."""
    return [h for h in hosts if not _HOSTNAME.match(h)]


def _split_top_level(spec: str) -> list[str]:
    """Split on commas that are not inside [...] brackets."""
    parts: list[str] = []
    depth = 0
    cur = ""
    for ch in spec:
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth < 0:
                raise ValueError(f"Unbalanced ']' in hostlist: {spec!r}")
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    if depth != 0:
        raise ValueError(f"Unbalanced '[' in hostlist: {spec!r}")
    parts.append(cur)
    return [p.strip() for p in parts if p.strip()]


def _expand_token(token: str) -> list[str]:
    """Expand one token, recursing so multiple bracket groups work."""
    start = token.find("[")
    if start == -1:
        return [token]
    end = token.index("]", start)
    prefix, ranges, rest = token[:start], token[start + 1:end], token[end + 1:]
    out: list[str] = []
    for item in ranges.split(","):
        item = item.strip()
        if not item:
            continue
        if "-" in item:
            lo, hi = item.split("-", 1)
            width = len(lo) if lo.startswith("0") and len(lo) > 1 else 0
            if int(hi) < int(lo):
                raise ValueError(f"Descending range {item!r} in hostlist token {token!r}")
            nums = [str(i).zfill(width) for i in range(int(lo), int(hi) + 1)]
        else:
            nums = [item]
        for n in nums:
            out.extend(_expand_token(f"{prefix}{n}{rest}"))
    return out


def expand(spec: str) -> list[str]:
    """Expand a hostlist expression into individual hostnames (order preserved)."""
    hosts: list[str] = []
    for token in _split_top_level(spec):
        hosts.extend(_expand_token(token))
    return hosts


def _ranges(nums: list[int], width: int) -> str:
    nums = sorted(set(nums))
    chunks: list[str] = []
    i = 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        a, b = str(nums[i]).zfill(width), str(nums[j]).zfill(width)
        chunks.append(a if i == j else f"{a}-{b}")
        i = j + 1
    return ",".join(chunks)


def compress(hosts: list[str]) -> str:
    """Compress hostnames into a compact hostlist expression."""
    plain: set[str] = set()
    # prefix -> {"padded": {width: [nums]}, "natural": [nums]}
    groups: dict[str, dict] = {}
    for h in set(hosts):
        m = _TRAILING_DIGITS.match(h)
        if not m:
            plain.add(h)
            continue
        prefix, digits = m.group(1), m.group(2)
        g = groups.setdefault(prefix, {"padded": {}, "natural": []})
        if digits.startswith("0") and len(digits) > 1:
            g["padded"].setdefault(len(digits), []).append(int(digits))
        else:
            g["natural"].append(digits)

    out: list[str] = sorted(plain)
    for prefix in sorted(groups):
        g = groups[prefix]
        natural = list(g["natural"])
        for width, nums in sorted(g["padded"].items()):
            # numbers that already have `width` digits belong with the padded set
            absorbed = [d for d in natural if len(d) == width]
            natural = [d for d in natural if len(d) != width]
            all_nums = nums + [int(d) for d in absorbed]
            out.append(_fmt(prefix, all_nums, width))
        if natural:
            out.append(_fmt(prefix, [int(d) for d in natural], 0))
    return ",".join(out)


def _fmt(prefix: str, nums: list[int], width: int) -> str:
    uniq = sorted(set(nums))
    if len(uniq) == 1:
        return f"{prefix}{str(uniq[0]).zfill(width)}"
    return f"{prefix}[{_ranges(uniq, width)}]"
