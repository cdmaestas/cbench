# Changelog

All notable changes to Cbench are documented here.
See `cbench/CHANGES` for the v1.x Perl toolchain history.

---

## [Unreleased]

### Added
- **Node-aware fio I/O testing in `cbench snb`.** New repeatable `--fs-target PATH`
  option targets fio at explicit filesystem(s). For each target, snb detects the
  filesystem type (gpfs/lustre/nfs/panfs/local, via `/proc/self/mountinfo`) and
  probes O_DIRECT support; when O_DIRECT is unavailable it falls back to buffered
  I/O sized to 2× RAM to defeat the page cache (capped to free space, with a
  cache-influenced caveat recorded). Results are stored per target
  (`benchmark = snb_fio_{fstype}_{basename}`) with provenance in `status_detail`.
  The random-I/O job's `--numjobs` tracks node cores (`min(numcores, 16)`) so
  each node is driven proportional to its core count; the sequential job stays
  single-stream.
- `fio` single-node `hw_test` parser (`hw_tests/fio.py`, `test_class=disk`) —
  produces the same four throughput metrics as `iozone`
  (`fio_read/write/randomread/randomwrite`), so fio can stand in for iozone.
- **Progress heartbeat for `cbench snb run`.** Each running test now emits a
  "still running (elapsed)" line every 30 s (tunable via `--heartbeat SECONDS`,
  `<=0` disables), so a long test (fio, linpack, hpcc) is visibly alive instead
  of indistinguishable from a hang.
- **`cbench nodecheck` node precheck.** Probes every node in a pool (`--nodelist`
  or Slurm `--partition`) via pdsh (`-R ssh` or `-R exec`) or ssh, collects
  logical CPU count, MemTotal, CPU model, and each configured IO target's fstype
  and free space, verifies the pool is homogeneous (CPUs exact, MemTotal within
  2%, every target mounted with the same fstype, every node reachable), and
  writes `$CBENCHTEST/nodefacts/<name>.json` for job generation. Exits nonzero on
  failure; `--allow-heterogeneous` and `--ignore` cover mixed pools.
- New `cluster.yaml` keys: `io_targets` (named IO target directories),
  `remotecmd_rcmd` (`ssh`|`exec`), `remotecmd_exec_cmd` (exec template with `%h`).

### Fixed
- pdsh-style hostlists with more than one bracket group (e.g. `n[1-3],m[5-6]`,
  as returned by `sinfo`) were expanded incorrectly by `nodehwtest`; hostlist
  handling now lives in `cbench.hostlist`.

### Changed
- **RPM and DEB packages now recommend Open MPI** (RPM `Recommends: openmpi-devel`;
  DEB `Recommends: openmpi-bin, libopenmpi-dev`), needed to build and run the MPI
  benchmarks (IOR, mdtest, IMB, OSU, HPL, …). It is a weak dependency: installed
  by default, but sites on another MPI can skip it (`--setopt=install_weak_deps=False`
  / `--no-install-recommends`). Both formats also recommend `environment-modules`
  for the `module` command (Lmod sites already have one; a conflicting weak
  dependency is skipped, not fatal). On RHEL, Open MPI installs outside PATH: use
  `module load mpi/openmpi-x86_64` or add `/usr/lib64/openmpi/bin` to PATH.
- **`fio` is no longer part of the default `cbench snb run` suite** — it is now
  opt-in via `--tests` and, when selected, **requires** `--fs-target`. Existing
  invocations that relied on fio running by default must add `fio` to `--tests`
  and supply `--fs-target`. The rest of the suite is unaffected.

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
