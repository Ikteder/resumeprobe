from __future__ import annotations

import importlib.util
import json
import xml.etree.ElementTree as ET

import pytest

from resumeprobe.cli import main
from resumeprobe.contracts import Scenario
from resumeprobe.report import load_report, render_html, render_svg
from resumeprobe.runner import run_case, run_matrix


@pytest.mark.parametrize(
    "boundary", ["none", "before-effect", "after-effect", "after-task", "after-checkpoint"]
)
@pytest.mark.parametrize("mode", ["naive", "stable-key", "attempt-key"])
def test_reference_crash_boundaries(tmp_path, boundary, mode):
    case = run_case(Scenario("reference", mode, boundary, 20261009, 0), tmp_path / "case")
    assert case["expectation_matched"], case
    assert case["effect_count"] == (2 if boundary == "after-effect" and mode != "stable-key" else 1)
    assert case["completion_only_safe"]


@pytest.mark.skipif(importlib.util.find_spec("langgraph") is None, reason="optional LangGraph")
@pytest.mark.parametrize(
    "boundary", ["none", "before-effect", "after-effect", "after-task", "after-checkpoint"]
)
@pytest.mark.parametrize("mode", ["naive", "stable-key", "attempt-key"])
def test_real_langgraph_crash_boundaries(tmp_path, boundary, mode):
    case = run_case(Scenario("langgraph", mode, boundary, 20261009, 0), tmp_path / "case")
    assert case["expectation_matched"], case
    assert case["effect_count"] == (2 if boundary == "after-effect" and mode != "stable-key" else 1)
    assert case["completion_only_safe"]


def test_existing_output_is_never_overwritten(tmp_path):
    marker = tmp_path / "user-content.txt"
    marker.write_text("preserve", encoding="utf-8")
    assert main(["run", "--output", str(tmp_path), "--repetitions", "1"]) == 2
    assert marker.read_text(encoding="utf-8") == "preserve"


def test_timeout_is_inconclusive(tmp_path):
    case = run_case(
        Scenario("reference", "stable-key", "after-effect", 1, 0),
        tmp_path / "case",
        timeout=0.00001,
    )
    assert case["status"] == "inconclusive"
    assert not case["expectation_matched"]


def test_matrix_report_roundtrip_and_tamper(tmp_path):
    output = tmp_path / "run"
    report = run_matrix(output, repetitions=1)
    assert report["summary"] == {
        "cases": 15,
        "safe": 13,
        "unsafe": 2,
        "inconclusive": 0,
        "completion_only_false_safe": 2,
        "expectation_matches": 15,
    }
    assert load_report(output / "report.json") == report
    assert main(["audit", str(output / "report.json")]) == 1
    ET.fromstring(render_svg(report))
    assert "Boundary matrix" in render_html(report)
    report["cases"][0]["status"] = "unsafe"
    (output / "tampered.json").write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError, match="stored verdict"):
        load_report(output / "tampered.json")


def test_html_escapes_untrusted_text(tmp_path):
    report = run_matrix(tmp_path / "run", repetitions=1)
    report["cases"][0]["trace"][0]["detail"] = "<script>alert(1)</script>"
    rendered = render_html(report)
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered


@pytest.mark.parametrize(
    "payload", ["{}", '{"schema_version":1,"cases":[]}', '{"schema_version":1,"cases":NaN}']
)
def test_malformed_report_rejected(tmp_path, payload):
    path = tmp_path / "invalid.json"
    path.write_text(payload, encoding="utf-8")
    assert main(["audit", str(path)]) == 2
