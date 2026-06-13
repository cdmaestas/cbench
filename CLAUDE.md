# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository overview

Cbench is an HPC benchmarking framework. v2.0 adds a Python toolchain alongside the original Perl scripts (which remain intact and functional). All new work goes in `cbench/python/`.

**Branch layout:**
- `main` — canonical branch with all commits
- `v2.0` — active development branch (Python toolchain)
- `v1.3.0` — tag at the original Perl-only commit

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

There is no linter or formatter configured. CI runs `pytest` on Python 3.9–3.12 via `.github/workflows/test.yml` on pushes to `cbench/python/**`.

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
`ResultsDB` wraps SQLite with WAL mode and FK cascade deletes. Schema: `runs` table + `metrics` table (one row per metric per run). `store(ParseResult)` is idempotent-safe via INSERT OR REPLACE on `(cluster, testset, ident, jobname)`. The DB lives at `$CBENCHTEST/cbench_results.db`.

### 6. CLI (`cli/`)
Four subgroups wired into `cli/main.py`:
- `gen-jobs` / `start-jobs` / `parse` / `query` — MPI benchmark workflow
- `nodehwtest gen-jobs` / `start-jobs` / `parse` — single-node hw test workflow  
- `utils run-sizes` / `find-pq` / `find-n` / `npb-procs` — sizing utilities

### 7. Templates (`templates.py`)
`_here_to_jinja(text)` converts legacy `TOKEN_HERE` syntax in `*.in` template files to `{{ TOKEN }}` at load time — existing Perl templates work without modification. `RUN_SIZES` is the canonical list of proc counts used across generation and filtering.

## Key environment variables

| Variable | Purpose |
|---|---|
| `CBENCHOME` | Root of the cbench installation (contains `cluster.yaml`, `perllib/`, `templates/`) |
| `CBENCHTEST` | Root of the test output tree; also searched for `cluster.yaml` |
| `CBENCHCLUSTER` | Selects a named cluster section within `cluster.yaml` |

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
