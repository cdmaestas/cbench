"""Tests for cbench.utils and the utils CLI subcommands."""

import pytest
from click.testing import CliRunner
from cbench.cli.main import cli
from cbench.utils import (
    is_power_of_two,
    is_perfect_square,
    is_perfect_cube,
    is_multiple_of,
    filter_run_sizes,
    find_pq,
    compute_n,
    find_npb_numprocs,
)


# ---------------------------------------------------------------------------
# predicates
# ---------------------------------------------------------------------------

def test_power_of_two():
    assert is_power_of_two(1)
    assert is_power_of_two(2)
    assert is_power_of_two(1024)
    assert not is_power_of_two(3)
    assert not is_power_of_two(0)
    assert not is_power_of_two(6)

def test_perfect_square():
    assert is_perfect_square(1)
    assert is_perfect_square(4)
    assert is_perfect_square(9)
    assert is_perfect_square(16)
    assert not is_perfect_square(3)
    assert not is_perfect_square(7)

def test_perfect_cube():
    assert is_perfect_cube(1)
    assert is_perfect_cube(8)
    assert is_perfect_cube(27)
    assert is_perfect_cube(64)
    assert not is_perfect_cube(2)
    assert not is_perfect_cube(9)

def test_multiple_of():
    assert is_multiple_of(256, 256)
    assert is_multiple_of(512, 256)
    assert not is_multiple_of(100, 256)
    assert is_multiple_of(300, 100)


# ---------------------------------------------------------------------------
# filter_run_sizes
# ---------------------------------------------------------------------------

def test_run_sizes_pof2():
    sizes = filter_run_sizes(max_procs=64, pof2=True)
    assert all(is_power_of_two(s) for s in sizes)
    assert 1 in sizes
    assert 64 in sizes
    assert 3 not in sizes

def test_run_sizes_square():
    sizes = filter_run_sizes(max_procs=100, square=True)
    assert all(is_perfect_square(s) for s in sizes)
    assert 4 in sizes
    assert 16 in sizes
    assert 36 in sizes

def test_run_sizes_mult():
    sizes = filter_run_sizes(max_procs=300, mult=100, try_all=True)
    assert sizes == [100, 200, 300]

def test_run_sizes_minprocs():
    sizes = filter_run_sizes(max_procs=64, min_procs=32, pof2=True)
    assert all(s >= 32 for s in sizes)

def test_run_sizes_addr():
    sizes = filter_run_sizes(max_procs=20, addr=5)
    assert sizes == [5, 10, 15, 20]

def test_run_sizes_no_filter_returns_all_in_range():
    sizes = filter_run_sizes(max_procs=8)
    # should include all run_sizes values up to 8
    assert len(sizes) > 0
    assert all(s <= 8 for s in sizes)

def test_run_sizes_try_all():
    sizes = filter_run_sizes(max_procs=10, try_all=True, pof2=True)
    assert sizes == [1, 2, 4, 8]


# ---------------------------------------------------------------------------
# find_pq
# ---------------------------------------------------------------------------

def test_find_pq_square_nprocs():
    # 16 procs: P=4, Q=4 should appear
    pairs = find_pq(16)
    assert any(p == 4 and q == 4 for p, q, _ in pairs)

def test_find_pq_decent_ratio():
    pairs = find_pq(48)
    decent = [(p, q, r) for p, q, r in pairs if 1.0 <= r <= 4.0]
    assert decent  # 48 has decent decompositions like P=4,Q=12

def test_find_pq_prime():
    # 7 procs: only P=1,Q=7 or P=7,Q=1
    pairs = find_pq(7, delta=10)
    pq_set = {(p, q) for p, q, _ in pairs}
    assert (1, 7) in pq_set or (7, 1) in pq_set

def test_find_pq_zero():
    assert find_pq(0) == []


# ---------------------------------------------------------------------------
# compute_n
# ---------------------------------------------------------------------------

def test_compute_n_basic():
    # 4 nodes, 2048 MB each, factor 0.5
    nvals = compute_n(nprocs=4, ppn=1, memory_per_node_mb=2048, memory_util_factors=[0.5])
    assert len(nvals) == 1
    assert nvals[0] > 0
    # N^2 * 8 bytes ≈ 0.5 * total_mem
    # total_mem = 4 * 2048 * 1024^2 bytes
    import math
    total_bytes = 4 * 2048 * 1024 * 1024
    expected = int(math.sqrt(total_bytes / 8) * 0.5 * 1.02)
    assert nvals[0] == expected

def test_compute_n_multiple_factors():
    nvals = compute_n(4, 1, 2048, [0.5, 0.6, 0.7])
    assert len(nvals) == 3
    assert nvals[0] < nvals[1] < nvals[2]


# ---------------------------------------------------------------------------
# find_npb_numprocs
# ---------------------------------------------------------------------------

def test_npb_procs_power_of_two():
    r = find_npb_numprocs(100)
    assert r["power_of_two"] == 64

def test_npb_procs_perfect_square():
    r = find_npb_numprocs(100)
    assert r["perfect_square"] == 100  # 100 = 10^2

def test_npb_procs_exact_power():
    r = find_npb_numprocs(64)
    assert r["power_of_two"] == 64
    assert r["perfect_square"] == 64  # 64 = 8^2

def test_npb_procs_small():
    r = find_npb_numprocs(3)
    assert r["power_of_two"] == 2
    assert r["perfect_square"] == 1


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------

runner = CliRunner()

def test_cli_run_sizes_pof2():
    result = runner.invoke(cli, ["utils", "run-sizes", "--maxprocs", "16", "--pof2"])
    assert result.exit_code == 0
    sizes = [int(x) for x in result.output.strip().split(",")]
    assert all(is_power_of_two(s) for s in sizes)

def test_cli_run_sizes_mult100():
    result = runner.invoke(cli, ["utils", "run-sizes", "--maxprocs", "300", "--mult100", "--try-all"])
    assert result.exit_code == 0
    assert result.output.strip() == "100,200,300"

def test_cli_run_sizes_addr():
    result = runner.invoke(cli, ["utils", "run-sizes", "--maxprocs", "20", "--addr", "5"])
    assert result.exit_code == 0
    assert result.output.strip() == "5,10,15,20"

def test_cli_run_sizes_newline():
    result = runner.invoke(cli, ["utils", "run-sizes", "--maxprocs", "8", "--pof2", "--newline"])
    assert result.exit_code == 0
    lines = result.output.strip().splitlines()
    assert all(is_power_of_two(int(l)) for l in lines)

def test_cli_find_pq():
    result = runner.invoke(cli, ["utils", "find-pq", "--nprocs", "16"])
    assert result.exit_code == 0
    assert "P=4 Q=4" in result.output
    assert "DECENT RATIO" in result.output

def test_cli_find_pq_decent_only():
    result = runner.invoke(cli, ["utils", "find-pq", "--nprocs", "48", "--decent-only"])
    assert result.exit_code == 0
    assert "DECENT RATIO" in result.output

def test_cli_find_n():
    result = runner.invoke(cli, [
        "utils", "find-n",
        "--nprocs", "4", "--ppn", "1",
        "--memory", "2048",
        "--util", "0.5,0.6",
    ])
    assert result.exit_code == 0
    assert "Nvals" in result.output
    assert "total nodes = 4" in result.output

def test_cli_npb_procs():
    result = runner.invoke(cli, ["utils", "npb-procs", "--nprocs", "100"])
    assert result.exit_code == 0
    assert "64" in result.output   # closest power of two
    assert "100" in result.output  # 100 is a perfect square
