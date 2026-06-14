"""Parser for MLPerf Training and Inference benchmark output.

MLPerf Training emits structured :::MLLOG JSON lines via the mlperf_logging
library.  The key events are run_start / run_stop (with status: success/abort)
and eval_accuracy points in between.

MLPerf Inference uses the LoadGen summary block:
  ================================================
  MLPerf Results Summary
  ================================================
  Scenario : Offline | SingleStream | MultiStream | Server
  Samples per second: <N>          (Offline / Server)
  90th percentile latency (ns) : <N>   (SingleStream / MultiStream)
  Result is : VALID | INVALID
"""

from __future__ import annotations

import json
import re

from cbench.parsers.base import BenchmarkParser, ParseResult

# :::MLLOG {"time_ms": ..., "key": "run_start", ...}
_MLLOG_RE = re.compile(r":::MLLOG\s+(\{.*\})")

# Inference loadgen patterns
_INF_SCENARIO_RE = re.compile(r"^Scenario\s*:\s*(\S+)", re.MULTILINE)
_INF_RESULT_RE = re.compile(r"^Result is\s*:\s*(VALID|INVALID)", re.MULTILINE)
_INF_SAMPLES_RE = re.compile(r"^Samples per second\s*:\s*([\d.]+)", re.MULTILINE)
_INF_LATENCY_RE = re.compile(r"^90th percentile latency \(ns\)\s*:\s*([\d.]+)", re.MULTILINE)
_INF_MEAN_LATENCY_RE = re.compile(r"^Mean latency \(ns\)\s*:\s*([\d.]+)", re.MULTILINE)
_INF_99_LATENCY_RE = re.compile(r"^99th percentile latency \(ns\)\s*:\s*([\d.]+)", re.MULTILINE)
_INF_HEADER_RE = re.compile(r"MLPerf Results Summary")


def _parse_training(stdout: str) -> ParseResult | None:
    """Return a ParseResult if the output looks like MLPerf Training logs."""
    mllog_lines = _MLLOG_RE.findall(stdout)
    if not mllog_lines:
        return None

    run_start_ms: float | None = None
    run_stop_ms: float | None = None
    run_status: str = "unknown"
    accuracies: list[float] = []
    epochs_seen: list[float] = []

    for raw in mllog_lines:
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue

        key = entry.get("key", "")
        time_ms = entry.get("time_ms", 0)
        value = entry.get("value")
        meta = entry.get("metadata") or {}

        if key == "run_start":
            run_start_ms = float(time_ms)
        elif key == "run_stop":
            run_stop_ms = float(time_ms)
            run_status = str(meta.get("status", "unknown")).lower()
        elif key == "eval_accuracy" and value is not None:
            try:
                accuracies.append(float(value))
            except (TypeError, ValueError):
                pass
        elif key == "epoch_stop":
            ep = meta.get("epoch_num")
            if ep is not None:
                try:
                    epochs_seen.append(float(ep))
                except (TypeError, ValueError):
                    pass

    if run_start_ms is None:
        return ParseResult(status="NOTSTARTED")

    metrics: dict[str, float] = {}

    if run_stop_ms is not None and run_start_ms is not None:
        metrics["time_to_train_s"] = (run_stop_ms - run_start_ms) / 1000.0

    if accuracies:
        metrics["final_accuracy"] = accuracies[-1]
        metrics["max_accuracy"] = max(accuracies)

    if epochs_seen:
        metrics["epochs"] = max(epochs_seen)

    if run_status == "success":
        return ParseResult(status="PASSED", metrics=metrics)
    elif run_status in ("aborted", "abort"):
        return ParseResult(
            status="ERROR(ABORTED)",
            metrics=metrics,
            status_detail=f"MLPerf training run_stop status={run_status}",
        )
    elif run_stop_ms is not None:
        return ParseResult(
            status="ERROR(UNKNOWN_STATUS)",
            metrics=metrics,
            status_detail=f"run_stop status={run_status}",
        )
    else:
        # run_start seen but no run_stop
        return ParseResult(
            status="ERROR(INCOMPLETE)",
            metrics=metrics,
            status_detail="run_start seen but no run_stop",
        )


def _parse_inference(stdout: str) -> ParseResult | None:
    """Return a ParseResult if the output looks like MLPerf Inference loadgen output."""
    if not _INF_HEADER_RE.search(stdout):
        return None

    m_result = _INF_RESULT_RE.search(stdout)
    if m_result is None:
        return ParseResult(
            status="ERROR(INCOMPLETE)",
            status_detail="MLPerf Results Summary found but no 'Result is' line",
        )

    valid = m_result.group(1) == "VALID"
    metrics: dict[str, float] = {}

    m = _INF_SCENARIO_RE.search(stdout)
    scenario = m.group(1) if m else "unknown"

    m = _INF_SAMPLES_RE.search(stdout)
    if m:
        metrics["samples_per_second"] = float(m.group(1))

    m = _INF_LATENCY_RE.search(stdout)
    if m:
        metrics["latency_p90_ns"] = float(m.group(1))

    m = _INF_MEAN_LATENCY_RE.search(stdout)
    if m:
        metrics["latency_mean_ns"] = float(m.group(1))

    m = _INF_99_LATENCY_RE.search(stdout)
    if m:
        metrics["latency_p99_ns"] = float(m.group(1))

    if valid:
        return ParseResult(status="PASSED", metrics=metrics,
                           status_detail=f"scenario={scenario}")
    else:
        return ParseResult(status="ERROR(INVALID)",
                           metrics=metrics,
                           status_detail=f"scenario={scenario} result=INVALID")


class MlperfParser(BenchmarkParser):
    """Parses MLPerf Training and Inference benchmark output.

    Training (:::MLLOG format):
      Metrics: time_to_train_s, final_accuracy, max_accuracy, epochs

    Inference (LoadGen summary format):
      Metrics: samples_per_second (Offline/Server),
               latency_p90_ns / latency_mean_ns / latency_p99_ns (latency scenarios)
    """

    names = ["mlperf", "mlperf-training", "mlperf-inference"]

    def parse(self, stdout: str, stderr: str = "") -> ParseResult:
        if "CBENCH NOTICE" in stdout:
            for line in stdout.splitlines():
                if "CBENCH NOTICE" in line:
                    return ParseResult(status="NOTICE", status_detail=line.strip())

        # Try training format first (:::MLLOG lines)
        result = _parse_training(stdout)
        if result is not None:
            return result

        # Try inference format (LoadGen summary block)
        result = _parse_inference(stdout)
        if result is not None:
            return result

        return ParseResult(status="NOTSTARTED")

    def metric_units(self) -> dict[str, str]:
        return {
            # Training
            "time_to_train_s": "seconds",
            "final_accuracy": "fraction",
            "max_accuracy": "fraction",
            "epochs": "epochs",
            # Inference
            "samples_per_second": "samples/s",
            "latency_p90_ns": "ns",
            "latency_mean_ns": "ns",
            "latency_p99_ns": "ns",
        }
