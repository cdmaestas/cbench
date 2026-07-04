# Changelog

All notable changes to Cbench are documented here.
See `cbench/CHANGES` for the v1.x Perl toolchain history.

---

## [2.0.0] — 2026-07-03

### Python toolchain (new)

Version 2.0 adds a modern Python toolchain (`cbench/python/`) alongside the
original Perl scripts, which remain intact and fully functional.
Install with `pip install -e cbench/python/` to get the `cbench` CLI.

#### New commands

| Command | Description |
|---|---|
| `cbench build run/all/list/check/update` | Download, compile, and cache benchmark software |
| `cbench gen-jobs` | Generate batch job scripts from cluster config and templates |
| `cbench start-jobs` | Submit jobs to SLURM, PBS, LSF, Moab, or run locally |
| `cbench parse` | Parse benchmark stdout into a SQLite DB and JSON |
| `cbench query` | Query results by benchmark, cluster, status, date range; trend analysis |
| `cbench snb run/report/store/compare` | Single-node benchmark suite (no scheduler required) |
| `cbench nodehwtest gen-jobs/start-jobs/parse` | Per-node hardware qualification |
| `cbench serve` | Flask web dashboard with Prometheus `/metrics` endpoint |
| `cbench diag` | Scan output files for known error patterns using parse filters |
| `cbench utils run-sizes/find-pq/find-n/npb-procs` | HPC sizing utilities |
| `cbench make-skel` | Generate skeleton job script templates |
| `cbench rm-failed` | Remove ERROR job directories |

#### Benchmark builders (15 total)

`cbench build run <name>` downloads source and compiles:
`stream`, `imb` (Intel MPI Benchmarks), `osu` (OSU MPI Micro-Benchmarks),
`ior` (IOR + mdtest), `hpl` (HPL Linpack), `hpcc` (HPC Challenge),
`npb` (NAS Parallel Benchmarks), `amg` (LLNL AMG), `hpccg` (Mantevo HPCCG),
`mpibench`, `mpigraph`, `graph500`, `bonnie`, `iozone`, `fio`.

`cbench build update` pulls upstream changes and rebuilds only if HEAD changed.
Build results are cached in `<prefix>/build.lock` keyed by source URL and
compiler config hash — unchanged builds are skipped on subsequent runs.

#### Benchmark output parsers

Python ports of all 31 Perl output parsing modules plus new additions:
`xhpl`, `xhpl2`, `hpcc`, `imb`, `npb`, `ior`, `io`, `iosanity`, `osu`,
`mpioverhead`, `amg`, `beff`, `bonnie`, `com`, `graph500`, `hpccg`,
`irs`, `lammps`, `mdtest`, `miranda`, `mpibench`, `mpigraph`, `phdmesh`,
`rotate`, `rotlat`, `routecheck`, `sppm`, `sqmr`, `stress`, `longstress`,
`sweep3d`, `trilinos`, `fileop`, `laten`, `fio`, `io500`, `elbencho`,
`gpfsperf`, `mlperf` (training + inference).

Auto-registration via `__init_subclass__` — new parsers self-register by
setting `names = [...]` on a `BenchmarkParser` subclass.

#### Results database

SQLite DB at `$CBENCHTEST/cbench_results.db`:
- WAL mode, FK cascade deletes, idempotent `INSERT OR REPLACE` on
  `(cluster, testset, ident, jobname, benchmark)` — re-parsing overwrites
  rather than duplicating rows.
- `cbench query --trend` — per-ident metric averages in chronological order
  with Δ% column.
- `cbench query --output csv/json/prometheus` — flexible export formats.
- `cbench query --aggregate` — mean/min/max per benchmark+metric.

#### Web dashboard (`cbench serve`)

Optional Flask app (`pip install "cbench[web]"`):
- Dark-themed single-page dashboard with summary cards, filterable results
  table (auto-refreshes every 30 s), and Chart.js metric trend chart.
- `/metrics` Prometheus text exposition endpoint for scraping.
- `--no-cdn` / `--assets-dir` for air-gapped HPC clusters.
- All DB-sourced values HTML-escaped before `innerHTML` assignment (XSS prevention).
- Prometheus label values escaped per the text format spec.

#### Single-node benchmarks (`cbench snb`)

Runs stream, cachebench, dgemm, mpistreams, linpack, npb, fio, hpcc directly
without a job scheduler. Results stored to the shared SQLite DB.

- `cbench snb run --remote NODE` dispatches via ssh/pdsh to a remote node
  (shared filesystem required); `--remote-cbench PATH` sets the binary path.
- `cbench snb compare --ident X --baseline Y` flags regressions beyond a
  configurable threshold.

#### Configuration

`cluster.yaml` replaces the Perl `cluster.def` for the Python toolchain
(Perl tools continue reading `cluster.def` unchanged). Full JSON Schema
validation with enum guards, range checks, and walltime pattern validation.
`$CBENCHCLUSTER` env var selects a named cluster section.

#### Schedulers and launchers

Batch: SLURM, Torque/PBS, PBS Pro, LSF, Moab, Cray CLE Torque,
`local` (runs scripts directly with `bash` — no scheduler required).

MPI launchers: OpenMPI (`orterun`), mpiexec, SLURM (`srun`), yod, ALPS (`aprun`).

#### Security hardening

- XSS: dashboard JS `esc()` helper escapes all DB-sourced `innerHTML` values.
- Prometheus: `_prom_label()` escapes `"` and `\n` in label values.
- Tarball downloads: zip-slip guard validates every member path before `extractall`.
- `cluster_name` restricted to `[A-Za-z0-9_-]+` by JSON Schema.
- `--remote`/`--node` hostname arguments reject `/`, `\\`, `..`, and spaces.
- HTTPS enforced for iozone download (was HTTP).

#### CI

GitHub Actions on Python 3.9–3.12; `pytest --cov-fail-under=80` coverage gate;
`.coverage` artifact uploaded on the Python 3.12 run.
RPM and DEB packages built and attached to GitHub Releases automatically.

---

## [1.3.0] — 2013

Original Perl toolchain release. See [`cbench/CHANGES`](cbench/CHANGES) for details.
