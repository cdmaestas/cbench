# Cbench Python Toolchain

Modern Python replacement for the core Cbench Perl scripts. Installable as a package; coexists with the original Perl tools.

## Install

```bash
pip install -e .
pip install -e ".[dev]"   # includes pytest
```

## Package layout

```
cbench/
├── config.py           # ClusterConfig dataclass + load_config()
├── launchers.py        # MPI launch command builders (openmpi, mpiexec, slurm, alps, yod)
├── schedulers.py       # Batch scheduler adapters (slurm, torque, pbspro, lsf, moab)
├── templates.py        # Template assembly + TOKEN_HERE → Jinja2 substitution; RUN_SIZES list
├── db.py               # SQLite results store (ResultsDB, ParseResult)
├── utils.py            # Pure-math sizing helpers (filter_run_sizes, find_pq, compute_n, ...)
├── parsers/            # 31 MPI benchmark output parsers
│   ├── base.py         # BenchmarkParser ABC + REGISTRY (auto-registered via __init_subclass__)
│   └── *.py            # xhpl, hpcc, imb, npb, ior, osu, amg, beff, bonnie, com, fileop,
│                       # graph500, hpccg, irs, lammps, laten, mdtest, miranda, mpibench,
│                       # mpigraph, phdmesh, rotate, rotlat, routecheck, sppm, sqmr, stress,
│                       # sweep3d, trilinos, io500, mlperf, elbencho
├── parse_filters/      # Error-detection filters applied during cbench parse
│   ├── __init__.py     # build_filter_set(), apply_filters()
│   └── *.py            # openmpi, slurm, torque, mvapich, mpiexec, cray, misc
├── hw_tests/           # 27 single-node hw_test parsers used by cbench nodehwtest
│   ├── __init__.py     # HwTest ABC + REGISTRY + get_hw_test()
│   └── *.py            # cpuinfo, meminfo, streams, stream2, stress_cpu, stress_disk,
│                       # iozone, hpcc, npb, xhpl, xhpl2, nodeperf, memtester, dmidecode,
│                       # cachebench, ctcs_memtst, fpck, ibport, idle, matmult, mpqc,
│                       # numa_gpu, numa_mem, omdiag, psnap, stride, topspin
└── cli/
    ├── main.py         # Top-level click group; wires in all subgroups
    ├── nodehwtest.py   # cbench nodehwtest: gen-jobs | start-jobs | parse
    ├── utils_cmd.py    # cbench utils: run-sizes | find-pq | find-n | npb-procs
    ├── diag.py         # cbench diag: apply parse filters, aggregate error counts
    ├── snb.py          # cbench snb: single-node benchmark run and report
    └── main.py         # also houses: make-skel, rm-failed (single-command tools)
```

## Adding a new parser

1. Create `cbench/parsers/myapp.py`:

```python
from cbench.parsers.base import BenchmarkParser, ParseResult

class MyAppParser(BenchmarkParser):
    names = ["myapp"]   # benchmark name(s) from jobname convention

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        # return ParseResult(status="PASSED", metrics={"throughput": 1234.5})
        # return ParseResult(status="ERROR(NOTSTARTED)")
        # return ParseResult(status="NOTICE", status_detail="reason")
        ...

    def metric_units(self) -> dict[str, str]:
        return {"throughput": "MB/s"}
```

2. Import it in `cbench/parsers/__init__.py` — the class registers itself automatically via `__init_subclass__`.

## SQLite schema

```sql
runs    (id, cluster, testset, ident, jobname, benchmark,
         numprocs, ppn, numnodes, status, status_detail, parsed_at)

metrics (id, run_id → runs.id, metric, value, units)
```

Query from Python:

```python
from cbench.db import ResultsDB

db = ResultsDB("/path/to/cbench_results.db")
rows = db.query(benchmark="xhpl", status="PASSED", since="2025-01-01")
print(db.export_json(cluster="mycluster"))
```

## Running tests

```bash
python -m pytest tests/ -v
```

288 tests covering config loading, all 28 MPI parsers, parse filters, 27 nodehwtest hw_test parsers, the SQLite store, template substitution, sizing utilities, diag, snb, and rm-failed.
