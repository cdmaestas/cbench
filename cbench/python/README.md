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
├── config.py        # ClusterConfig dataclass + load_config()
├── launchers.py     # MPI launch command builders (openmpi, mpiexec, slurm, alps, yod)
├── schedulers.py    # Batch scheduler adapters (slurm, torque, pbspro, lsf, moab)
├── templates.py     # Template assembly + TOKEN_HERE → Jinja2 substitution
├── db.py            # SQLite results store (ResultsDB, ParseResult)
├── parsers/
│   ├── base.py      # BenchmarkParser ABC + REGISTRY
│   ├── xhpl.py      # HPL/Linpack
│   ├── hpcc.py      # HPCC Suite
│   ├── imb.py       # Intel MPI Benchmarks
│   ├── npb.py       # NAS Parallel Benchmarks
│   ├── ior.py       # IOR I/O benchmark
│   ├── osu.py       # OSU MPI benchmarks
│   ├── amg.py       # AMG multigrid
│   ├── beff.py      # b_eff bandwidth
│   ├── bonnie.py    # Bonnie++ I/O
│   ├── com.py       # COM point-to-point
│   ├── fileop.py    # fileop metadata
│   ├── graph500.py  # Graph500
│   ├── hpccg.py     # HPCCG
│   ├── irs.py       # IRS radiation solver
│   ├── lammps.py    # LAMMPS MD
│   ├── laten.py     # MPI latency
│   ├── mdtest.py    # mdtest metadata I/O
│   ├── miranda.py   # Miranda
│   ├── mpibench.py  # mpiBench collectives
│   ├── mpigraph.py  # mpiGraph all-pairs
│   ├── phdmesh.py   # phdMesh
│   ├── rotate.py    # ring bandwidth
│   ├── rotlat.py    # ring latency
│   ├── routecheck.py# MPI routing validation
│   ├── sppm.py      # sPPM hydro
│   ├── sqmr.py      # SQMR message rate
│   ├── stress.py    # all-to-all stress
│   ├── sweep3d.py   # SWEEP3D transport
│   └── trilinos.py  # Trilinos Epetra
└── cli/
    └── main.py      # click CLI: gen-jobs | start-jobs | parse | query
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

86 tests covering config loading, all 28 parsers, the SQLite store, and template substitution.
