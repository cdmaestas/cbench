"""Tests for cbench.hostlist (pdsh/Slurm hostlist expand + compress)."""

import pytest

from cbench.hostlist import compress, expand

ZIMA = ["zima1", "zima2", "zima3", "zima4", "zimabg1", "zimabg2", "zimad"]


def test_expand_single_group():
    assert expand("n[1-3,5]") == ["n1", "n2", "n3", "n5"]


def test_expand_multiple_groups():
    # what `sinfo -o %N` returns for multi-rack partitions
    assert expand("n[1-3],m[5-6]") == ["n1", "n2", "n3", "m5", "m6"]


def test_expand_zima_topology():
    assert expand("zima[1-4],zimabg[1-2],zimad") == ZIMA


def test_expand_preserves_zero_padding():
    assert expand("n[08-10]") == ["n08", "n09", "n10"]


def test_expand_multiple_brackets_in_one_token():
    assert expand("r[1-2]n[1-2]") == ["r1n1", "r1n2", "r2n1", "r2n2"]


def test_expand_plain_list():
    assert expand("n001,n002") == ["n001", "n002"]


@pytest.mark.parametrize("bad", ["n[1-3", "n1-3]", "n[5-2]"])
def test_expand_rejects_malformed(bad):
    with pytest.raises(ValueError):
        expand(bad)


def test_compress_zima_topology():
    assert compress(ZIMA) == "zimad,zima[1-4],zimabg[1-2]"


def test_compress_padded_absorbs_same_width():
    assert compress([f"n{i:02d}" for i in range(1, 11)]) == "n[01-10]"


def test_compress_natural_numbers():
    assert compress([f"n{i}" for i in range(1, 11)]) == "n[1-10]"


def test_compress_gaps_and_single_host():
    assert compress(["n1", "n2", "n5"]) == "n[1-2,5]"
    assert compress(["zima3"]) == "zima3"


@pytest.mark.parametrize("hosts", [
    ZIMA,
    [f"n{i:03d}" for i in range(1, 130, 3)],
    ["a1", "a10", "a2", "b", "c05", "c6"],
    ["gpu01", "gpu02", "cpu1", "cpu2", "cpu3", "login"],
])
def test_round_trip(hosts):
    assert sorted(expand(compress(hosts))) == sorted(set(hosts))


def test_nodehwtest_expand_now_handles_multiple_groups():
    from cbench.cli.nodehwtest import _expand_pdsh
    assert _expand_pdsh("n[1-2],m[5-6]") == ["n1", "n2", "m5", "m6"]


def test_invalid_hostnames():
    from cbench.hostlist import invalid_hostnames
    assert invalid_hostnames(["zimabg1", "n01.cluster", "gpu_node-3"]) == []
    assert invalid_hostnames(["n1;id", "a b", "x$(id)", "-n", "n.", ""]) == ["n1;id", "a b", "x$(id)", "-n", "n.", ""]
