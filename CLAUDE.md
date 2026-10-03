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
- **Current focus:** _Perl→Python port is feature-complete; repo is post-hardening and CI-green on `v2.0`. No work in flight._
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

To add a new parser: create `parsers/mybench.py`, subclass `BenchmarkParser`, set `names`, import it in `parsers/__init__.py`.

### 3. Parse filters (`parse_filters/`)
Seven modules (openmpi, slurm, torque, mvapich, mpiexec, cray, misc) each expose a `FILTERS: dict[str, str]` mapping regex patterns to message templates (`$1`, `$2` for capture groups). `build_filter_set(names)` merges them; `apply_filters(filters, text)` scans line-by-line and returns matched error strings. Wired into `cbench parse` via `--customparse` or `parse_filter_include` in `cluster.yaml`.

### 4. hw_test parsers (`hw_tests/`)
Used exclusively by `cbench nodehwtest parse`. Same auto-registration pattern as benchmark parsers but via `HwTest` base class with `name` and `test_class` class variables. Each `parse(lines: list[str])` returns `dict[str, float | str]`. The output file format uses `CBENCH MARK: MODULE <name>` delimiters — `cli/nodehwtest.py:_parse_run_file()` segments the file and dispatches to the right `HwTest`.

### 5. Database (`db.py`)
`ResultsDB` wraps SQLite with WAL mode and FK cascade deletes. Schema: `runs` table + `metrics` table (one row per metric per run). `store(ParseResult)` is idempotent-safe via `INSERT OR REPLACE` on a `UNIQUE` index of `(cluster, testset, ident, jobname, benchmark)` — re-parsing overwrites rather than duplicating. `deduplicate()` migrates pre-index databases. `trend(benchmark, metric)` returns per-ident averages ordered chronologically. The DB lives at `$CBENCHTEST/cbench_results.db`.

### 6. CLI (`cli/`)
Six subgroups wired into `cli/main.py`:
- `gen-jobs` / `start-jobs` / `parse` / `query` — MPI benchmark workflow
- `nodehwtest gen-jobs` / `start-jobs` / `parse` — single-node hw test workflow
- `snb run` / `report` / `store` / `compare` — single-node benchmark suite
- `build run` / `build all` / `build list` / `build check` / `build update` — benchmark builder framework
- `serve` — Flask web dashboard (optional `cbench[web]` extra)
- `utils run-sizes` / `find-pq` / `find-n` / `npb-procs` — sizing utilities

### 7. Templates (`templates.py`)
`_here_to_jinja(text)` converts legacy `TOKEN_HERE` syntax in `*.in` template files to `{{ TOKEN }}` at load time — existing Perl templates work without modification. `RUN_SIZES` is the canonical list of proc counts used across generation and filtering.

### 8. Benchmark builders (`builders/`)
Auto-registration via `__init_subclass__` (same pattern as parsers). `BenchmarkBuilder` base class provides `fetch()`, `build()`, `check_requires()`, and `update_source()`. `update_source()` calls `git_pull()` from `_util.py` for git-cloned sources; tarball sources always return False. `BuildLock` (in `cli/build.py`) caches successful builds in `<prefix>/build.lock` (JSON) keyed by source URL + SHA-256 config hash. Available builders: `stream`, `imb`, `osu`, `ior`, `hpl`, `hpcc`, `npb`, `amg`, `hpccg`, `mpibench`, `mpigraph`, `graph500`, `bonnie`, `iozone`, `fio`.

To add a new builder: create `builders/mybench.py`, subclass `BenchmarkBuilder`, set `name`, `description`, `source_url`, implement `fetch()` and `build()`, then import in `builders/__init__.py`.

### 9. Single-node benchmarks (`cli/snb.py`)
`cbench snb run` executes stream, cachebench, dgemm, mpistreams, linpack, npb, hpcc directly (no job scheduler). `_runcmd()` runs each test via `subprocess.Popen` with a poll loop that emits a "still running (elapsed)" heartbeat every `--heartbeat` seconds (default `_HEARTBEAT_SECS` = 30; `<=0` disables) so long tests are visibly alive, not mistakable for a hang. Linpack uses `_generate_hpl_dat()` to size HPL.dat to ~50% memory; output parsed by `XhplParser`. NPB runs `EP.B.x` and `CG.B.x`, appending to a single `.npb.out` file; output split by "NAS Parallel Benchmarks" sections and parsed by `NpbParser`. `--remote NODE` dispatches via ssh/pdsh using `remotecmd_method` from `cluster.yaml`; node name is validated (rejects `/`, `\\`, `..`, spaces). `--remote-cbench PATH` sets the cbench binary path on the remote.

**Node-aware fio I/O (opt-in).** fio is **not** in the default `--tests` suite — select it explicitly, and it then **requires** one or more `--fs-target PATH` (repeatable; `UsageError` otherwise). For each target, snb detects the filesystem type (`_detect_fstype()` — longest-mountpoint-prefix match in `/proc/self/mountinfo`; `unknown` off-Linux) and probes O_DIRECT support (`_supports_odirect()` — syscall probe). With O_DIRECT it keeps the fixed `--size`; on the buffered fallback it sizes the file to 2× `MemTotal` ÷ numjobs (`_fio_buffered_size_bytes()`), capping to 90% of free space and flagging a cache-influenced caveat. The random-I/O job's `--numjobs` tracks node cores (`min(numcores, 16)`) so each node is driven proportional to its size; the sequential job stays single-stream (`numjobs=1`). Each target's fio output is written to the single `out("fio")` file preceded by a `### CBENCH FS-TARGET path=.. fstype=.. odirect=.. caveat=..` marker; `_parse_fio_targets()` splits it into one result per target with `benchmark = snb_fio_{fstype}_{basename}` (node identity stays in `jobname`) and the path/fstype/caveat recorded in `status_detail`. FS type can't be a metric — the `metrics.value` column is `REAL`-only.

### 10. Web dashboard (`cli/serve.py`)
Flask app (optional `cbench[web]`). Routes: `/` HTML dashboard, `/api/summary`, `/api/results`, `/api/trend`, `/metrics` (Prometheus text format), `/static/<file>` (local assets). `--no-cdn` avoids CDN; `--assets-dir` serves local Bootstrap/Chart.js. Dashboard JS uses `esc()` to HTML-escape all DB-sourced values before `innerHTML` assignment (XSS prevention). Prometheus label values are escaped via `_prom_label()` (`"` → `\"`, `\n` → `\\n`).

### 11. Node precheck (`nodecheck.py`, `cli/nodecheck.py`, `hostlist.py`)
`cbench nodecheck --nodelist 'zima[1-4]' | --partition P` probes every node in a pool and writes `$CBENCHTEST/nodefacts/<name>.json` (name defaults to `cluster_name`) for gen-jobs, which runs on the submit host and can't see compute nodes. Transport: pdsh with `-R <remotecmd_rcmd>` (`ssh` default; `exec` uses the `remotecmd_exec_cmd` template, which must contain `%h`), or a serial ssh loop when `remotecmd_method: ssh`; `check_pdsh_rcmd()` parses `pdsh -V` and names the missing `pdsh-rcmd-*` RPM. The probe script ships base64-encoded (`remote_shell_command()` / `exec_command_suffix()`) so it survives any login shell and pdsh's argument joining. Per node it collects logical CPUs (`processor` lines), MemTotal, CPU model, and each `io_targets` entry's fstype (`findmnt -T`, fallback `stat -f`) + free space, ending with a `cbench_probe=ok` sentinel. `analyze()`: CPU count must match exactly, MemTotal within `MEM_TOLERANCE` (2%), model mismatch warns, missing/mixed-fstype targets and unreachable/incomplete nodes are hard errors; `--allow-heterogeneous` downgrades CPU/mem mismatch to a warning (consumers: IO sizing uses max MemTotal, non-IO uses min, CPUs use min). `group_summary()` replicates `dshbak -c`. `load_facts()` refuses failed verdicts and warns past `STALE_DAYS` (30). `hostlist.expand()`/`compress()` handle multi-group pdsh/Slurm hostlists (`n[1-3],m[01-02]`); `nodehwtest._expand_pdsh` delegates to it. `ClusterConfig.explicit_keys` records which keys came from cluster.yaml (vs built-in defaults).

### 12. Node-aware IO sizing in gen-jobs (`iosizing.py`)
`gen-jobs --nodefacts NAME|PATH` loads a nodecheck facts file; `resolve_node_values()` gives IO sizing the MAX MemTotal, memory-sized work the MIN, and CPU counts the MIN. Without facts, values come from cluster.yaml only if listed in `cfg.explicit_keys` — built-in defaults are never used for sizing, and a sized testset with no memory source fails **before anything is rendered** (jinja `Undefined` would otherwise turn a missing token into an empty string). Tokens go in through `substitute(extra=...)`: `IOR_BLOCKSIZE` (`io_ior*`: `-b = 2×MemTotal/ppn`, rounded UP to a multiple of `-t` 128m), `BONNIE_SIZE_MB`/`BONNIE_RAM_MB` (3 concurrent instances write 2× RAM in aggregate; `-s` up, `-r` down, `-s ≥ 2·-r`), `IO_REQUIRED_KB`, `IO_CAVEAT`, `IO_TARGET_DIR`, and `TESTDIR` for IOR. Rule of thumb: **IO rounds up, memory rounds down.** Sizes that exceed 90% of the free space nodecheck saw are capped, warned at gen time, and carry a `CBENCH CAVEAT:` line. Targets: IOR/mdtest → `io_targets.parallel`, bonnie → `io_targets.node-local`; cluster.yaml decides paths, facts only supply free space when they probed the same path. `iosanity_*` keeps its small fixed size (still uses the target dir). For testsets with an mdtest template, the measured CPU count replaces `procs_per_node` as the top ppn level and higher levels are dropped. Every sized job calls `cbench_io_preflight` (defined in `common_header.in`, **not** `cbench_functions` — that file is deployed separately and could be stale) to `df` the target right before running and exit with `CBENCH NOTICE: insufficient space` if it shrank. `compute_n()` rounds N down (no Perl ×1.02); `cbench utils find-n --nodefacts` uses the MIN MemTotal. Python gen-jobs does **not** yet generate HPL.dat (separate PR).

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
