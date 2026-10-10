from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

from resumeprobe import __version__
from resumeprobe.audit import audit_case, summarize
from resumeprobe.contracts import Scenario, canonical, matrix
from resumeprobe.sink import EffectSink


def run_case(scenario: Scenario, directory: Path, timeout: float = 20) -> dict:
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "scenario.json").write_text(canonical(scenario.to_dict()), encoding="utf-8")
    processes = []
    count = 1 if scenario.boundary == "none" else 2
    environment = os.environ.copy()
    environment["PYTHONHASHSEED"] = str(scenario.seed)
    environment["LANGCHAIN_TRACING_V2"] = "false"
    environment["LANGSMITH_TRACING"] = "false"
    result = None
    for attempt in range(1, count + 1):
        started = time.perf_counter()
        command = [
            sys.executable,
            "-m",
            "resumeprobe.worker",
            "--directory",
            str(directory),
            "--attempt",
            str(attempt),
        ]
        try:
            process = subprocess.run(
                command,
                env=environment,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
            returncode = process.returncode
            stderr = process.stderr[-4000:]
        except subprocess.TimeoutExpired:
            returncode = None
            stderr = "Worker timed out and was terminated by the supervisor."
        processes.append(
            {
                "attempt": attempt,
                "returncode": returncode,
                "stderr": stderr,
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
            }
        )
        result_path = directory / f"result-{attempt}.json"
        if returncode == 0 and result_path.exists():
            result = json.loads(result_path.read_text(encoding="utf-8"))
        if returncode is None:
            break
    snapshot = EffectSink(directory / "sink.sqlite").snapshot()
    findings = audit_case(scenario, snapshot, processes, result)
    protocol_failed = any(
        code in findings
        for code in (
            "WORKER_PROTOCOL_FAILED",
            "CRASH_BOUNDARY_NOT_PROVEN",
            "FRESH_PROCESS_NOT_PROVEN",
        )
    )
    status = "inconclusive" if protocol_failed else ("unsafe" if findings else "safe")
    expected_safe = scenario.mode == "stable-key" or scenario.boundary != "after-effect"
    return {
        "case_id": scenario.case_id,
        "scenario": scenario.to_dict(),
        "operation_id": scenario.operation_id,
        "payload_sha256": snapshot["effects"][0]["payload_sha256"] if snapshot["effects"] else None,
        "status": status,
        "findings": findings,
        "effect_count": len(snapshot["effects"]),
        "completion_only_safe": bool(processes and processes[-1]["returncode"] == 0),
        "expected_status": "safe" if expected_safe else "unsafe",
        "expectation_matched": status == ("safe" if expected_safe else "unsafe"),
        "processes": processes,
        "effects": snapshot["effects"],
        "trace": snapshot["events"],
        "result": result,
    }


def run_matrix(
    output: Path,
    *,
    seed: int = 20261009,
    repetitions: int = 3,
    adapters: tuple[str, ...] = ("reference",),
    timeout: float = 20,
) -> dict:
    cases = matrix(seed, repetitions, adapters)
    if not 0.1 <= timeout <= 300:
        raise ValueError("timeout must be between 0.1 and 300 seconds")
    versions = {"resumeprobe": __version__, "python": platform.python_version()}
    if "langgraph" in adapters:
        for package in ("langgraph", "langgraph-checkpoint-sqlite"):
            try:
                versions[package] = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError as exc:
                raise ValueError(
                    "install resumeprobe[langgraph] before selecting this adapter"
                ) from exc
    # Refuse an existing destination, even an empty one, to avoid overwriting user evidence.
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    results = [run_case(case, output / "cases" / case.case_id, timeout) for case in cases]
    report = {
        "schema_version": 1,
        "suite": "tool-recovery-v1",
        "seed": seed,
        "repetitions": repetitions,
        "versions": versions,
        "platform": platform.platform(),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "summary": summarize(results),
        "cases": results,
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
