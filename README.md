# Cbench

**Scalable Cluster Benchmarking and Testing Toolkit**

Cbench is a framework for building, running, and parsing HPC benchmarks across Linux parallel compute clusters. It automates the full lifecycle: generating job scripts, submitting them to a batch scheduler, and parsing the resulting output into structured results.

Originally developed at Sandia National Laboratories (v1.3.0, 2013). Version 2.0.0 adds a modern Python toolchain alongside the original Perl scripts.

---

## Repository layout

```
cbench/
├── cbench.pl               # Core Perl library (job launchers, schedulers, template engine)
├── cluster.def             # Perl cluster configuration (legacy)
├── cluster.yaml            # YAML cluster configuration (Python toolchain)
├── tools/                  # Perl scripts: gen_jobs, start_jobs, output_parse, ...
├── sbin/                   # Orchestration wrappers
├── templates/              # Job script templates (*.in)
├── perllib/
│   ├── output_parse/       # Benchmark-specific Perl parsers (31 benchmarks)
│   ├── parse_filter/       # Custom error-detection filter modules
│   ├── gen_jobs/           # Job-generation hook modules
│   └── hw_test/            # Single-node hardware test modules
├── python/                 # ← Modern Python toolchain (see below)
│   ├── pyproject.toml
│   ├── cbench/             # Installable Python package
│   └── tests/
├── doc/                    # Full documentation (see doc/README)
└── opensource/             # Bundled benchmark sources

openapps/                   # Scientific application sources (AMG, LAMMPS, Trilinos, ...)
fixit123/                   # Node breakfix and qualification framework
```

---

## Quick start — Python toolchain

The Python toolchain (`cbench/python/`) is a pip-installable package that replaces the core Perl scripts with a single `cbench` CLI. The original Perl scripts remain intact and fully functional.

### Requirements

- Python 3.9+
- `click`, `pyyaml`, `rich`, `jinja2` (installed automatically)

### Install

```bash
pip install -e cbench/python/
```

### Configure

Copy and edit the cluster configuration:

```bash
cp cbench/cluster.yaml my_cluster.yaml
# Edit: max_nodes, procs_per_node, batch_method, joblaunch_method, etc.
export CBENCHOME=/path/to/cbench/cbench
export CBENCHTEST=/path/to/your/test/tree
```

### Generate job scripts

```bash
cbench gen-jobs --testset bandwidth --ident run1
cbench gen-jobs --testset linpack   --ident run1 --ppn 4,8 --maxprocs 256
cbench gen-jobs --testset bandwidth --ident run1 --dry-run   # preview without writing
```

Job scripts are written to `$CBENCHTEST/<testset>/<ident>/<jobname>/`.

### Submit jobs

```bash
cbench start-jobs --testset bandwidth --ident run1 --batch
cbench start-jobs --testset bandwidth --ident run1 --throttledbatch 20  # keep 20 jobs active
cbench start-jobs --testset bandwidth --ident run1 --interactive
```

### Parse results

```bash
cbench parse --testset bandwidth --ident run1
cbench parse --testset bandwidth --ident run1 --output json
```

Results are written to:
- Terminal: colored pass/fail table
- `$CBENCHTEST/<testset>/<ident>/results.json`
- `$CBENCHTEST/cbench_results.db` (SQLite)

### Query the results database

```bash
cbench query --benchmark xhpl
cbench query --cluster mycluster --status PASSED --since 2025-01-01
cbench query --testset bandwidth --output json
```

---

## Supported benchmarks

| Benchmark | Parser | Key metrics |
|---|---|---|
| HPL / Linpack | `xhpl`, `xhpl2` | GigaFlops, runtime |
| HPCC Suite | `hpcc` | HPL, DGEMM, PTRANS, STREAM, FFT, RandomAccess |
| NAS Parallel Benchmarks | `npb` | Mop/s |
| Intel MPI Benchmarks | `imb` | latency µs, bandwidth MB/s |
| IOR | `ior`, `io`, `iosanity` | write/read MB/s |
| OSU MPI | `osu`, `mpioverhead` | bandwidth MB/s, latency µs |
| AMG | `amg` | solver FOM |
| b_eff | `beff` | bidir bandwidth MB/s |
| Bonnie++ | `bonnie` | sequential/random I/O |
| COM | `com` | unidir/bidir bandwidth |
| Graph500 | `graph500` | TEPS |
| HPCCG | `hpccg` | MFlops |
| IRS | `irs` | FOM, zone time |
| LAMMPS | `lammps` | ns/day |
| mdtest | `mdtest` | file/dir metadata ops/s |
| Miranda | `miranda` | transfer rate MiB/s |
| mpiBench | `mpibench`, `collective` | collective latency µs |
| mpiGraph | `mpigraph` | all-pairs send/recv MB/s |
| phdMesh | `phdmesh` | search/rebalance time |
| rotate / rotlat | `rotate`, `rotlat` | ring bandwidth/latency |
| routecheck | `routecheck` | routing validation time |
| sPPM | `sppm` | HYD/IO cpu+wall time |
| SQMR | `sqmr` | message rate msgs/s |
| stress | `stress`, `longstress` | all-to-all aggregate MB/s |
| SWEEP3D | `sweep3d` | CPU time, grind time |
| Trilinos Epetra | `trilinos` | SpMV, SpMM, BLAS MFlops |
| fileop | `fileop` | pass/fail |
| laten | `laten` | MPI latency µs |

---

## Supported schedulers and launchers

**Batch schedulers:** SLURM, Torque/PBS, PBS Pro, LSF, Moab, LoadLeveler, Cray CLE Torque

**MPI launchers:** OpenMPI (`orterun`), mpiexec, SLURM (`srun`), yod, ALPS (`aprun`)

---

## Original Perl toolchain

The original Perl tools remain fully functional. Set `CBENCHOME` and `CBENCHTEST`, then:

```bash
# Generate jobs (Perl)
$CBENCHOME/sbin/gen_jobs.pl --testset bandwidth --ident run1

# Submit jobs
$CBENCHOME/sbin/start_jobs.pl --testset bandwidth --ident run1 --batch

# Parse output
$CBENCHOME/tools/cbench_output_parse.pl --testset bandwidth --ident run1
```

For full Perl toolchain documentation see [`cbench/doc/README`](cbench/doc/README) and the HOWTOs in [`cbench/doc/`](cbench/doc/).

---

## Running tests

```bash
pip install -e "cbench/python[dev]"
cd cbench/python
python -m pytest tests/ -v
```

CI runs automatically on Python 3.9–3.12 for every push touching `cbench/python/`.

---

## Configuration reference

`cluster.yaml` (or the legacy `cluster.def`) controls all cluster-specific parameters:

| Parameter | Default | Description |
|---|---|---|
| `cluster_name` | `test` | Cluster identifier (override with `$CBENCHCLUSTER`) |
| `max_nodes` | `1` | Total nodes available |
| `procs_per_node` | `8` | Cores per node |
| `max_ppn_procs` | auto | Max processes at each ppn level |
| `memory_per_node_mb` | `2048` | RAM per node in MB |
| `default_walltime` | `04:00:00` | Default job walltime (HH:MM:SS) |
| `walltime_method` | `0` | `0`=constant, `1`=stepped by run size |
| `walltime_steptime` | `10` | Minutes added per run-size step (method 1) |
| `joblaunch_method` | `openmpi` | MPI launcher: `openmpi`, `mpiexec`, `slurm`, `alps`, `yod` |
| `batch_method` | `slurm` | Scheduler: `slurm`, `torque`, `pbspro`, `lsf`, `moab` |
| `memory_util_factors` | `[0.25, 0.80, 0.85]` | Memory utilization fractions (Linpack) |
| `parse_filter_include` | see yaml | Error-detection filter modules to load |

---

## License

Cbench is free software licensed under the [GNU General Public License v2](cbench/doc/LICENSE).
Copyright (2005) Sandia Corporation. Under the terms of Contract DE-AC04-94AL85000 with Sandia Corporation, the U.S. Government retains certain rights in this software.
