from __future__ import annotations

import gc
import json
import warnings
import xml.etree.ElementTree as ET
from copy import deepcopy

import pytest

from resumeprobe.cli import main
from resumeprobe.sink import EffectSink
from resumeprobe.sink_recovery import (
    SINK_BOUNDARIES,
    SinkScenario,
    audit_sink_case,
    load_sink_report,
    render_sink_html,
    render_sink_svg,
    run_sink_case,
    run_sink_matrix,
    summarize_sink,
)


@pytest.mark.parametrize("boundary", SINK_BOUNDARIES)
def test_kill_inside_real_sink_transaction(tmp_path, boundary):
    case = run_sink_case(SinkScenario(boundary, 20261009, 0), tmp_path / "case")
    assert case["expectation_matched"], case
    assert len(case["before_resume"]["effects"]) == (
        1 if boundary in ("after-commit", "split-commit") else 0
    )
    assert len(case["before_resume"]["keys"]) == (1 if boundary == "after-commit" else 0)
    assert len(case["after_resume"]["effects"]) == (2 if boundary == "split-commit" else 1)
    assert case["completion_only_safe"]


def test_sink_timeout_preserves_inconclusive_evidence(tmp_path):
    case = run_sink_case(SinkScenario("before-key", 1, 0), tmp_path / "case", timeout=0.00001)
    assert case["status"] == "inconclusive"
    assert not case["expectation_matched"]


def test_sink_connections_close_after_commit_and_rollback(tmp_path):
    gc.collect()
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always", ResourceWarning)
        sink = EffectSink(tmp_path / "sink.sqlite")
        sink.apply("op", {"v": 1}, "stable-key", 1)
        with pytest.raises(ValueError):
            sink.apply("op", {"v": 2}, "stable-key", 2)
        assert len(sink.snapshot()["effects"]) == 1
        gc.collect()
    assert not [warning for warning in recorded if warning.category is ResourceWarning]


def test_sink_report_roundtrip_coverage_tamper_and_visual(tmp_path):
    report = run_sink_matrix(tmp_path / "run", repetitions=1)
    assert report["summary"] == {
        "cases": 4,
        "safe": 3,
        "unsafe": 1,
        "inconclusive": 0,
        "completion_only_false_safe": 1,
        "expectation_matches": 4,
    }
    assert load_sink_report(tmp_path / "run/report.json") == report
    assert main(["sink-audit", str(tmp_path / "run/report.json")]) == 1
    ET.fromstring(render_sink_svg(report))
    changed = deepcopy(report)
    changed["cases"].pop()
    changed["summary"] = summarize_sink(changed["cases"])
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="coverage"):
        load_sink_report(path)
    report["cases"][0]["processes"][0]["stderr"] = "<script>test</script>"
    assert "<script>" not in render_sink_html(report)


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("result", "RESULT_IDENTITY_VIOLATION"),
        ("pre-count", "RECOVERY_STATE_VIOLATION"),
        ("pre-key", "PRE_RESUME_KEY_VIOLATION"),
        ("boundary", "CRASH_BOUNDARY_NOT_PROVEN"),
        ("pid", "FRESH_PROCESS_NOT_PROVEN"),
        ("bool-exit", "WORKER_PROTOCOL_NOT_PROVEN"),
        ("sequence", "CONTROL_ORDER_NOT_PROVEN"),
    ],
)
def test_sink_audit_rejects_inconsistent_receipts(tmp_path, mutation, code):
    case = run_sink_case(SinkScenario("after-commit", 1, 0), tmp_path / "case")
    if mutation == "result":
        case["result"]["effect_id"] = 999
    elif mutation == "pre-count":
        case["before_resume"]["effects"] = []
    elif mutation == "pre-key":
        case["before_resume"]["keys"][0]["effect_id"] = 999
    elif mutation == "boundary":
        case["control"][1]["detail"]["boundary"] = "before-key"
    elif mutation == "pid":
        case["control"][2]["pid"] = case["control"][0]["pid"]
    elif mutation == "bool-exit":
        case["processes"][1]["returncode"] = False
    else:
        case["control"][1]["seq"] = case["control"][0]["seq"]
    assert code in audit_sink_case(case)


def test_existing_sink_output_preserved(tmp_path):
    marker = tmp_path / "user.txt"
    marker.write_text("keep", encoding="utf-8")
    assert main(["sink-run", "--output", str(tmp_path)]) == 2
    assert marker.read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize("body", ["[]", "null", "{}", '{"suite":NaN}'])
def test_invalid_sink_evidence(tmp_path, body):
    path = tmp_path / "invalid.json"
    path.write_text(body, encoding="utf-8")
    assert main(["sink-audit", str(path)]) == 2
