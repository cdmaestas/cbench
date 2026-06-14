"""cbench serve — lightweight web dashboard for Cbench results.

Requires the optional 'web' extra:
    pip install "cbench[web]"

Endpoints:
  GET /           — HTML dashboard (auto-refreshes every 30 s)
  GET /api/summary    — JSON summary counts
  GET /api/results    — JSON run list (supports benchmark/cluster/testset/ident/status/since/until/limit params)
  GET /api/trend      — JSON trend series (benchmark + metric required)
  GET /metrics        — Prometheus text exposition format
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import click

_HTML_CDN_HEADER = """  <link rel="stylesheet"
        href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css">
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>"""

# Minimal inline CSS used when --no-cdn is set and no local assets are present
_HTML_MINIMAL_STYLE = """  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{background:#0d1117;color:#c9d1d9;font-family:monospace;padding:1rem}
    h1{color:#f0f6fc;font-size:1.25rem;margin-bottom:1rem}
    .row{display:flex;flex-wrap:wrap;gap:.5rem;margin-bottom:1rem}
    .card{background:#161b22;border:1px solid #30363d;padding:1rem;min-width:150px}
    .fs-2{font-size:1.5rem;font-weight:bold}
    .text-success{color:#3fb950}.text-danger{color:#f85149}
    .text-muted{color:#8b949e;font-size:.75rem}
    table{width:100%;border-collapse:collapse;background:#161b22;margin-bottom:1rem}
    th,td{padding:.4rem .6rem;border:1px solid #30363d;font-size:.8rem}
    th{color:#8b949e;text-transform:uppercase}
    .badge-pass{color:#3fb950}.badge-err{color:#f85149}
    input,select{background:#0d1117;color:#c9d1d9;border:1px solid #30363d;padding:.3rem;font-size:.8rem}
    button{background:#1f6feb;color:#fff;border:none;padding:.3rem .8rem;cursor:pointer;font-size:.8rem}
    canvas{background:#161b22;border:1px solid #30363d;margin-top:.5rem}
    .metric-val{color:#79c0ff}
    .no-cdn-notice{background:#2d1a00;border:1px solid #bb8009;color:#e3b341;padding:.5rem;margin-bottom:1rem;font-size:.8rem}
  </style>"""

_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Cbench Dashboard</title>
  <!-- ASSETS_HERE -->
  <style>
    body{background:#0d1117;color:#c9d1d9}
    .card{background:#161b22;border:1px solid #30363d}
    .table{color:#c9d1d9}
    .table-hover tbody tr:hover{background:#1c2128;color:#f0f6fc}
    th{color:#8b949e;font-size:.75rem;text-transform:uppercase;font-weight:600}
    .metric-val{font-family:monospace;color:#79c0ff}
    h1{color:#f0f6fc}
    .form-control,.form-select{background:#0d1117!important;color:#c9d1d9!important;border-color:#30363d!important}
    .form-control::placeholder{color:#6e7681}
    .no-cdn-notice{background:#2d1a00;border:1px solid #bb8009;color:#e3b341;padding:.5rem;margin-bottom:1rem;font-size:.8rem}
  </style>
</head>
<body>
<div class="container-fluid py-3">
  <!-- CDN_NOTICE_HERE -->
  <div class="d-flex align-items-center gap-3 mb-3">
    <h1 class="mb-0 fs-4">Cbench Dashboard</h1>
    <small class="text-muted">auto-refresh 30 s</small>
  </div>

  <!-- Summary cards -->
  <div class="row g-3 mb-3">
    <div class="col-6 col-md-3">
      <div class="card p-3 text-center">
        <div class="fs-2 fw-bold" id="s-total">—</div>
        <div class="text-muted small">Total Runs</div>
      </div>
    </div>
    <div class="col-6 col-md-3">
      <div class="card p-3 text-center">
        <div class="fs-2 fw-bold text-success" id="s-pass">—</div>
        <div class="text-muted small">Passed</div>
      </div>
    </div>
    <div class="col-6 col-md-3">
      <div class="card p-3 text-center">
        <div class="fs-2 fw-bold text-danger" id="s-fail">—</div>
        <div class="text-muted small">Failed</div>
      </div>
    </div>
    <div class="col-6 col-md-3">
      <div class="card p-3 text-center">
        <div class="fs-2 fw-bold" id="s-bm">—</div>
        <div class="text-muted small">Benchmarks</div>
      </div>
    </div>
  </div>

  <!-- Filters -->
  <div class="card p-3 mb-3">
    <div class="row g-2">
      <div class="col-md-2">
        <input class="form-control form-control-sm" id="f-benchmark" placeholder="Benchmark">
      </div>
      <div class="col-md-2">
        <input class="form-control form-control-sm" id="f-cluster" placeholder="Cluster">
      </div>
      <div class="col-md-2">
        <input class="form-control form-control-sm" id="f-testset" placeholder="Testset">
      </div>
      <div class="col-md-2">
        <input class="form-control form-control-sm" id="f-ident" placeholder="Ident">
      </div>
      <div class="col-md-2">
        <select class="form-select form-select-sm" id="f-status">
          <option value="">All statuses</option>
          <option value="PASSED">PASSED</option>
          <option value="ERROR">ERROR</option>
        </select>
      </div>
      <div class="col-md-2">
        <button class="btn btn-sm btn-primary w-100" onclick="loadResults()">Filter</button>
      </div>
    </div>
  </div>

  <!-- Results table -->
  <div class="card mb-3">
    <div class="table-responsive">
      <table class="table table-hover table-sm mb-0">
        <thead><tr>
          <th>Benchmark</th><th>Cluster</th><th>Testset</th><th>Ident</th>
          <th>Job</th><th>NP</th><th>Status</th><th>Top Metric</th><th>Parsed At</th>
        </tr></thead>
        <tbody id="results-body">
          <tr><td colspan="9" class="text-center text-muted py-3">Loading…</td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- Trend chart -->
  <div class="card p-3 mb-3">
    <h6 class="text-muted mb-2">Metric Trend</h6>
    <div class="row g-2 mb-3">
      <div class="col-md-3">
        <input class="form-control form-control-sm" id="t-benchmark" placeholder="Benchmark (e.g. xhpl)">
      </div>
      <div class="col-md-3">
        <input class="form-control form-control-sm" id="t-metric" placeholder="Metric (e.g. gflops)">
      </div>
      <div class="col-md-2">
        <button class="btn btn-sm btn-outline-info w-100" onclick="loadTrend()">Plot</button>
      </div>
    </div>
    <canvas id="trend-chart" height="80"></canvas>
  </div>
</div>

<script>
let trendChart = null;

function statusBadge(s) {
  if (s === 'PASSED') return '<span class="badge bg-success">PASSED</span>';
  if (s && s.startsWith('ERROR')) return '<span class="badge bg-danger">' + s + '</span>';
  return '<span class="badge bg-secondary">' + (s || '') + '</span>';
}

function topMetric(metrics) {
  const entries = Object.entries(metrics || {});
  if (!entries.length) return '—';
  const [k, v] = entries[0];
  return '<span class="metric-val">' + k + '=' + (+v.value).toPrecision(4) + (v.units || '') + '</span>';
}

async function loadSummary() {
  const r = await fetch('/api/summary');
  const d = await r.json();
  document.getElementById('s-total').textContent = d.total ?? '—';
  document.getElementById('s-pass').textContent  = d.passed ?? '—';
  document.getElementById('s-fail').textContent  = d.failed ?? '—';
  document.getElementById('s-bm').textContent    = d.benchmarks ?? '—';
}

async function loadResults() {
  const p = new URLSearchParams();
  ['benchmark','cluster','testset','ident'].forEach(k => {
    const v = document.getElementById('f-' + k).value.trim();
    if (v) p.set(k, v);
  });
  const st = document.getElementById('f-status').value;
  if (st) p.set('status', st);
  p.set('limit', '100');

  const r = await fetch('/api/results?' + p);
  const rows = await r.json();
  const tbody = document.getElementById('results-body');
  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted py-3">No results</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map(row => `<tr>
    <td>${row.benchmark}</td>
    <td>${row.cluster}</td>
    <td>${row.testset}</td>
    <td>${row.ident}</td>
    <td class="text-truncate" style="max-width:150px" title="${row.jobname}">${row.jobname}</td>
    <td>${row.numprocs}</td>
    <td>${statusBadge(row.status)}</td>
    <td>${topMetric(row.metrics)}</td>
    <td class="text-muted small">${(row.parsed_at || '').slice(0, 19)}</td>
  </tr>`).join('');
}

async function loadTrend() {
  const bm = document.getElementById('t-benchmark').value.trim();
  const metric = document.getElementById('t-metric').value.trim();
  if (!bm || !metric) { alert('Enter benchmark and metric name'); return; }

  const r = await fetch('/api/trend?benchmark=' + encodeURIComponent(bm) +
                        '&metric=' + encodeURIComponent(metric));
  const data = await r.json();
  if (!data.length) { alert('No trend data found'); return; }

  const labels = data.map(d => d.ident);
  const values = data.map(d => d.value);
  const units  = data[0]?.units || '';

  if (trendChart) trendChart.destroy();
  trendChart = new Chart(document.getElementById('trend-chart'), {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: bm + ' / ' + metric + (units ? ' (' + units + ')' : ''),
        data: values,
        borderColor: '#58a6ff',
        backgroundColor: 'rgba(88,166,255,0.1)',
        tension: 0.25,
        pointRadius: 5,
        pointHoverRadius: 7,
      }]
    },
    options: {
      plugins: { legend: { labels: { color: '#c9d1d9' } } },
      scales: {
        x: { ticks: { color: '#8b949e' }, grid: { color: '#30363d' } },
        y: { ticks: { color: '#8b949e' }, grid: { color: '#30363d' } }
      }
    }
  });
}

async function refresh() {
  await Promise.all([loadSummary(), loadResults()]);
}

refresh();
setInterval(refresh, 30000);
</script>
</body>
</html>
"""


def _prometheus_text(db) -> str:
    """Render all recent metrics in Prometheus text exposition format."""
    rows = db.query(limit=2000)
    lines = [
        "# HELP cbench_metric_value Cbench benchmark metric value",
        "# TYPE cbench_metric_value gauge",
    ]
    for row in rows:
        ts_ms = ""
        if row["parsed_at"]:
            try:
                dt = datetime.fromisoformat(row["parsed_at"].replace("Z", "+00:00"))
                ts_ms = str(int(dt.timestamp() * 1000))
            except ValueError:
                pass
        for metric_name, mv in row.get("metrics", {}).items():
            labels = ",".join([
                f'benchmark="{row["benchmark"]}"',
                f'cluster="{row["cluster"]}"',
                f'testset="{row["testset"]}"',
                f'ident="{row["ident"]}"',
                f'metric="{metric_name}"',
            ])
            line = f"cbench_metric_value{{{labels}}} {mv['value']}"
            if ts_ms:
                line += f" {ts_ms}"
            lines.append(line)
    return "\n".join(lines) + "\n"


def _build_html(no_cdn: bool, assets_dir: Optional[Path]) -> str:
    """Return the dashboard HTML with appropriate asset loading strategy."""
    if no_cdn:
        # Try local asset files first
        if assets_dir:
            css_path = assets_dir / "bootstrap.min.css"
            js_path = assets_dir / "chart.umd.min.js"
            if css_path.exists() and js_path.exists():
                header = (
                    f'  <link rel="stylesheet" href="/static/bootstrap.min.css">\n'
                    f'  <script src="/static/chart.umd.min.js"></script>'
                )
            else:
                header = _HTML_MINIMAL_STYLE
        else:
            header = _HTML_MINIMAL_STYLE
        notice = (
            '\n<div class="no-cdn-notice">⚠ Running in air-gapped mode. '
            'For full UI: copy bootstrap.min.css and chart.umd.min.js into --assets-dir.</div>'
            if header == _HTML_MINIMAL_STYLE else ""
        )
    else:
        header = _HTML_CDN_HEADER
        notice = ""

    return _HTML.replace(
        "  <!-- ASSETS_HERE -->", header
    ).replace(
        "  <!-- CDN_NOTICE_HERE -->", notice
    )


def _make_flask_app(db_path: Path, no_cdn: bool = False, assets_dir: Optional[Path] = None):
    try:
        from flask import Flask, Response, jsonify, request, send_from_directory
    except ImportError:
        return None

    from cbench.db import ResultsDB

    app = Flask(__name__)
    app.config["db_path"] = db_path
    app.config["no_cdn"] = no_cdn
    app.config["assets_dir"] = assets_dir
    _html_cache = _build_html(no_cdn, assets_dir)

    @app.route("/")
    def index():
        return _html_cache, 200, {"Content-Type": "text/html; charset=utf-8"}

    @app.route("/static/<path:filename>")
    def static_assets(filename):
        if not assets_dir:
            return "Assets directory not configured", 404
        return send_from_directory(str(assets_dir), filename)

    @app.route("/api/summary")
    def api_summary():
        db = ResultsDB(app.config["db_path"])
        s = db.summary()
        total = sum(s.values())
        passed = s.get("PASSED", 0)
        with db._conn() as con:
            bm_count = con.execute(
                "SELECT COUNT(DISTINCT benchmark) FROM runs"
            ).fetchone()[0]
        return jsonify({
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "benchmarks": bm_count,
        })

    @app.route("/api/results")
    def api_results():
        db = ResultsDB(app.config["db_path"])
        kwargs: dict = {}
        for key in ("benchmark", "cluster", "testset", "ident", "status", "since", "until"):
            v = request.args.get(key)
            if v:
                kwargs[key] = v
        limit = min(int(request.args.get("limit", 100)), 1000)
        return jsonify(db.query(limit=limit, **kwargs))

    @app.route("/api/trend")
    def api_trend():
        bm = request.args.get("benchmark", "")
        metric = request.args.get("metric", "")
        if not bm or not metric:
            return jsonify({"error": "benchmark and metric are required"}), 400
        db = ResultsDB(app.config["db_path"])
        kwargs: dict = {}
        for key in ("cluster", "testset", "since", "until"):
            v = request.args.get(key)
            if v:
                kwargs[key] = v
        return jsonify(db.trend(benchmark=bm, metric=metric, **kwargs))

    @app.route("/metrics")
    def prometheus():
        db = ResultsDB(app.config["db_path"])
        return Response(_prometheus_text(db), mimetype="text/plain; version=0.0.4")

    return app


@click.command("serve")
@click.option("--port", default=8080, show_default=True, type=int,
              help="TCP port to listen on")
@click.option("--host", default="127.0.0.1", show_default=True,
              help="Address to bind (use 0.0.0.0 to expose to the network)")
@click.option("--cbenchtest", default=None, envvar="CBENCHTEST")
@click.option("--no-cdn", is_flag=True,
              help="Serve without CDN dependencies (for air-gapped HPC clusters)")
@click.option("--assets-dir", default=None, type=click.Path(),
              help="Directory containing bootstrap.min.css and chart.umd.min.js for --no-cdn mode")
def serve_cmd(
    port: int,
    host: str,
    cbenchtest: Optional[str],
    no_cdn: bool,
    assets_dir: Optional[str],
) -> None:
    """Start a web dashboard for browsing Cbench results.

    Requires the optional 'web' extra: pip install "cbench[web]"

    Endpoints:
      /         — HTML dashboard
      /api/*    — JSON API consumed by the dashboard
      /metrics  — Prometheus text exposition (for scraping)

    Air-gapped clusters: use --no-cdn to avoid CDN requests. Copy
    bootstrap.min.css and chart.umd.min.js into a local directory and pass
    it with --assets-dir; without assets the dashboard falls back to minimal
    built-in CSS (no chart support).
    """
    cbenchtest = cbenchtest or os.environ.get("CBENCHTEST", ".")
    db_path = Path(cbenchtest) / "cbench_results.db"
    assets_path = Path(assets_dir) if assets_dir else None

    app = _make_flask_app(db_path, no_cdn=no_cdn, assets_dir=assets_path)
    if app is None:
        raise click.ClickException(
            "Flask is not installed. Run: pip install 'cbench[web]'"
        )

    if not db_path.exists():
        click.echo(
            f"Warning: database not found at {db_path} — "
            "it will be created when results are stored.",
            err=True,
        )

    click.echo(f"Cbench dashboard running at http://{host}:{port}/")
    click.echo(f"Prometheus metrics at http://{host}:{port}/metrics")
    click.echo("Press Ctrl-C to stop.")
    app.run(host=host, port=port, debug=False)
