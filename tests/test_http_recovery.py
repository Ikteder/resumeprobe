from __future__ import annotations

import http.client
import json
import threading
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest

from resumeprobe.cli import main
from resumeprobe.http_client import send_request
from resumeprobe.http_contract import HTTP_CASES, HttpScenario
from resumeprobe.http_evidence import (
    audit_http_case,
    load_http_report,
    render_http_html,
    render_http_svg,
)
from resumeprobe.http_runner import run_http_case, run_http_matrix
from resumeprobe.http_server import make_server
from resumeprobe.sink import EffectSink


@pytest.mark.parametrize("name", HTTP_CASES)
def test_response_loss_real_separate_processes(tmp_path, name):
    scenario = HttpScenario(name, 20261009, 0)
    case = run_http_case(scenario, tmp_path / "case")
    assert case["expectation_matched"], case
    assert case["effect_count"] == (1 if scenario.expected_status == "safe" else 2)
    assert case["clients"][0]["outcome"] == "transport_error"
    assert case["clients"][1]["status"] == (409 if name == "payload-conflict" else 200)
    if name == "payload-conflict":
        assert not case["findings"]


@pytest.fixture
def live_server(tmp_path):
    sink = EffectSink(tmp_path / "sink.sqlite")
    server = make_server(sink, drop_first=False)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02})
    thread.start()
    try:
        yield server, sink
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        assert not thread.is_alive()


def test_concurrent_http_key_and_intent_binding(live_server):
    server, sink = live_server
    scenario = HttpScenario("stable-key", 1, 0)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(
                lambda attempt: send_request(server.server_port, scenario.request(1), attempt),
                range(1, 17),
            )
        )
    assert all(result["status"] == 200 for result in results)
    assert all(result["body"] == results[0]["body"] for result in results)
    assert len(sink.snapshot()["effects"]) == 1
    conflicting = scenario.request(1)
    conflicting["operation_id"] = "another-logical-operation"
    assert send_request(server.server_port, conflicting, 2)["status"] == 409
    assert len(sink.snapshot()["effects"]) == 1


@pytest.mark.parametrize(
    "body,headers,path,expected",
    [
        (b"{}", {}, "/effects", 400),
        (b"{}", {"Content-Type": "application/json"}, "/effects", 400),
        (
            b'{"operation_id":"op","payload":{"n":NaN}}',
            {"Content-Type": "application/json", "X-ResumeProbe-Attempt": "1"},
            "/effects",
            400,
        ),
        (
            b"",
            {
                "Content-Type": "application/json",
                "X-ResumeProbe-Attempt": "1",
                "Content-Length": "9000",
            },
            "/effects",
            413,
        ),
        (b"", {}, "/admin/prune", 404),
        (
            b"",
            {
                "Content-Type": "application/json",
                "X-ResumeProbe-Attempt": "1",
                "Transfer-Encoding": "chunked",
            },
            "/effects",
            400,
        ),
    ],
)
def test_invalid_http_inputs_have_no_effect(live_server, body, headers, path, expected):
    server, sink = live_server
    connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    try:
        connection.request("POST", path, body, headers)
        response = connection.getresponse()
        assert response.status == expected
        response.read()
    finally:
        connection.close()
    assert not sink.snapshot()["effects"]


def test_http_report_roundtrip_tamper_and_escaping(tmp_path):
    report = run_http_matrix(tmp_path / "run", repetitions=1)
    assert report["summary"] == {
        "cases": 5,
        "safe": 2,
        "unsafe": 3,
        "inconclusive": 0,
        "completion_only_false_safe": 3,
        "expectation_matches": 5,
    }
    assert load_http_report(tmp_path / "run/report.json") == report
    assert main(["http-audit", str(tmp_path / "run/report.json")]) == 1
    ET.fromstring(render_http_svg(report))
    changed = deepcopy(report)
    changed["cases"][0]["status"] = "safe"
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="verdict"):
        load_http_report(path)
    changed["cases"][0]["trace"][0]["detail"]["message"] = "<script>oops</script>"
    rendered = render_http_html(changed)
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered


def test_http_audit_does_not_trust_completion_or_drop_trace(tmp_path):
    case = run_http_case(HttpScenario("stable-key", 1, 0), tmp_path / "case")
    case["clients"][1]["body"]["effect_id"] = 999
    assert "RESULT_IDENTITY_VIOLATION" in audit_http_case(case)
    case["trace"] = [event for event in case["trace"] if event["kind"] != "http_response_dropped"]
    assert "COMMIT_BEFORE_DROP_NOT_PROVEN" in audit_http_case(case)
    case["clients"][0]["outcome"] = "response"
    assert "RESPONSE_LOSS_NOT_PROVEN" in audit_http_case(case)


@pytest.mark.parametrize("timeout", [0, -1, float("inf"), float("nan"), 121])
def test_invalid_timeout_no_output(tmp_path, timeout):
    with pytest.raises(ValueError, match="timeout"):
        run_http_matrix(tmp_path / "new", timeout=timeout)
    assert not (tmp_path / "new").exists()


def test_http_existing_output_is_preserved(tmp_path):
    marker = tmp_path / "user.txt"
    marker.write_text("keep", encoding="utf-8")
    assert main(["http-run", "--output", str(tmp_path)]) == 2
    assert marker.read_text(encoding="utf-8") == "keep"
