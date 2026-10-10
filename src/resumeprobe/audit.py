from __future__ import annotations

from resumeprobe.contracts import CRASH_EXIT, Scenario, digest


def audit_case(
    scenario: Scenario, snapshot: dict, processes: list[dict], result: object
) -> list[str]:
    """Audit actual evidence, independent of the expected matrix outcome."""
    findings = []
    effects = snapshot["effects"]
    events = snapshot["events"]
    expected_exits = [0] if scenario.boundary == "none" else [CRASH_EXIT, 0]
    if [process["returncode"] for process in processes] != expected_exits:
        findings.append("WORKER_PROTOCOL_FAILED")
    crash_events = [event for event in events if event["kind"] == "crash_injected"]
    if scenario.boundary != "none":
        if len(crash_events) != 1 or crash_events[0]["detail"] != {"boundary": scenario.boundary}:
            findings.append("CRASH_BOUNDARY_NOT_PROVEN")
        workers = [event["detail"]["pid"] for event in events if event["kind"] == "worker_started"]
        if len(workers) != 2 or workers[0] == workers[1]:
            findings.append("FRESH_PROCESS_NOT_PROVEN")
    if not effects:
        findings.append("MISSING_EFFECT")
    elif len(effects) > 1:
        findings.append("DUPLICATE_EFFECT")
    expected_payload = digest(scenario.payload)
    if any(effect["operation_id"] != scenario.operation_id for effect in effects):
        findings.append("OPERATION_ID_MISMATCH")
    if any(effect["payload_sha256"] != expected_payload for effect in effects):
        findings.append("PAYLOAD_DRIFT")
    if not isinstance(result, dict):
        findings.append("MISSING_RESULT")
    else:
        if result.get("operation_id") != scenario.operation_id:
            findings.append("RESULT_OPERATION_MISMATCH")
        if result.get("payload_sha256") != expected_payload:
            findings.append("RESULT_PAYLOAD_MISMATCH")
        if result.get("effect_id") not in {effect["effect_id"] for effect in effects}:
            findings.append("RESULT_EFFECT_MISMATCH")
    return findings


def summarize(cases: list[dict]) -> dict[str, int]:
    return {
        "cases": len(cases),
        "safe": sum(case["status"] == "safe" for case in cases),
        "unsafe": sum(case["status"] == "unsafe" for case in cases),
        "inconclusive": sum(case["status"] == "inconclusive" for case in cases),
        "completion_only_false_safe": sum(
            case["completion_only_safe"] and case["status"] == "unsafe" for case in cases
        ),
        "expectation_matches": sum(case["expectation_matched"] for case in cases),
    }
