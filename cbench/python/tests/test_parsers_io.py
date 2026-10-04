"""IOR / mdtest / bonnie++ parsers against real current-version output.

Fixtures in tests/fixtures/io/ are unedited job output (usernames scrubbed)
from the zima test cluster: IOR-4.1.0+dev and mdtest-4.1.0+dev from the
unified hpc/ior repo, and bonnie++ 2.00a run by the iometadata template.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest
from click.testing import CliRunner

from cbench.cli.main import cli
from cbench.parsers import get_parser
from cbench.parsers.base import ALIASES
from cbench.parsers.bonnie import BonnieParser
from cbench.parsers.ior import IorParser
from cbench.parsers.mdtest import MdtestParser

FIXTURES = Path(__file__).parent / "fixtures" / "io"


def _fixture(name: str) -> str:
    return (FIXTURES / f"{name}.txt").read_text()


# ---------------------------------------------------------------------------
# parser lookup (alias_spec)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bench, cls", [
    ("ior1mNtoN", IorParser),     # io / iosanity job names
    ("ior1mNto1", IorParser),
    ("iosanity", IorParser),
    ("iostress", IorParser),      # shakedown
    ("bonnie", BonnieParser),
    ("mdtest", MdtestParser),
])
def test_io_job_names_resolve_to_parsers(bench, cls):
    assert isinstance(get_parser(bench), cls)


@pytest.mark.parametrize("bench", ["prior", "iozonex", "nosuchbench"])
def test_alias_must_match_whole_name(bench):
    assert get_parser(bench) is None


def test_iozone_is_not_caught_by_the_ior_alias():
    assert type(get_parser("iozone")).__name__ == "IozoneParser"


@pytest.mark.parametrize("bench, parser", [
    ("cgC", "NpbParser"), ("xhpl_big", "XhplParser"), ("xhpl2-x", "XhplParser"),
    ("osubibw", "OsuParser"), ("mpibenchbcast", "MpibenchParser"),
    ("32cubed", "HpccgParser"), ("imbcust", "ImbParser"),
    ("mpi_simple", "Graph500Parser"), ("rhodo", "LammpsParser"),
])
def test_perl_alias_specs_ported(bench, parser):
    assert type(get_parser(bench)).__name__ == parser


def test_alias_specs_compile_and_are_unique_per_class():
    classes = [cls for _, cls in ALIASES]
    assert len(classes) == len(set(classes))


# ---------------------------------------------------------------------------
# IOR
# ---------------------------------------------------------------------------

def test_ior_modern_file_per_process():
    r = IorParser().parse(_fixture("ior_nton"))
    assert r.status == "PASSED"
    # the MB/s figure from "Max Write:", not the MiB/s "Summary of all tests" row
    assert r.metrics == {"write": pytest.approx(89.92), "read": pytest.approx(2470.99)}


def test_ior_modern_shared_file():
    r = IorParser().parse(_fixture("ior_nto1"))
    assert r.status == "PASSED"
    assert r.metrics == {"write": pytest.approx(126.26), "read": pytest.approx(2237.62)}


def test_ior_modern_unfinished_run_is_error():
    text = "\n".join(
        line for line in _fixture("ior_nton").splitlines() if not line.startswith("Finished")
    )
    assert IorParser().parse(text).status == "ERROR(STARTED)"


# ---------------------------------------------------------------------------
# mdtest
# ---------------------------------------------------------------------------

def test_mdtest_modern_rate_summary():
    r = MdtestParser().parse(_fixture("mdtest"))
    assert r.status == "PASSED"
    assert len(r.metrics) == 10
    assert r.metrics["directory_create"] == pytest.approx(648.277)
    assert r.metrics["directory_rename"] == pytest.approx(1986.877)
    assert r.metrics["file_read"] == pytest.approx(91660.822)
    assert r.metrics["tree_remove"] == pytest.approx(432.437)
    assert set(r.metrics) <= set(MdtestParser().metric_units())


def test_mdtest_ignores_time_summary_table():
    time_table = (
        "SUMMARY time (in sec): (of 50 iterations)\n"
        "   Directory creation             0.050          0.010          0.020          0.005\n"
    )
    r = MdtestParser().parse(_fixture("mdtest") + time_table)
    assert r.metrics["directory_create"] == pytest.approx(648.277)


def test_mdtest_launched_but_no_summary_is_error():
    first = _fixture("mdtest").splitlines()[0]
    assert MdtestParser().parse(first).status == "ERROR(STARTED)"


# ---------------------------------------------------------------------------
# bonnie++
# ---------------------------------------------------------------------------

def test_bonnie_2x_rows_summed_across_instances():
    r = BonnieParser().parse(_fixture("bonnie"))
    assert r.status == "PASSED"
    assert r.metrics["instances"] == 3
    assert r.metrics["sequential_write_char"] == pytest.approx(604 + 497 + 646)
    assert r.metrics["sequential_write_block"] == pytest.approx(9633 + 9433 + 9406)
    assert r.metrics["sequential_read_block"] == pytest.approx(53023 + 52383 + 51801)
    assert r.metrics["random_seeks"] == pytest.approx(1447 + 1524 + 1262)
    assert r.metrics["sequential_create"] == pytest.approx(5247 + 5248 + 5248)
    assert r.metrics["random_delete"] == pytest.approx(10570 + 10570 + 10572)


def test_bonnie_too_fast_field_drops_only_that_metric():
    r = BonnieParser().parse(_fixture("bonnie"))
    # the stat columns are +++++ in every row: omitted, and said so
    assert "sequential_create_read" not in r.metrics
    assert "random_create_read" not in r.metrics
    assert "sequential_create_read" in r.status_detail
    assert "random_create_read" in r.status_detail


def test_bonnie_partially_too_fast_metric_is_not_summed_short():
    rows = [line for line in _fixture("bonnie").splitlines() if line.startswith("1.98")]
    a = rows[0].split(",")
    a[9] = "+++++"  # putc too fast in one instance only
    r = BonnieParser().parse("\n".join([",".join(a), *rows[1:]]))
    assert r.status == "PASSED"
    assert "sequential_write_char" not in r.metrics
    assert r.metrics["sequential_write_block"] == pytest.approx(9633 + 9433 + 9406)


def test_bonnie_no_result_rows_is_error():
    r = BonnieParser().parse("Using uid:1000, gid:1000.\nWriting a byte at a time...")
    assert r.status == "ERROR(STARTED)"


def test_bonnie_units_cover_metrics():
    r = BonnieParser().parse(_fixture("bonnie"))
    assert set(r.metrics) <= set(BonnieParser().metric_units())


# ---------------------------------------------------------------------------
# cbench parse: end to end, including CBENCH CAVEAT capture
# ---------------------------------------------------------------------------

def _job(base: Path, testset: str, jobname: str, stdout: str) -> None:
    d = base / testset / "zima" / jobname
    d.mkdir(parents=True)
    (d / "job.o1").write_text(stdout)


def test_parse_cli_io_jobs_pass_and_keep_caveat(tmp_path):
    _job(tmp_path, "iosanity", "ior1mNtoN-4ppn-4", _fixture("ior_nton"))
    _job(tmp_path, "iosanity", "ior1mNto1-4ppn-4", _fixture("ior_nto1"))
    _job(tmp_path, "iometadata", "mdtest-4ppn-4", _fixture("mdtest"))
    _job(tmp_path, "iometadata", "bonnie-1ppn-1", _fixture("bonnie"))

    for testset in ("iosanity", "iometadata"):
        res = CliRunner().invoke(cli, [
            "parse", "--testset", testset, "--ident", "zima", "--cbenchtest", str(tmp_path),
        ])
        assert res.exit_code == 0, res.output

    con = sqlite3.connect(tmp_path / "cbench_results.db")
    rows = dict(con.execute("SELECT jobname, status FROM runs").fetchall())
    assert rows == dict.fromkeys(
        ["ior1mNtoN-4ppn-4", "ior1mNto1-4ppn-4", "mdtest-4ppn-4", "bonnie-1ppn-1"], "PASSED"
    )
    (detail,) = con.execute(
        "SELECT status_detail FROM runs WHERE jobname = 'bonnie-1ppn-1'"
    ).fetchone()
    assert re.search(r"too fast to measure.*; CBENCH CAVEAT: bonnie\+\+ size capped", detail)
    (ior_detail,) = con.execute(
        "SELECT status_detail FROM runs WHERE jobname = 'ior1mNtoN-4ppn-4'"
    ).fetchone()
    assert "CAVEAT" not in (ior_detail or "")
