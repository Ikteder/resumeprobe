from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from resumeprobe.audit import summarize
from resumeprobe.http_evidence import audit_http_case, load_http_report, summary_http
from resumeprobe.report import load_report

EVIDENCE = Path(__file__).resolve().parents[1] / "docs" / "experiments"


@pytest.mark.parametrize(
    "filename,loader,summarizer",
    [
        ("recovery-v1.json", load_report, summarize),
        ("http-replay-v1.json", load_http_report, summary_http),
    ],
)
@pytest.mark.parametrize("mutation", ["missing-case", "seed", "expected-status", "summary"])
def test_declared_suite_and_verdict_cannot_be_silently_edited(
    tmp_path, filename, loader, summarizer, mutation
):
    report = loader(EVIDENCE / filename)
    if mutation == "missing-case":
        report["cases"].pop()
        report["summary"] = summarizer(report["cases"])
    elif mutation == "seed":
        report["seed"] += 1
    elif mutation == "expected-status":
        report["cases"][0]["expected_status"] = "invented"
    else:
        report["summary"]["safe"] += 1
    path = tmp_path / "edited.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    with pytest.raises(ValueError):
        loader(path)


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("pid", "SEPARATE_PROCESSES_NOT_PROVEN"),
        ("server", "SERVER_TRACE_NOT_PROVEN"),
        ("sequence", "SERVER_TRACE_NOT_PROVEN"),
        ("returncode", "CLIENT_PROTOCOL_FAILED"),
        ("request-key", "REQUEST_IDENTITY_NOT_PROVEN"),
        ("effect-key", "EFFECT_TRACE_NOT_PROVEN"),
        ("prune", "PRUNING_NOT_PROVEN"),
    ],
)
def test_http_protocol_evidence_is_reconciled(mutation, code):
    report = load_http_report(EVIDENCE / "http-replay-v1.json")
    case = deepcopy(
        next(case for case in report["cases"] if case["scenario"]["name"] == "pruned-key")
    )
    if mutation == "pid":
        case["clients"][1]["pid"] = case["clients"][0]["pid"]
    elif mutation == "server":
        case["server"]["host"] = "external.invalid"
    elif mutation == "sequence":
        case["trace"][1]["seq"] = case["trace"][0]["seq"]
    elif mutation == "returncode":
        case["processes"][0]["returncode"] = False
    elif mutation == "request-key":
        next(event for event in case["trace"] if event["kind"] == "http_request")["detail"][
            "key"
        ] = "regenerated"
    elif mutation == "effect-key":
        case["effects"][0]["request_key"] = "substituted"
    else:
        case["trace"] = [event for event in case["trace"] if event["kind"] != "key_pruned"]
    assert code in audit_http_case(case)


@pytest.mark.parametrize("body", ["[]", "null", '{"suite":"http-replay-v1"}', '{"n":NaN}'])
def test_malformed_http_report_is_a_validation_error(tmp_path, body):
    path = tmp_path / "invalid.json"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(ValueError):
        load_http_report(path)
