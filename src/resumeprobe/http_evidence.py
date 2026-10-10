from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path

from resumeprobe.contracts import digest
from resumeprobe.http_contract import HTTP_CASES, HttpScenario


def audit_http_case(case: dict) -> list[str]:
    scenario = HttpScenario(**case["scenario"])
    findings = []
    clients, processes = case["clients"], case["processes"]
    trace, effects = case["trace"], case["effects"]
    if (
        len(processes) != 2
        or any(type(p["returncode"]) is not int or p["returncode"] != 0 for p in processes)
        or [p.get("attempt") for p in processes] != [1, 2]
    ):
        findings.append("CLIENT_PROTOCOL_FAILED")
    if (
        len(clients) != 2
        or clients[0].get("outcome") != "transport_error"
        or not clients[0].get("error_type")
        or [client.get("attempt") for client in clients] != [1, 2]
        or clients[-1].get("outcome") != "response"
    ):
        findings.append("RESPONSE_LOSS_NOT_PROVEN")
    sequence = [event["seq"] for event in trace]
    starts = [event for event in trace if event["kind"] == "http_server_started"]
    if (
        any(type(seq) is not int or seq <= 0 for seq in sequence)
        or sequence != sorted(set(sequence))
        or len(starts) != 1
        or starts[0]["detail"] != case["server"]
        or case["server"].get("host") != "127.0.0.1"
        or type(case["server"].get("port")) is not int
        or not 1 <= case["server"]["port"] <= 65535
    ):
        findings.append("SERVER_TRACE_NOT_PROVEN")
    pids = [client.get("pid") for client in clients] + [case["server"].get("pid")]
    if (
        len(pids) != 3
        or any(type(pid) is not int or pid <= 0 for pid in pids)
        or len(set(pids)) != 3
    ):
        findings.append("SEPARATE_PROCESSES_NOT_PROVEN")
    commits = [event for event in trace if event["kind"] == "effect_committed"]
    drops = [event for event in trace if event["kind"] == "http_response_dropped"]
    if (
        not commits
        or len(drops) != 1
        or commits[0]["seq"] >= drops[0]["seq"]
        or commits[0]["detail"]["effect_id"] != drops[0]["detail"].get("effect_id")
        or drops[0]["attempt"] != 1
    ):
        findings.append("COMMIT_BEFORE_DROP_NOT_PROVEN")
    requests = [event for event in trace if event["kind"] == "http_request"]
    if (
        len(requests) != 2
        or [event["attempt"] for event in requests] != [1, 2]
        or any(
            event["detail"].get("key") != scenario.request(event["attempt"])["key"]
            or event["detail"].get("pid") != case["server"].get("pid")
            for event in requests
        )
    ):
        findings.append("REQUEST_IDENTITY_NOT_PROVEN")
    prunes = [event for event in trace if event["kind"] == "key_pruned"]
    if scenario.name == "pruned-key":
        if (
            len(prunes) != 1
            or prunes[0]["detail"] != {"request_key": scenario.operation_id, "deleted": 1}
            or not drops
            or len(requests) != 2
            or not drops[0]["seq"] < prunes[0]["seq"] < requests[1]["seq"]
        ):
            findings.append("PRUNING_NOT_PROVEN")
    elif prunes:
        findings.append("UNEXPECTED_PRUNING")
    if len(effects) != 1:
        findings.append("EFFECT_COUNT_VIOLATION")
    original_digest = digest(scenario.request(1)["payload"])
    if any(
        effect["operation_id"] != scenario.operation_id
        or effect["payload_sha256"] != original_digest
        for effect in effects
    ):
        findings.append("EFFECT_PAYLOAD_VIOLATION")
    if (
        len(effects) != len(commits)
        or [effect["effect_id"] for effect in effects]
        != [event["detail"].get("effect_id") for event in commits]
        or any(
            type(effect["effect_id"]) is not int
            or effect["effect_id"] <= 0
            or effect["request_key"] != scenario.request(effect["attempt"])["key"]
            for effect in effects
        )
    ):
        findings.append("EFFECT_TRACE_NOT_PROVEN")
    response = clients[-1] if clients else {}
    if scenario.name == "payload-conflict":
        conflicts = [event for event in trace if event["kind"] == "http_conflict"]
        if response.get("status") != 409 or len(conflicts) != 1:
            findings.append("CONFLICT_NOT_REJECTED")
    else:
        body = response.get("body")
        if (
            response.get("status") != 200
            or not isinstance(body, dict)
            or body.get("operation_id") != scenario.operation_id
            or body.get("payload_sha256") != original_digest
            or body.get("effect_id") not in [effect["effect_id"] for effect in effects]
        ):
            findings.append("RESULT_IDENTITY_VIOLATION")
    return findings


def classify(findings: list[str]) -> str:
    if any(code.endswith("NOT_PROVEN") or code == "CLIENT_PROTOCOL_FAILED" for code in findings):
        return "inconclusive"
    return "unsafe" if findings else "safe"


def summary_http(cases: list[dict]) -> dict:
    statuses = Counter(case["status"] for case in cases)
    return {
        "cases": len(cases),
        "safe": statuses["safe"],
        "unsafe": statuses["unsafe"],
        "inconclusive": statuses["inconclusive"],
        "completion_only_false_safe": sum(
            case["completion_only_safe"] and case["status"] == "unsafe" for case in cases
        ),
        "expectation_matches": sum(case["expectation_matched"] for case in cases),
    }


def load_http_report(path: Path) -> dict:
    if path.stat().st_size > 10_000_000:
        raise ValueError("HTTP report exceeds 10 MB")

    def reject_constant(value):
        raise ValueError(f"non-finite JSON: {value}")

    report = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    if (
        not isinstance(report, dict)
        or report.get("schema_version") != 1
        or report.get("suite") != "http-replay-v1"
    ):
        raise ValueError("expected http-replay-v1 schema 1")
    cases = report.get("cases")
    if not isinstance(cases, list) or not 1 <= len(cases) <= 250:
        raise ValueError("expected 1 to 250 HTTP cases")
    repetitions = report.get("repetitions")
    if type(repetitions) is not int or not 1 <= repetitions <= 50:
        raise ValueError("invalid HTTP repetitions")
    expected_cases = {
        HttpScenario(name, report.get("seed"), repetition).case_id
        for name in HTTP_CASES
        for repetition in range(repetitions)
    }
    seen = set()
    for case in cases:
        try:
            scenario = HttpScenario(**case["scenario"])
            if scenario.seed != report["seed"]:
                raise ValueError("case seed differs from report seed")
            if case["case_id"] != scenario.case_id or scenario.case_id in seen:
                raise ValueError("invalid or duplicate HTTP case identity")
            seen.add(scenario.case_id)
            for field in ("clients", "processes", "trace", "effects"):
                if not isinstance(case[field], list):
                    raise ValueError(f"{field} must be a list")
            findings = audit_http_case(case)
            status = classify(findings)
            expected = scenario.expected_status
            baseline = len(case["clients"]) == 2 and case["clients"][-1].get("status") == 200
            if (
                case["findings"] != findings
                or case["status"] != status
                or case["effect_count"] != len(case["effects"])
                or case["expected_status"] != expected
                or case["expectation_matched"] != (status == expected)
                or case["completion_only_safe"] != baseline
            ):
                raise ValueError("HTTP verdict differs from supplied evidence")
        except (KeyError, TypeError, AttributeError, IndexError) as exc:
            raise ValueError(f"malformed HTTP case: {exc}") from exc
    if seen != expected_cases:
        raise ValueError("HTTP report is missing or substituting declared suite cases")
    if report.get("summary") != summary_http(cases):
        raise ValueError("HTTP summary differs from evidence")
    return report


def render_http_svg(report: dict) -> str:
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 440" '
        'role="img" aria-labelledby="title"><title id="title">'
        "Effects after a committed HTTP response is lost</title>"
        '<rect width="960" height="440" rx="16" fill="#0a1324"/>'
        '<g font-family="system-ui,sans-serif" fill="#e2e8f0">'
        '<text x="32" y="42" font-size="24" font-weight="700">'
        "A stable key stops helping when the server forgets it</text>"
        '<text x="32" y="76" font-size="15">'
        "Real loopback sockets. First response dropped after effect commit.</text>"
    ]
    for index, name in enumerate(HTTP_CASES):
        cases = [case for case in report["cases"] if case["scenario"]["name"] == name]
        count = max((case["effect_count"] for case in cases), default=0)
        counts = ", ".join(str(case["effect_count"]) for case in cases)
        color = "#5eead4" if all(case["status"] == "safe" for case in cases) else "#fb923c"
        y = 108 + index * 50
        parts.append(
            f'<text x="32" y="{y + 23}" font-size="16">{name}</text>'
            f'<rect x="220" y="{y}" width="{min(count, 4) * 140}" height="32" '
            f'rx="5" fill="{color}"/><text x="{235 + min(count, 4) * 140}" '
            f'y="{y + 23}" font-size="16">effects: {counts}</text>'
        )
    parts.append(
        '<text x="32" y="408" font-size="14">One effect required; payload conflict safely '
        "returns 409. Pruning is simulated, not provider timing.</text></g></svg>"
    )
    return "".join(parts)


def render_http_html(report: dict) -> str:
    escape = html.escape
    rows, details = [], []
    for name in HTTP_CASES:
        cases = [case for case in report["cases"] if case["scenario"]["name"] == name]
        rows.append(
            "<tr>"
            + "".join(
                f"<td>{escape(value)}</td>"
                for value in (
                    name,
                    ", ".join(str(case["effect_count"]) for case in cases),
                    ", ".join(sorted({case["status"] for case in cases})),
                    ", ".join(str(case["clients"][-1].get("status")) for case in cases),
                )
            )
            + "</tr>"
        )
    for case in report["cases"]:
        evidence = {key: case[key] for key in ("server", "clients", "trace", "findings")}
        details.append(
            f"<details><summary>{escape(case['case_id'])}: {escape(case['status'])}</summary>"
            f"<pre>{escape(json.dumps(evidence, indent=2))}</pre></details>"
        )
    metrics = escape(json.dumps(report["summary"], indent=2))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HTTP replay evidence</title>
<style>*{{box-sizing:border-box}}body{{background:#0a1324;color:#e2e8f0;margin:0;font:16px/1.6
system-ui,sans-serif}}main{{max-width:1100px;padding:28px 20px;margin:auto}}h1{{font-size:clamp(
28px,5vw,44px);line-height:1.2}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;color:#a5b4fc}}
.table{{overflow:auto}}table{{border-collapse:collapse;width:100%;min-width:580px}}th,td{{padding:
12px;text-align:left;border-bottom:1px solid #304362}}details{{padding:14px;background:#13223a;
margin:12px 0;border-radius:10px}}summary{{cursor:pointer;overflow-wrap:anywhere}}</style>
</head><body><main><h1>The server committed. The client heard nothing.</h1><p>A separate
loopback server commits a synthetic effect before dropping the socket. Fresh clients retry.
Stable retained keys deduplicate; regenerated or explicitly pruned keys do not. Changed
payloads must fail closed. A 409 conflict is safe rejection, not successful completion.</p>
<pre>{metrics}</pre><h2>Observed replay matrix</h2><div class="table"><table><thead><tr>
<th>Scenario</th><th>Effects per repetition</th><th>Contract</th><th>Retry HTTP status</th></tr>
</thead><tbody>{"".join(rows)}</tbody></table></div><h2>Independent process and ledger evidence</h2>
{"".join(details)}<h2>Limits</h2><p>Seed {report["seed"]}.
Authored local fixtures, unsigned evidence,
simulated key pruning, no production endpoint or model. No provider compatibility, retention
duration, distributed transaction, server-crash, or cross-host reliability claim.</p></main>
</body></html>"""
