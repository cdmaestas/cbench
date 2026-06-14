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

### Generate a skeleton job script

```bash
# Write setvars-1ppn-1.slurm + setvars-1ppn-1.sh to the current directory
cbench make-skel

# Choose a different skeleton template (skeleton_hello.in)
cbench make-skel --skelname hello --ppn 4 --numprocs 16

# Preview without writing
cbench make-skel --skelname setvars --dry-run

# Write to a specific directory
cbench make-skel --skelname setvars --outdir /path/to/newbench/
```

Available skeletons are the `skeleton_*.in` files in `$CBENCHOME/templates/`
(`hello`, `setvars`, `snb`). All `TOKEN_HERE` substitutions are expanded exactly
as they would be in a real `cbench gen-jobs` run.

---

### Remove failed jobs

```bash
# Preview which ERROR job directories would be removed
cbench rm-failed --testset bandwidth --ident run1

# Actually delete them
cbench rm-failed --testset bandwidth --ident run1 --force

# Restrict to a subset of jobs
cbench rm-failed --testset bandwidth --ident run1 --match "xhpl" --force
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

### Node hardware testing

```bash
# Create a test identifier for a set of nodes
cbench nodehwtest gen-jobs --nodelist n[1-10] --ident run1

# Submit one batch job per node (or run via pdsh)
cbench nodehwtest start-jobs --ident run1 --nodebatch
cbench nodehwtest start-jobs --ident run1 --remote

# Parse node_hw_test output files and report statistical outliers
cbench nodehwtest parse --ident run1 --characterize --save-targets baseline
cbench nodehwtest parse --ident run1 --load-targets baseline
```

Output files are named `<node>.node_hw_test.run<NNNN>` in `$CBENCHTEST/nodehwtest/<ident>/`.

### Sizing utilities

```bash
# Run sizes filtered by various criteria
cbench utils run-sizes --maxprocs 1024 --pof2
cbench utils run-sizes --maxprocs 512  --square
cbench utils run-sizes --maxprocs 2048 --mult 256
cbench utils run-sizes --maxprocs 100  --addr 5    # arithmetic sequence: 5,10,15,...

# Find HPL grid decompositions for N MPI ranks
cbench utils find-pq --nprocs 512 --decent-only

# Compute HPL problem size N from memory and utilization
cbench utils find-n --nprocs 512 --ppn 16 --memory 64000 --util 0.5,0.6,0.7

# Find valid NPB processor counts (power-of-2 and perfect-square)
cbench utils npb-procs --nprocs 500
```

### Diagnose output files

```bash
# Scan output files for known error patterns and aggregate by error type
cbench diag file1.out file2.out --filters openmpi,slurm

# Scan an entire testset/ident tree
cbench diag --testset bandwidth --ident run1 --filters slurm,misc

# Show only sources that appeared ≥ 3 times; emit JSON
cbench diag --testset bandwidth --ident run1 --threshold 3 --output json

# Filter by node role (for OMPI src→dst errors)
cbench diag file.out --source-only
cbench diag file.out --source-dest-only
```

Available filter modules: `openmpi`, `slurm`, `torque`, `mvapich`, `mpiexec`, `cray`, `misc`.

---

### Single-node benchmarking

```bash
# Run the full single-node benchmark suite (stream, cachebench, dgemm, mpistreams, linpack, npb)
cbench snb run --ident run1 --destdir /scratch/snb

# Run a subset of tests
cbench snb run --ident run1 --tests "stream|dgemm" --numcores 32

# Preview commands without executing
cbench snb run --ident run1 --dry-run

# Display a results summary table from saved output files
cbench snb report --ident run1 --destdir /scratch/snb
cbench snb report --ident run1 --node n042   # report for a specific node
```

Output files are written to `<destdir>/<ident>/<hostname>.snb.<test>.out`.

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
