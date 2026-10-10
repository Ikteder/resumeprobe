from __future__ import annotations

from copy import deepcopy

import pytest

from resumeprobe.audit import audit_case
from resumeprobe.contracts import Scenario, digest


def fixture():
    scenario = Scenario("reference", "stable-key", "after-effect", 20261009, 0)
    result = {
        "effect_id": 1,
        "operation_id": scenario.operation_id,
        "payload_sha256": digest(scenario.payload),
    }
    snapshot = {
        "effects": [deepcopy(result)],
        "events": [
            {"kind": "worker_started", "detail": {"pid": 1}},
            {"kind": "crash_injected", "detail": {"boundary": "after-effect"}},
            {"kind": "worker_started", "detail": {"pid": 2}},
        ],
    }
    processes = [{"returncode": 86}, {"returncode": 0}]
    return scenario, snapshot, processes, result


def test_valid_reconciled_evidence():
    assert audit_case(*fixture()) == []


def test_completion_without_effect_is_rejected():
    scenario, snapshot, processes, result = fixture()
    snapshot["effects"] = []
    findings = audit_case(scenario, snapshot, processes, result)
    assert "MISSING_EFFECT" in findings
    assert "RESULT_EFFECT_MISMATCH" in findings


@pytest.mark.parametrize(
    "field,code",
    [
        ("operation_id", "RESULT_OPERATION_MISMATCH"),
        ("payload_sha256", "RESULT_PAYLOAD_MISMATCH"),
        ("effect_id", "RESULT_EFFECT_MISMATCH"),
    ],
)
def test_returned_receipt_must_identify_actual_effect(field, code):
    scenario, snapshot, processes, result = fixture()
    result[field] = "wrong"
    assert code in audit_case(scenario, snapshot, processes, result)


def test_effect_payload_drift_is_rejected():
    scenario, snapshot, processes, result = fixture()
    snapshot["effects"][0]["payload_sha256"] = "changed"
    assert "PAYLOAD_DRIFT" in audit_case(scenario, snapshot, processes, result)


def test_unreached_crash_cannot_pass():
    scenario, snapshot, processes, result = fixture()
    snapshot["events"] = [
        event for event in snapshot["events"] if event["kind"] != "crash_injected"
    ]
    assert "CRASH_BOUNDARY_NOT_PROVEN" in audit_case(scenario, snapshot, processes, result)


def test_non_crash_exit_is_not_an_injected_crash():
    scenario, snapshot, processes, result = fixture()
    processes[0]["returncode"] = 1
    assert "WORKER_PROTOCOL_FAILED" in audit_case(scenario, snapshot, processes, result)
