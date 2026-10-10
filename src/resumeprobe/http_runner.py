from __future__ import annotations

import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

from resumeprobe import __version__
from resumeprobe.contracts import canonical
from resumeprobe.http_contract import HTTP_CASES, HttpScenario
from resumeprobe.http_evidence import audit_http_case, classify, summary_http
from resumeprobe.sink import EffectSink


def run_http_case(scenario: HttpScenario, directory: Path, timeout: float = 10) -> dict:
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "scenario.json").write_text(canonical(scenario.to_dict()), encoding="utf-8")
    environment = {**os.environ, "PYTHONHASHSEED": str(scenario.seed)}
    ready_path = directory / "server-ready.json"
    clients, processes = [], []
    with (directory / "server-stderr.txt").open("w", encoding="utf-8") as errors:
        server = subprocess.Popen(
            [sys.executable, "-m", "resumeprobe.http_server", "--directory", str(directory)],
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=errors,
        )
        try:
            deadline = time.monotonic() + timeout
            ready = None
            while time.monotonic() < deadline and server.poll() is None:
                if ready_path.exists():
                    try:
                        ready = json.loads(ready_path.read_text(encoding="utf-8"))
                        break
                    except json.JSONDecodeError:
                        pass  # Writer has not yet closed its small readiness record.
                time.sleep(0.02)
            if ready is None:
                raise ValueError("HTTP fixture server did not become ready; evidence preserved")
            for attempt in (1, 2):
                command = [
                    sys.executable,
                    "-m",
                    "resumeprobe.http_client",
                    "--directory",
                    str(directory),
                    "--port",
                    str(ready["port"]),
                    "--attempt",
                    str(attempt),
                ]
                try:
                    completed = subprocess.run(
                        command, env=environment, capture_output=True, text=True, timeout=timeout
                    )
                    processes.append(
                        {
                            "attempt": attempt,
                            "returncode": completed.returncode,
                            "stderr": completed.stderr[-4000:],
                        }
                    )
                except subprocess.TimeoutExpired:
                    processes.append(
                        {"attempt": attempt, "returncode": None, "stderr": "client timeout"}
                    )
                result_path = directory / f"client-{attempt}.json"
                clients.append(
                    json.loads(result_path.read_text(encoding="utf-8"))
                    if result_path.exists()
                    else {}
                )
                if attempt == 1 and scenario.name == "pruned-key":
                    EffectSink(directory / "sink.sqlite").prune_fixture_key(scenario.operation_id)
        finally:
            if server.poll() is None:
                server.terminate()
            try:
                server.wait(timeout=3)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=3)
    snapshot = EffectSink(directory / "sink.sqlite").snapshot()
    case = {
        "case_id": scenario.case_id,
        "scenario": scenario.to_dict(),
        "server": ready,
        "clients": clients,
        "processes": processes,
        "effects": snapshot["effects"],
        "trace": snapshot["events"],
        "effect_count": len(snapshot["effects"]),
    }
    findings = audit_http_case(case)
    status = classify(findings)
    case.update(
        {
            "findings": findings,
            "status": status,
            "completion_only_safe": clients[-1].get("status") == 200,
            "expected_status": scenario.expected_status,
            "expectation_matched": status == scenario.expected_status,
        }
    )
    return case


def run_http_matrix(
    output: Path, seed: int = 20261009, repetitions: int = 3, timeout: float = 10
) -> dict:
    if type(repetitions) is not int or not 1 <= repetitions <= 50:
        raise ValueError("repetitions must be in [1, 50]")
    if not math.isfinite(timeout) or not 0 < timeout <= 120:
        raise ValueError("timeout must be finite and in (0, 120]")
    scenarios = [
        HttpScenario(name, seed, repetition)
        for name in HTTP_CASES
        for repetition in range(repetitions)
    ]
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    cases = [
        run_http_case(scenario, output / "cases" / scenario.case_id, timeout)
        for scenario in scenarios
    ]
    report = {
        "schema_version": 1,
        "suite": "http-replay-v1",
        "seed": seed,
        "repetitions": repetitions,
        "versions": {"resumeprobe": __version__, "python": sys.version.split()[0]},
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "cases": cases,
        "summary": summary_http(cases),
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
