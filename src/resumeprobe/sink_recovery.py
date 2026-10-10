from __future__ import annotations

import html
import json
import math
import os
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path

from resumeprobe import __version__
from resumeprobe.contracts import CRASH_EXIT, canonical, digest
from resumeprobe.sink import EffectSink

SINK_BOUNDARIES = ("before-key", "after-key", "after-commit", "split-commit")


@dataclass(frozen=True)
class SinkScenario:
    boundary: str
    seed: int
    repetition: int

    def __post_init__(self):
        if self.boundary not in SINK_BOUNDARIES:
            raise ValueError("unknown sink boundary")
        if type(self.seed) is not int or not 0 <= self.seed <= 2**32 - 1:
            raise ValueError("seed must be in [0, 2^32-1]")
        if type(self.repetition) is not int or not 0 <= self.repetition < 50:
            raise ValueError("repetition must be in [0, 49]")

    @property
    def case_id(self):
        return f"sink-{self.boundary}-{self.repetition}"

    @property
    def operation_id(self):
        return digest(asdict(self))[:24]

    @property
    def payload(self):
        return {
            "action": "publish_synthetic_receipt",
            "seed": self.seed,
            "record": self.operation_id,
        }


def audit_sink_case(case: dict) -> list[str]:
    scenario = SinkScenario(**case["scenario"])
    findings = []
    if (
        [p["returncode"] for p in case["processes"]] != [CRASH_EXIT, 0]
        or any(type(p["returncode"]) is not int for p in case["processes"])
        or [p["attempt"] for p in case["processes"]] != [1, 2]
    ):
        findings.append("WORKER_PROTOCOL_NOT_PROVEN")
    control = case["control"]
    starts = [event for event in control if event["kind"] == "worker_started"]
    crashes = [event for event in control if event["kind"] == "crash_injected"]
    sequences = [event["seq"] for event in control]
    if sequences != sorted(set(sequences)) or any(
        type(seq) is not int or seq <= 0 for seq in sequences
    ):
        findings.append("CONTROL_ORDER_NOT_PROVEN")
    if (
        len(starts) != 2
        or [e["attempt"] for e in starts] != [1, 2]
        or len({e["pid"] for e in starts}) != 2
        or any(type(e["pid"]) is not int or e["pid"] <= 0 for e in starts)
    ):
        findings.append("FRESH_PROCESS_NOT_PROVEN")
    if (
        len(crashes) != 1
        or crashes[0]["attempt"] != 1
        or crashes[0]["detail"] != {"boundary": scenario.boundary}
        or not starts
        or crashes[0]["pid"] != starts[0]["pid"]
    ):
        findings.append("CRASH_BOUNDARY_NOT_PROVEN")
    elif len(starts) == 2 and not starts[0]["seq"] < crashes[0]["seq"] < starts[1]["seq"]:
        findings.append("CONTROL_ORDER_NOT_PROVEN")
    pre_effects = case["before_resume"]["effects"]
    pre_keys = case["before_resume"]["keys"]
    expected_pre_effects = 1 if scenario.boundary in ("after-commit", "split-commit") else 0
    expected_pre_keys = 1 if scenario.boundary == "after-commit" else 0
    if len(pre_effects) != expected_pre_effects or len(pre_keys) != expected_pre_keys:
        findings.append("RECOVERY_STATE_VIOLATION")
    final = case["after_resume"]
    if len(final["effects"]) != 1:
        findings.append("EFFECT_COUNT_VIOLATION")
    expected_digest = digest(scenario.payload)
    if any(
        effect["operation_id"] != scenario.operation_id
        or effect["payload_sha256"] != expected_digest
        or effect["request_key"] != scenario.operation_id
        for effect in pre_effects + final["effects"]
    ):
        findings.append("EFFECT_IDENTITY_VIOLATION")
    keys = final["keys"]
    if any(
        key["request_key"] != scenario.operation_id
        or key["payload_sha256"] != expected_digest
        or key["effect_id"] not in [effect["effect_id"] for effect in pre_effects]
        for key in pre_keys
    ):
        findings.append("PRE_RESUME_KEY_VIOLATION")
    if (
        len(keys) != 1
        or keys[0]["request_key"] != scenario.operation_id
        or keys[0]["payload_sha256"] != expected_digest
        or keys[0]["effect_id"] not in [effect["effect_id"] for effect in final["effects"]]
    ):
        findings.append("KEY_EFFECT_BINDING_VIOLATION")
    result = case["result"]
    if (
        not isinstance(result, dict)
        or result.get("operation_id") != scenario.operation_id
        or (
            result.get("payload_sha256") != expected_digest
            or result.get("effect_id") not in [effect["effect_id"] for effect in final["effects"]]
        )
    ):
        findings.append("RESULT_IDENTITY_VIOLATION")
    return findings


def classify_sink(findings: list[str]) -> str:
    if any(finding.endswith("NOT_PROVEN") for finding in findings):
        return "inconclusive"
    return "unsafe" if findings else "safe"


def summarize_sink(cases: list[dict]) -> dict:
    return {
        "cases": len(cases),
        "safe": sum(c["status"] == "safe" for c in cases),
        "unsafe": sum(c["status"] == "unsafe" for c in cases),
        "inconclusive": sum(c["status"] == "inconclusive" for c in cases),
        "completion_only_false_safe": sum(
            c["status"] == "unsafe" and c["completion_only_safe"] for c in cases
        ),
        "expectation_matches": sum(c["expectation_matched"] for c in cases),
    }


def run_sink_case(scenario: SinkScenario, directory: Path, timeout: float = 10) -> dict:
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "scenario.json").write_text(canonical(asdict(scenario)), encoding="utf-8")
    processes, before = [], None
    environment = {**os.environ, "PYTHONHASHSEED": str(scenario.seed)}
    for attempt in (1, 2):
        try:
            worker = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "resumeprobe.sink_worker",
                    "--directory",
                    str(directory),
                    "--attempt",
                    str(attempt),
                ],
                env=environment,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            processes.append(
                {
                    "attempt": attempt,
                    "returncode": worker.returncode,
                    "stderr": worker.stderr[-4000:],
                }
            )
        except subprocess.TimeoutExpired:
            processes.append({"attempt": attempt, "returncode": None, "stderr": "timeout"})
        if attempt == 1:
            before = EffectSink(directory / "sink.sqlite").snapshot()
    control = []
    control_path = directory / "control.sqlite"
    if control_path.exists():
        with closing(sqlite3.connect(control_path)) as db:
            db.row_factory = sqlite3.Row
            rows = (
                db.execute("SELECT * FROM events ORDER BY seq")
                if db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='events'"
                ).fetchone()
                else []
            )
            for row in rows:
                event = dict(row)
                event["detail"] = json.loads(event["detail"])
                control.append(event)
    result_path = directory / "result.json"
    case = {
        "case_id": scenario.case_id,
        "scenario": asdict(scenario),
        "processes": processes,
        "control": control,
        "before_resume": before,
        "after_resume": EffectSink(directory / "sink.sqlite").snapshot(),
        "result": json.loads(result_path.read_text(encoding="utf-8"))
        if result_path.exists()
        else None,
    }
    findings = audit_sink_case(case)
    status = classify_sink(findings)
    expected = "unsafe" if scenario.boundary == "split-commit" else "safe"
    case.update(
        {
            "findings": findings,
            "status": status,
            "expected_status": expected,
            "expectation_matched": status == expected,
            "completion_only_safe": processes[-1]["returncode"] == 0,
        }
    )
    return case


def run_sink_matrix(
    output: Path, seed: int = 20261009, repetitions: int = 3, timeout: float = 10
) -> dict:
    if type(repetitions) is not int or not 1 <= repetitions <= 50:
        raise ValueError("repetitions must be in [1, 50]")
    if not math.isfinite(timeout) or not 0 < timeout <= 120:
        raise ValueError("timeout must be finite and in (0,120]")
    scenarios = [
        SinkScenario(boundary, seed, repetition)
        for boundary in SINK_BOUNDARIES
        for repetition in range(repetitions)
    ]
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    cases = [
        run_sink_case(scenario, output / "cases" / scenario.case_id, timeout)
        for scenario in scenarios
    ]
    report = {
        "schema_version": 1,
        "suite": "sink-atomicity-v1",
        "seed": seed,
        "repetitions": repetitions,
        "versions": {
            "resumeprobe": __version__,
            "python": sys.version.split()[0],
            "sqlite": sqlite3.sqlite_version,
        },
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        "cases": cases,
        "summary": summarize_sink(cases),
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def load_sink_report(path: Path) -> dict:
    if path.stat().st_size > 10_000_000:
        raise ValueError("sink report exceeds 10 MB")

    def reject_constant(value):
        raise ValueError(f"non-finite JSON: {value}")

    report = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    if (
        not isinstance(report, dict)
        or report.get("suite") != "sink-atomicity-v1"
        or report.get("schema_version") != 1
    ):
        raise ValueError("expected sink-atomicity-v1 schema 1")
    repetitions = report.get("repetitions")
    if type(repetitions) is not int or not 1 <= repetitions <= 50:
        raise ValueError("invalid repetitions")
    expected_ids = {
        SinkScenario(boundary, report.get("seed"), repetition).case_id
        for boundary in SINK_BOUNDARIES
        for repetition in range(repetitions)
    }
    cases, seen = report.get("cases"), set()
    if not isinstance(cases, list) or not 1 <= len(cases) <= 200:
        raise ValueError("expected 1 to 200 sink cases")
    for case in cases:
        try:
            scenario = SinkScenario(**case["scenario"])
            if (
                case["case_id"] != scenario.case_id
                or scenario.case_id in seen
                or scenario.seed != report["seed"]
            ):
                raise ValueError("invalid sink case identity")
            seen.add(scenario.case_id)
            findings = audit_sink_case(case)
            status = classify_sink(findings)
            expected = "unsafe" if scenario.boundary == "split-commit" else "safe"
            if (
                case["findings"] != findings
                or case["status"] != status
                or case["expected_status"] != expected
                or case["expectation_matched"] != (status == expected)
                or case["completion_only_safe"] != (case["processes"][-1]["returncode"] == 0)
            ):
                raise ValueError("sink verdict differs from evidence")
        except (KeyError, TypeError, AttributeError, IndexError) as exc:
            raise ValueError(f"malformed sink case: {exc}") from exc
    if seen != expected_ids or report.get("summary") != summarize_sink(cases):
        raise ValueError("sink suite coverage or summary differs from evidence")
    return report


def render_sink_html(report: dict) -> str:
    rows = []
    for case in report["cases"]:
        rows.append(
            f"<details><summary>{html.escape(case['case_id'])}: "
            f"{html.escape(case['status'])}</summary><pre>"
            f"{html.escape(json.dumps(case, indent=2))}</pre></details>"
        )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Sink atomicity</title>
<style>*{{box-sizing:border-box}}body{{margin:0;background:#0a1324;color:#e2e8f0;font:16px/1.6
system-ui,sans-serif}}main{{max-width:1100px;margin:auto;padding:28px 20px}}h1{{font-size:clamp(
28px,5vw,44px);line-height:1.2}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;color:#a5b4fc}}
details{{padding:14px;background:#13223a;margin:12px 0;border-radius:10px}}summary{{cursor:pointer;
overflow-wrap:anywhere}}</style></head><body><main><h1>Crash inside the tool transaction</h1>
<p>The real sink keeps the effect and deduplication key atomic. A deliberately broken fixture
commits them separately. Both can finish after retry; only one preserves the effect contract.
Pre-resume snapshots and a separate crash-control database expose the boundary.</p>
<pre>{html.escape(json.dumps(report["summary"], indent=2))}</pre>{"".join(rows)}<h2>Limits</h2>
<p>Local SQLite, real process death, synthetic effects, unsigned evidence. No hardware power
loss, filesystem corruption, distributed atomicity, provider, or model claim.</p>
</main></body></html>"""


def render_sink_svg(report: dict) -> str:
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 390" role="img" '
        'aria-labelledby="title"><title id="title">Sink transaction crash effects</title>'
        '<rect width="960" height="390" rx="16" fill="#0a1324"/>'
        '<g font-family="system-ui,sans-serif" fill="#e2e8f0">'
        '<text x="32" y="44" font-size="24" font-weight="700">'
        "The key and effect must survive together</text>"
        '<text x="32" y="77" font-size="15">'
        "Observed process crashes inside the real SQLite sink transaction.</text>"
    ]
    for index, boundary in enumerate(SINK_BOUNDARIES):
        cases = [c for c in report["cases"] if c["scenario"]["boundary"] == boundary]
        counts = [len(c["after_resume"]["effects"]) for c in cases]
        width = min(max(counts, default=0), 4) * 140
        color = "#5eead4" if all(c["status"] == "safe" for c in cases) else "#fb923c"
        y = 106 + index * 50
        parts.append(
            f'<text x="32" y="{y + 22}" font-size="16">{boundary}</text>'
            f'<rect x="220" y="{y}" width="{width}" height="32" rx="5" '
            f'fill="{color}"/><text x="{235 + width}" y="{y + 22}" font-size="16">'
            f"effects: {', '.join(map(str, counts))}</text>"
        )
    parts.append(
        '<text x="32" y="358" font-size="14">split-commit is intentionally unsafe '
        "comparison code, not the real sink. No power-loss claim.</text></g></svg>"
    )
    return "".join(parts)
