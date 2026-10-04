"""HPL.dat / hpccinf.txt generation in gen-jobs (cbench.hplsizing).

Memory numbers are zima's type-A nodes (MemTotal 7705320-7706776 kB).
"""

import json
import math
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from cbench import hplsizing, templates
from cbench.cli.main import cli
from cbench.config import ClusterConfig
from cbench.utils import compute_pq


# ---------------------------------------------------------------------------
# compute_pq (port of Perl compute_PQ)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n, pq", [
    (1, (1, 1)), (2, (1, 2)), (3, (1, 3)), (4, (2, 2)), (8, (2, 4)),
    (16, (4, 4)), (32, (4, 8)), (72, (8, 9)), (96, (8, 12)), (110, (10, 11)),
])
def test_compute_pq_matches_perl(n, pq):
    assert compute_pq(n) == pq


@pytest.mark.parametrize("n", [0, 7, 11, 13])
def test_compute_pq_none_without_a_1_to_3_grid(n):
    assert compute_pq(n) is None


def test_every_standard_run_size_has_a_grid():
    assert [n for n in templates.RUN_SIZES if compute_pq(n) is None] == []


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------

def _render(bench, **kw):
    args = {"numprocs": 16, "ppn": 4, "mem_per_node_mb": 7500, "factors": [0.25, 0.8]} | kw
    return hplsizing.render(hplsizing.input_spec(bench), templates._templates_dir(), **args)


def test_hpl_dat_carries_n_per_factor_and_grid():
    lines = _render("xhpl").splitlines()
    total = 7500 * 4 * 1024 * 1024  # 4 nodes
    n25, n80 = (math.floor(math.sqrt(total / 8) * f) for f in (0.25, 0.8))
    assert lines[4].split()[0] == "2"                       # of problem sizes
    assert lines[5].split()[:2] == [str(n25), str(n80)]     # Ns
    assert lines[10].split()[0] == "4" and lines[11].split()[0] == "4"  # P, Q
    assert "_HERE" not in "\n".join(lines)


@pytest.mark.parametrize("bench, filename", [
    ("xhpl", "HPL.dat"), ("xhpl2", "HPL.dat"), ("xhplintel", "HPL.dat"), ("hpcc", "hpccinf.txt"),
])
def test_input_spec_per_benchmark(bench, filename):
    spec = hplsizing.input_spec(bench)
    assert spec.filename == filename
    assert "_HERE" not in _render(bench)


def test_no_input_file_for_other_benchmarks():
    assert hplsizing.input_spec("imb") is None and hplsizing.input_spec("hpccg") is None


def test_render_none_when_no_grid():
    assert _render("xhpl", numprocs=7) is None


def test_render_rejects_nonpositive_n():
    with pytest.raises(hplsizing.HplSizingError):
        _render("xhpl", factors=[0.0])


def test_shakedown_uses_single_low_factor():
    cfg = ClusterConfig()
    assert hplsizing.mem_util_factors(cfg, "shakedown") == [0.45]
    assert hplsizing.mem_util_factors(cfg, "linpack") == cfg.memory_util_factors


# ---------------------------------------------------------------------------
# gen-jobs end to end
# ---------------------------------------------------------------------------

def _facts(mem_min=7705320, mem_max=15991676):
    return {
        "schema_version": 1, "name": "mixed",
        "created": datetime.now(timezone.utc).isoformat(),
        "allow_heterogeneous": True,
        "verdict": {"ok": True, "heterogeneous": True, "errors": [], "warnings": []},
        "aggregate": {"cpus": {"min": 4, "max": 8},
                      "memtotal_kb": {"min": mem_min, "max": mem_max},
                      "models": [], "targets": {}},
    }


@pytest.fixture
def genv(tmp_path):
    def write_cfg(extra=""):
        cfg = tmp_path / "cluster.yaml"
        cfg.write_text("cluster_name: zima\nmax_nodes: 4\nprocs_per_node: 4\n"
                       "batch_method: slurm\n" + extra)
        return cfg

    (tmp_path / "nodefacts").mkdir()
    (tmp_path / "nodefacts" / "mixed.json").write_text(json.dumps(_facts()))

    def run(*args, cfg_extra=""):
        return CliRunner().invoke(cli, ["gen-jobs", "--ident", "t1", "--run-type", "batch",
                                        "--config", str(write_cfg(cfg_extra)),
                                        "--cbenchtest", str(tmp_path), *args])

    def job(testset, jobname):
        return tmp_path / testset / "t1" / jobname

    return SimpleNamespace(tmp=tmp_path, run=run, job=job)


def test_genjobs_linpack_without_memory_source_fails_before_rendering(genv):
    res = genv.run("--testset", "linpack", "--ppn", "4", "--maxprocs", "4")
    assert res.exit_code != 0 and "--nodefacts" in res.output
    assert not (genv.tmp / "linpack").exists()


def test_genjobs_linpack_writes_hpl_dat_from_min_memtotal(genv):
    res = genv.run("--testset", "linpack", "--ppn", "4", "--maxprocs", "16",
                   "--nodefacts", "mixed")
    assert res.exit_code == 0, res.output
    dat = (genv.job("linpack", "xhpl-4ppn-16") / "HPL.dat").read_text().splitlines()
    # memory-sized: MIN MemTotal (the 7.3 GiB nodes), never the 15 GiB ones
    total = (7705320 // 1024) * 4 * 1024 * 1024
    assert dat[5].split()[1] == str(math.floor(math.sqrt(total / 8) * 0.8))
    for bench in ("xhpl", "xhpl2", "xhplintel"):
        assert (genv.job("linpack", f"{bench}-4ppn-4") / "HPL.dat").exists()


def test_genjobs_linpack_binary_paths_are_not_doubled(genv):
    res = genv.run("--testset", "linpack", "--ppn", "4", "--maxprocs", "4",
                   cfg_extra="memory_per_node_mb: 7500\n")
    assert res.exit_code == 0, res.output
    bindir = genv.tmp / "bin"
    for bench in ("xhpl", "xhpl2", "xhplintel"):
        script = next(genv.job("linpack", f"{bench}-4ppn-4").glob("*.slurm")).read_text()
        assert f'cbench_check_for_bin {bindir}/{bench}\n' in script
        assert "bin//" not in script


def test_genjobs_hpcc_writes_hpccinf(genv):
    res = genv.run("--testset", "hpcc", "--ppn", "4", "--maxprocs", "8",
                   cfg_extra="memory_per_node_mb: 7500\n")
    assert res.exit_code == 0, res.output
    inf = (genv.job("hpcc", "hpcc-4ppn-8") / "hpccinf.txt").read_text()
    assert "_HERE" not in inf
    script = next(genv.job("hpcc", "hpcc-4ppn-8").glob("*.slurm")).read_text()
    assert f"{genv.tmp}/bin/hpcc\"" in script and "bin//" not in script


def test_genjobs_shakedown_xhpl_uses_low_factor_and_says_so(genv):
    res = genv.run("--testset", "shakedown", "--ppn", "4", "--maxprocs", "4",
                   cfg_extra="memory_per_node_mb: 7500\n")
    assert res.exit_code == 0, res.output
    job = genv.job("shakedown", "xhpl-4ppn-4")
    assert (job / "HPL.dat").read_text().splitlines()[4].split()[0] == "1"
    assert 'memory_util_factors: 0.45"' in next(job.glob("*.slurm")).read_text()


def test_genjobs_skips_proc_counts_without_grid(genv, monkeypatch):
    monkeypatch.setattr(templates, "RUN_SIZES", [4, 7])
    res = genv.run("--testset", "linpack", "--ppn", "4", "--maxprocs", "8",
                   cfg_extra="memory_per_node_mb: 7500\n")
    assert res.exit_code == 0, res.output
    assert "no HPL P x Q grid" in res.output and "xhpl-4ppn-7" in res.output
    assert not genv.job("linpack", "xhpl-4ppn-7").exists()
    assert (genv.job("linpack", "xhpl-4ppn-4") / "HPL.dat").exists()


def test_genjobs_dry_run_prints_hpl_dat_and_writes_nothing(genv):
    res = genv.run("--testset", "linpack", "--ppn", "4", "--maxprocs", "4", "--dry-run",
                   cfg_extra="memory_per_node_mb: 7500\n")
    assert res.exit_code == 0, res.output
    assert "# of problems sizes (N)" in res.output and "Ps" in res.output
    assert not (genv.tmp / "linpack").exists()
