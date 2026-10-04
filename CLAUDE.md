# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository overview

Cbench is an HPC benchmarking framework. v2.0 adds a Python toolchain alongside the original Perl scripts (which remain intact and functional). All new work goes in `cbench/python/`.

**Branch layout:**
- `main` — canonical branch with all commits
- `v2.0` — active development branch (Python toolchain)
- `v1.3.0` — tag at the original Perl-only commit

## Current work / session handoff

Read this first — it's the pointer to "where things are right now" so a new session doesn't re-derive it.

- **Active branch:** `v2.0` (all Python work lands here). `main` tracks behind; sync `v2.0` → `main` at release milestones.
- **Current focus:** _Node-aware IO arc landed on `v2.0` and `main` (nodecheck, IO sizing, modern IO parsers, HPL.dat, fio as default node-local IOPS/metadata test — §11–§14). No work in flight; next candidates are in the session-state backlog (IO profile bundles first)._
- **Open PRs / in flight:** _none._
- **Detailed state:** richer per-session notes (in-flight work, next steps, gotchas, how to run things on this machine) live in Claude's **local memory dir** — not committed to the repo. At the start of a session, check that memory; a cold session can also be told "read session state."

**Handoff protocol — before ending a session:** update the three lines above (focus / open PRs), and update `session-state.md` in the memory dir with what changed, what's next, and any gotchas found. Keep this CLAUDE.md section *short and stable* — it's a pointer, not a changelog. Durable architecture facts go in the sections below; transient "what I'm doing now" goes in memory.

## Python toolchain — development commands

```bash
# Install (editable, from repo root)
pip install -e "cbench/python[dev]"

# Run all tests
cd cbench/python && python3 -m pytest tests/

# Run a single test file
python3 -m pytest tests/test_utils.py -v

# Run a single test by name
python3 -m pytest tests/test_parsers.py::test_xhpl_parse -v

# CLI entry point (after install)
cbench --help
cbench utils run-sizes --maxprocs 512 --pof2
cbench nodehwtest gen-jobs --nodelist n[1-10] --ident run1
```

Ruff is the linter (`[tool.ruff]` in `cbench/python/pyproject.toml`; rules F/E/B/S, py39 target — run `ruff check .` from `cbench/python/`). Pre-commit hooks are configured in `.pre-commit-config.yaml` at the repo root (ruff + hygiene checks on commit, full pytest on push); install with `pre-commit install --install-hooks -t pre-commit -t pre-push`. Keep `ruff check` clean — vetted false positives are annotated in-line with `noqa`/`nosec` plus a justification comment rather than disabling rules globally.

CI: `.github/workflows/test.yml` runs `pytest` with `--cov=cbench --cov-report=term-missing --cov-fail-under=80` on Python 3.9–3.12 on pushes to `cbench/python/**` (coverage artifact uploaded on the 3.12 run). `.github/workflows/security.yml` runs ruff + bandit + pip-audit on the same paths. Keep coverage above 80% — the CI gate enforces it.

## Python package architecture (`cbench/python/cbench/`)

The package is structured around four independent layers:

### 1. Config (`config.py`)
`ClusterConfig` dataclass loaded from `cluster.yaml` (searched via `CBENCHOME`, `CBENCHTEST`, or `./`). The `$CBENCHCLUSTER` env var selects a named section. Falls back to defaults if no file found — tests rely on this.

### 2. Benchmark output parsers (`parsers/`)
Auto-registration via `__init_subclass__`: any subclass of `BenchmarkParser` that sets `names = [...]` is added to `REGISTRY` automatically. Each parser gets a `stdout: str` and returns a `ParseResult(status, metrics)`. Status values: `PASSED`, `ERROR(...)`, `NOTICE`, `NOTSTARTED`, `NO_PARSER`, `FILTER_ERROR`.

To add a new parser: create `parsers/mybench.py`, subclass `BenchmarkParser`, set `names`, import it in `parsers/__init__.py`. Job directories are named `<benchmark>-<ppn>ppn-<np>`; `get_parser()` tries an exact `names` match, then each parser's `alias_spec` regex (full match, ported from Perl `alias_spec()`), e.g. IOR's `(ior|ios).*` catches `ior1mNtoN`. `cbench parse` appends any `CBENCH CAVEAT:` lines from job output to `status_detail`, and reads each job's newest run (`_job_output_files()`: newest `*.o*`/`slurm-*.out` plus its matching `.e<id>`).

### 3. Parse filters (`parse_filters/`)
Seven modules (openmpi, slurm, torque, mvapich, mpiexec, cray, misc) each expose a `FILTERS: dict[str, str]` mapping regex patterns to message templates (`$1`, `$2` for capture groups). `build_filter_set(names)` merges them; `apply_filters(filters, text)` scans line-by-line and returns matched error strings. Wired into `cbench parse` via `--customparse` or `parse_filter_include` in `cluster.yaml`.

### 4. hw_test parsers (`hw_tests/`)
Used exclusively by `cbench nodehwtest parse`. Same auto-registration pattern as benchmark parsers but via `HwTest` base class with `name` and `test_class` class variables. Each `parse(lines: list[str])` returns `dict[str, float | str]`. The output file format uses `CBENCH MARK: MODULE <name>` delimiters — `cli/nodehwtest.py:_parse_run_file()` segments the file and dispatches to the right `HwTest`.

### 5. Database (`db.py`)
`ResultsDB` wraps SQLite with WAL mode and FK cascade deletes. Schema: `runs` table + `metrics` table (one row per metric per run). `store(ParseResult)` is idempotent-safe via `INSERT OR REPLACE` on a `UNIQUE` index of `(cluster, testset, ident, jobname, benchmark)` — re-parsing overwrites rather than duplicating. `deduplicate()` migrates pre-index databases. `trend(benchmark, metric)` returns per-ident averages ordered chronologically. The DB lives at `$CBENCHTEST/cbench_results.db`.

### 6. CLI (`cli/`)
Six subgroups wired into `cli/main.py`:
- `gen-jobs` / `start-jobs` / `parse` / `query` — MPI benchmark workflow
- `gen-jobs --profile` — IO profile bundles (§15); `gen-jobs --fio-runtime` overrides `fio_runtime_s`
- `start-jobs --interactive` runs the `.sh` scripts gen-jobs writes; `--echo-output` sets `CBENCH_ECHO_OUTPUT=YES` so `cbench_functions` tees job output to the terminal
- `nodehwtest gen-jobs` / `start-jobs` / `parse` — single-node hw test workflow
- `snb run` / `report` / `store` / `compare` — single-node benchmark suite
- `build run` / `build all` / `build list` / `build check` / `build update` — benchmark builder framework
- `serve` — Flask web dashboard (optional `cbench[web]` extra)
- `utils run-sizes` / `find-pq` / `find-n` / `npb-procs` — sizing utilities

### 7. Templates (`templates.py`)
`_here_to_jinja(text)` converts legacy `TOKEN_HERE` syntax in `*.in` template files to `{{ TOKEN }}` at load time — existing Perl templates work without modification. `RUN_SIZES` is the canonical list of proc counts used across generation and filtering.

### 8. Benchmark builders (`builders/`)
Auto-registration via `__init_subclass__` (same pattern as parsers). `BenchmarkBuilder` base class provides `fetch()`, `build()`, `check_requires()`, and `update_source()`. `update_source()` calls `git_pull()` from `_util.py` for git-cloned sources; tarball sources always return False. `BuildLock` (in `cli/build.py`) caches successful builds in `<prefix>/build.lock` (JSON) keyed by source URL + SHA-256 config hash. Available builders: `stream`, `imb`, `osu`, `ior`, `hpl`, `hpcc`, `npb`, `amg`, `hpccg`, `mpibench`, `mpigraph`, `graph500`, `bonnie`, `iozone`, `fio`, `gpfsperf` (optional — needs GPFS; see §15).

To add a new builder: create `builders/mybench.py`, subclass `BenchmarkBuilder`, set `name`, `description`, `source_url`, implement `fetch()` and `build()`, then import in `builders/__init__.py`.

### 9. Single-node benchmarks (`cli/snb.py`)
`cbench snb run` executes stream, cachebench, dgemm, mpistreams, linpack, npb, hpcc directly (no job scheduler). `_runcmd()` runs each test via `subprocess.Popen` with a poll loop that emits a "still running (elapsed)" heartbeat every `--heartbeat` seconds (default `_HEARTBEAT_SECS` = 30; `<=0` disables) so long tests are visibly alive, not mistakable for a hang. Linpack uses `_generate_hpl_dat()` to size HPL.dat to ~50% memory; output parsed by `XhplParser`. NPB runs `EP.B.x` and `CG.B.x`, appending to a single `.npb.out` file; output split by "NAS Parallel Benchmarks" sections and parsed by `NpbParser`. `--remote NODE` dispatches via ssh/pdsh using `remotecmd_method` from `cluster.yaml`; node name is validated (rejects `/`, `\\`, `..`, spaces). `--remote-cbench PATH` sets the cbench binary path on the remote.

**Node-aware fio I/O (opt-in).** fio is **not** in the default `--tests` suite — select it explicitly, and it then **requires** one or more `--fs-target PATH` (repeatable; `UsageError` otherwise). For each target, snb detects the filesystem type (`_detect_fstype()` — longest-mountpoint-prefix match in `/proc/self/mountinfo`; `unknown` off-Linux) and probes O_DIRECT support (`_supports_odirect()` — syscall probe). With O_DIRECT it uses a fixed 256 MiB per-job `--size` (`fioprofile.DATA_SIZE` — small because fio's file layout runs before `--runtime` starts) and first checks the target can hold the peak (`_fio_direct_space_shortfall()`: numjobs × 256 MiB within 90% of free) — if not, the target is skipped and recorded as a `NOTICE` row (marker `skipped=insufficient_space need_kb=.. usable_kb=..`); the target dir is emptied between the sequential and random runs (`_clean_fio_dir()`) so their files never coexist. On the buffered fallback it sizes the file to 2× `MemTotal` ÷ numjobs (`_fio_buffered_size_bytes()`), capping to 90% of free space and flagging a cache-influenced caveat. The job set comes from `fioprofile.py` (shared with gen-jobs, §14). Random-I/O and metadata jobs use `--numjobs = min(numcores, 16)`, and the sequential job stays single-stream; `--fio-profile`/`--fio-runtime` override the cluster.yaml `fio_profile`/`fio_runtime_s`. Each target's fio output is written to the single `out("fio")` file preceded by a `### CBENCH FS-TARGET path=.. fstype=.. odirect=.. caveat=..` marker; `_parse_fio_targets()` splits it into one result per target with `benchmark = snb_fio_{fstype}_{basename}` (node identity stays in `jobname`) and the path/fstype/caveat recorded in `status_detail`. FS type can't be a metric — the `metrics.value` column is `REAL`-only.

### 10. Web dashboard (`cli/serve.py`)
Flask app (optional `cbench[web]`). Routes: `/` HTML dashboard, `/api/summary`, `/api/results`, `/api/trend`, `/metrics` (Prometheus text format), `/static/<file>` (local assets). `--no-cdn` avoids CDN; `--assets-dir` serves local Bootstrap/Chart.js. Dashboard JS uses `esc()` to HTML-escape all DB-sourced values before `innerHTML` assignment (XSS prevention). Prometheus label values are escaped via `_prom_label()` (`"` → `\"`, `\n` → `\\n`).

### 11. Node precheck (`nodecheck.py`, `cli/nodecheck.py`, `hostlist.py`)
`cbench nodecheck --nodelist 'zima[1-4]' | --partition P` probes every node in a pool and writes `$CBENCHTEST/nodefacts/<name>.json` (name defaults to `cluster_name`) for gen-jobs, which runs on the submit host and can't see compute nodes. Transport: pdsh with `-R <remotecmd_rcmd>` (`ssh` default; `exec` uses the `remotecmd_exec_cmd` template, which must contain `%h`), or a serial ssh loop when `remotecmd_method: ssh`; `check_pdsh_rcmd()` parses `pdsh -V` and names the missing `pdsh-rcmd-*` RPM. The probe script ships base64-encoded (`remote_shell_command()` / `exec_command_suffix()`) so it survives any login shell and pdsh's argument joining. Per node it collects logical CPUs (`processor` lines), MemTotal, CPU model, and each `io_targets` entry's fstype (`findmnt -T`, fallback `stat -f`) + free space, ending with a `cbench_probe=ok` sentinel. `analyze()`: CPU count must match exactly, MemTotal within `MEM_TOLERANCE` (2%), model mismatch warns, missing/mixed-fstype targets and unreachable/incomplete nodes are hard errors; `--allow-heterogeneous` downgrades CPU/mem mismatch to a warning (consumers: IO sizing uses max MemTotal, non-IO uses min, CPUs use min). `group_summary()` replicates `dshbak -c`. `load_facts()` refuses failed verdicts and warns past `STALE_DAYS` (30). `hostlist.expand()`/`compress()` handle multi-group pdsh/Slurm hostlists (`n[1-3],m[01-02]`); `nodehwtest._expand_pdsh` delegates to it. `ClusterConfig.explicit_keys` records which keys came from cluster.yaml (vs built-in defaults).

### 12. Node-aware IO sizing in gen-jobs (`iosizing.py`)
`gen-jobs --nodefacts NAME|PATH` loads a nodecheck facts file; `resolve_node_values()` gives IO sizing the MAX MemTotal, memory-sized work the MIN, and CPU counts the MIN. Without facts, values come from cluster.yaml only if listed in `cfg.explicit_keys` — built-in defaults are never used for sizing, and a sized testset with no memory source fails **before anything is rendered** (jinja `Undefined` would otherwise turn a missing token into an empty string). Tokens go in through `substitute(extra=...)`: `IOR_BLOCKSIZE` (`io_ior*`: `-b = 2×MemTotal/ppn`, rounded UP to a multiple of `-t` 128m), `BONNIE_SIZE_MB`/`BONNIE_RAM_MB` (3 concurrent instances write 2× RAM in aggregate; `-s` up, `-r` down, `-s ≥ 2·-r`), `IO_REQUIRED_KB`, `IO_CAVEAT`, `IO_TARGET_DIR`, and `TESTDIR` for IOR. Rule of thumb: **IO rounds up, memory rounds down.** Sizes that exceed 90% of the free space nodecheck saw are capped, warned at gen time, and carry a `CBENCH CAVEAT:` line. Targets: IOR/mdtest → `io_targets.parallel`, bonnie → `io_targets.node-local`; cluster.yaml decides paths, facts only supply free space when they probed the same path. `iosanity_*` keeps its small fixed size (still uses the target dir). For testsets with an mdtest template, the measured CPU count replaces `procs_per_node` as the top ppn level and higher levels are dropped. Every sized job calls `cbench_io_preflight` (defined in `common_header.in`, **not** `cbench_functions` — that file is deployed separately and could be stale) to `df` the target right before running and exit with `CBENCH NOTICE: insufficient space` if it shrank. `compute_n()` rounds N down (no Perl ×1.02); `cbench utils find-n --nodefacts` uses the MIN MemTotal.

### 14. fio job set (`fioprofile.py`)
fio is the default node-local IOPS + metadata test, in both `snb` and gen-jobs (`templates/iometadata_fio.in`). Jobs, one fio invocation each, all `--group_reporting`:
- `seq_rw`: sequential read/write at the profile block size.
- `rand_rw`: 4k random read/write.
- `md_create`/`md_stat`/`md_delete`: fio `filecreate`/`filestat`/`filedelete` engines (fio ≥ 3.23; if missing, a caveat, not a failure).

Timing and job counts:
- Data jobs are `--time_based --runtime=fio_runtime_s` (default 300 s).
- Metadata jobs are bounded by `nrfiles`, because a time-based delete would run out of files.
- numjobs = `min(cpus, 16)`.
- The target is emptied between jobs, so the peak is numjobs × the per-job file: 256 MiB with O_DIRECT. That is small because `--runtime` does not cover fio's up-front file layout, which took ~2.5 min for 4 × 1 GiB on zima xfs. Buffered runs use larger files (snb: 2× MemTotal; the job script: 1 GiB).
- The job script probes O_DIRECT before its preflight, so it checks the size it will actually use.

Sequential block size comes from `fio_profile`:
- `ai` 1m, `general` 4m, `hpc` 8m, `streaming` 16m.
- `auto` (default) picks `hpc` on gpfs/lustre/panfs/beegfs/ceph, else `general`.
- `fio_seq_bs` overrides it exactly.

`FioParser` splits output by these job names into metrics:
- `seq_read/write_bw_MiB_s`
- `rand_{read,write}_{iops,bw_MiB_s,lat_avg_us,lat_p99_us}`
- `create/stat/delete_ops`

Other fio output falls back to generic first-block metrics.

gen-jobs specifics:
- It generates fio once per testset (`_SINGLE_INSTANCE`, `fio-<ppn>ppn-1`).
- `iosizing.fio_tokens()` needs a CPU count (facts or explicit `procs_per_node`) and warns at gen time if the node-local target is short.
- The job probes O_DIRECT itself and falls back to buffered I/O with a `CBENCH CAVEAT`.
- The job script prints `Cbench fio: profile=…` at start and `Cbench fio: finished` at end. `FioParser` returns `ERROR(STARTED)` for output with the first and not the second (snb output has neither).
- `fileop` is in `_DEFAULT_SKIP` (the Perl tools still use its template), so it is generated only via `--match`, which filters job names (Perl parity).

### 15. IO profiles and the IO thread rule (`profiles.py`, `iosizing.io_threads`)
`gen-jobs --profile NAME [--group G ...]` treats a profile as a *virtual testset*: each member renders from its home template (`<home>_<bench>.in`), but every job goes under `$CBENCHTEST/<profile>/<ident>/`, so `start-jobs`, `parse` and `query` take `--testset <profile>` unchanged.

Groups in `io-default`:
- `node-local`: fio, bonnie, iozone. This is the default group.
- `parallel`: ior1mNtoN, mdtest.
- `gpfs`: gpfsperf.

`--group all` selects every group. A group whose target isn't available is skipped with a warning. The `gpfs` target is `io_targets.gpfs`, else `io_targets.parallel` when the node facts say it's GPFS (`iosizing._gpfs_alias`), so gen-jobs resolves node values before choosing groups. Job names are group-qualified (`fio-local-1ppn-1`), and `get_parser()` strips a trailing `-<qualifier>` when the name doesn't match exactly or via an alias.

**`io_threads(nv, cfg)`** is the single concurrency rule for every IO benchmark:
- What it sets: fio `--numjobs`, bonnie instances (`BONNIE_INSTANCES`, with sizes split across them), iozone `-t`, gpfsperf `-th`, and the mdtest top ppn level.
- The count: all CPUs on the smallest node. `io_threads_basis: logical` (the default) or `physical` uses physical cores from nodecheck facts v2, falling back to logical with a warning.
- The cap: `io_threads_max` if set. There is no built-in cap.
- snb applies the same rule locally (`_detect_physical_cores()`, `cap_threads`).

nodecheck facts **schema v2** adds per-node `cores` (distinct physical id/core id pairs) and `aggregate.cores`; v1 files still load. A physical-core mismatch at equal logical count (SMT differs) counts as heterogeneous. fio, bonnie, iozone and gpfsperf are `_SINGLE_INSTANCE`: one job per testset or profile, not one per ppn × size.

**iozone** (`templates/iolocal_iozone.in`, `parsers/iozone.py`):
- Runs throughput mode `-i 0 -i 1 -i 2 -t N`, with 2× RAM ÷ N per thread, rounded up to the record size, which is the fio profile block size.
- The parser records each test's "Children see" aggregate in MiB/s; without `iozone test complete.` the job is `ERROR(STARTED)`.
- The binary is looked up in `bin/`, `bin/hwtests/` (where the builder installs it), then PATH.

**gpfsperf** (`templates/iogpfs_gpfsperf.in`):
- Runs create seq, read seq, read rand and write rand on one 2× RAM file, with `-r` = the profile block size (8m on GPFS).
- The parser prefixes metrics `<op>_<pattern>_` when one output holds several operations.
- The job uses `$CBENCHTEST/bin/gpfsperf` if you built one, else the binary GPFS ships in `/usr/lpp/mmfs/samples/perf`.
- The `gpfsperf` builder copies those samples and runs `make gpfsperf`. You only need it for variants such as RDMA; `--extra cflags=...` replaces the makefile CFLAGS.
- Builders with `optional = True` (gpfsperf) are SKIPPED by `build all` when their prerequisites are missing.

Token gotcha: `TOKEN_HERE` must end at a word boundary. A token glued to a unit (`SIZE_HEREm`) is not substituted, so size tokens carry their unit (`IOZONE_SIZE=1668m`).

### 13. HPL input files in gen-jobs (`hplsizing.py`)
Port of Perl `xhpl_gen_innerloop`/`hpcc_gen_innerloop`. For `xhpl`, `xhpl2`, `xhplintel` (→ `HPL.dat` from `templates/xhpl_dat.in`) and `hpcc` (→ `hpccinf.txt` from `hpccinf_txt.in`), gen-jobs writes the input file into each job dir (job scripts `cd` there). N: one per `memory_util_factors` entry via `compute_n()`, from the MIN MemTotal (`--nodefacts`) or explicit `memory_per_node_mb` — same no-silent-defaults rule and fail-before-render check as IO. `shakedown` uses a single 0.45 factor (and `MEM_UTIL_FACTORS` is overridden so the job echoes it). P×Q: `utils.compute_pq()` (Perl `compute_PQ`: square, else first Q in (√n, 3√n] dividing n); a proc count with no grid is skipped with a warning (none of `RUN_SIZES` hit this). `XHPL_BIN`/`XHPL2_BIN`/`XHPLINTEL_BIN`/`HPCC_BIN` are bare binary names — templates prefix `CBENCHTEST_BIN_HERE/`.

## Key environment variables

| Variable | Purpose |
|---|---|
| `CBENCHOME` | Root of the cbench installation (contains `cluster.yaml`, `perllib/`, `templates/`) |
| `CBENCHTEST` | Root of the test output tree; also searched for `cluster.yaml` |
| `CBENCHCLUSTER` | Selects a named cluster section within `cluster.yaml` |

## Security baseline

These decisions are intentional — do not re-flag as vulnerabilities:
- `--mpi-cmd`, `--remote-cbench`, `--assets-dir` are CLI flags controlled by the cluster operator. They are trusted input; no validation beyond what the OS enforces.
- `send_from_directory(assets_dir, filename)` — Flask's `safe_join` prevents path traversal within the dir; the dir itself is operator-chosen at startup.
- Dashboard JS uses `esc()` to HTML-escape all DB-sourced values before `innerHTML` assignment.
- Prometheus label values are escaped via `_prom_label()` in `cli/serve.py`.
- Tarball downloads (`builders/_util.py:download()`) are https-only with a 120 s timeout; the zip-slip guard validates every member path *and* symlink/hardlink target with `Path.is_relative_to` before `extractall`.
- All path-containment checks use `Path.is_relative_to` (never `str.startswith`, which has a `/a/b` vs `/a/bc` prefix-collision).
- `cluster_name` in `cluster.yaml` is restricted to `[A-Za-z0-9_-]+` by JSON Schema validation.
- `--node`/`--remote` hostname arguments reject `/`, `\\`, `..`, and spaces.
- `snb.py:_runcmd()` accepts str (shell=True) only for hardcoded commands; user-derived args must be lists. Annotated `noqa: S602` / `nosec B602`.
- Vetted scanner false positives (parameterized SQL in `db.py`, the validated `extractall`, the https-only `urlopen`) carry inline `noqa`+`nosec` markers with justifications — keep `ruff check` and `bandit` at zero findings rather than suppressing rules globally.

## Error-handling policy

Silent failures are converted to explicit errors: conditions indicating corrupt state (bad `target_hw_values` lines, malformed `parsed_at` DB timestamps, failed batch submissions, missing `jsonschema`) raise `AssertionError` at the point of failure. Benchmark-output parsers stay tolerant of unparseable lines by design — third-party benchmark output is messy; skipping a bad line there is not a silent failure.

## Adding a benchmark parser (checklist)

1. Create `cbench/python/cbench/parsers/mybench.py` with a `BenchmarkParser` subclass, `names = ["mybench"]`, and implement `parse(stdout, stderr) -> ParseResult` and `metric_units() -> dict`.
2. Add `from cbench.parsers import mybench  # noqa: F401` in `cbench/python/cbench/parsers/__init__.py`.
3. Add tests in `cbench/python/tests/test_parsers_extended.py` with a sample output fixture.

## Perl toolchain (read-only context)

The original Perl toolchain lives in `cbench/cbench.pl` (core library), `cbench/tools/*.pl` (scripts), and `cbench/perllib/` (modules). Do not modify these unless fixing a Perl-specific bug. The Python toolchain is additive — it does not replace the Perl scripts.

Key Perl concepts that have Python equivalents:
- `cluster.def` → `cluster.yaml` + `config.py`
- `perllib/output_parse/*.pm` → `cbench/python/cbench/parsers/`
- `perllib/parse_filter/*.pm` → `cbench/python/cbench/parse_filters/`
- `perllib/hw_test/*.pm` → `cbench/python/cbench/hw_tests/`
- `cbench.pl:std_substitute()` → `templates.py:substitute()`
- `cbench.pl:compute_N()` → `utils.py:compute_n()`
