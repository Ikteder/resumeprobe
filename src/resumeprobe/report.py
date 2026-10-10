from __future__ import annotations

import html
import json
from collections import defaultdict
from pathlib import Path

from resumeprobe.audit import audit_case, summarize
from resumeprobe.contracts import Scenario


def load_report(path: Path) -> dict:
    if path.stat().st_size > 20_000_000:
        raise ValueError("report exceeds the 20 MB input limit")

    def reject_constant(value: str):
        raise ValueError(f"non-finite JSON value: {value}")

    report = json.loads(path.read_text(encoding="utf-8"), parse_constant=reject_constant)
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        raise ValueError("expected report schema_version 1")
    cases = report.get("cases")
    if not isinstance(cases, list) or not cases or len(cases) > 1500:
        raise ValueError("expected 1 to 1500 cases")
    seen = set()
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("case must be an object")
        try:
            scenario = Scenario(**case["scenario"])
            if case["case_id"] != scenario.case_id or scenario.case_id in seen:
                raise ValueError("invalid or duplicate case identity")
            seen.add(scenario.case_id)
            if not isinstance(case["effects"], list) or not isinstance(case["trace"], list):
                raise ValueError("effects and trace must be lists")
            if not isinstance(case["processes"], list) or not 1 <= len(case["processes"]) <= 2:
                raise ValueError("processes must contain one or two attempts")
            findings = audit_case(
                scenario,
                {"effects": case["effects"], "events": case["trace"]},
                case["processes"],
                case["result"],
            )
        except (KeyError, TypeError, AttributeError) as exc:
            raise ValueError(f"malformed case: {exc}") from exc
        inconclusive = any(
            code in findings
            for code in (
                "WORKER_PROTOCOL_FAILED",
                "CRASH_BOUNDARY_NOT_PROVEN",
                "FRESH_PROCESS_NOT_PROVEN",
            )
        )
        status = "inconclusive" if inconclusive else ("unsafe" if findings else "safe")
        if case.get("status") != status or case.get("findings") != findings:
            raise ValueError(f"stored verdict differs from evidence: {scenario.case_id}")
        if case.get("effect_count") != len(case["effects"]):
            raise ValueError(f"stored effect count differs from evidence: {scenario.case_id}")
        if case.get("completion_only_safe") != (case["processes"][-1]["returncode"] == 0):
            raise ValueError("completion baseline differs from process evidence")
        expected = (
            "safe"
            if scenario.mode == "stable-key" or scenario.boundary != "after-effect"
            else "unsafe"
        )
        if case.get("expected_status") != expected or case.get("expectation_matched") != (
            status == expected
        ):
            raise ValueError("stored expectation differs from the versioned suite")
    if report.get("summary") != summarize(cases):
        raise ValueError("stored summary differs from case evidence")
    return report


def grouped(report: dict) -> list[tuple[tuple[str, str, str], list[dict]]]:
    groups = defaultdict(list)
    for case in report["cases"]:
        scenario = case["scenario"]
        groups[(scenario["adapter"], scenario["mode"], scenario["boundary"])].append(case)
    return list(groups.items())


def render_html(report: dict) -> str:
    escape = html.escape
    summary = report["summary"]
    cards = "".join(
        f'<div class="metric"><strong>{escape(str(value))}</strong><span>'
        f"{escape(name.replace('_', ' '))}</span></div>"
        for name, value in summary.items()
    )
    rows = []
    for (adapter, mode, boundary), cases in grouped(report):
        counts = ", ".join(str(case["effect_count"]) for case in cases)
        statuses = ", ".join(sorted({case["status"] for case in cases}))
        codes = ", ".join(sorted({code for case in cases for code in case["findings"]})) or "none"
        rows.append(
            "<tr>"
            + "".join(
                f"<td>{escape(value)}</td>"
                for value in (
                    adapter,
                    mode,
                    boundary,
                    counts,
                    statuses,
                    codes,
                )
            )
            + "</tr>"
        )
    details = []
    for case in report["cases"]:
        traces = "".join(
            f"<li><strong>{escape(event['kind'])}</strong> · attempt {event['attempt']}"
            f"<pre>{escape(json.dumps(event['detail'], sort_keys=True))}</pre></li>"
            for event in case["trace"]
        )
        details.append(
            f"<details><summary>{escape(case['case_id'])} · {escape(case['status'])}"
            f" · {case['effect_count']} effect(s)</summary><ol>{traces}</ol>"
            f"<pre>{escape(json.dumps(case['processes'], indent=2))}</pre></details>"
        )
    versions = escape(json.dumps(report["versions"], sort_keys=True))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ResumeProbe recovery evidence</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#0a1324;color:#e2e8f0;
font:16px/1.6 system-ui,sans-serif}}main{{max-width:1200px;margin:auto;padding:32px 20px}}
h1{{font-size:clamp(28px,5vw,48px);line-height:1.1}}p{{max-width:85ch;color:#bac7dc}}
.tag{{font-size:12px;letter-spacing:.16em;color:#5eead4}}.metrics{{display:grid;
grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:28px 0}}
.metric{{background:#13223a;border:1px solid #304362;border-radius:12px;padding:16px}}
.metric strong{{display:block;font-size:32px;color:#5eead4}}.metric span{{font-size:14px}}
.table{{overflow:auto;border:1px solid #304362;border-radius:12px}}table{{border-collapse:
collapse;min-width:860px;width:100%;font-size:14px}}th,td{{padding:12px;text-align:left;
border-bottom:1px solid #304362}}th{{background:#13223a}}details{{margin:12px 0;padding:
14px;background:#13223a;border-radius:10px}}summary{{cursor:pointer;overflow-wrap:anywhere}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;color:#a5b4fc}}
li{{padding:6px}}code{{overflow-wrap:anywhere}}@media(max-width:600px){{main{{padding:
24px 16px}}.metrics{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
</style></head><body><main><span class="tag">PROCESS CRASH / EFFECT RECONCILIATION</span>
<h1>Did the resumed tool act twice?</h1><p>Workers abruptly exit at declared boundaries,
then resume in new processes. A separate SQLite ledger counts committed synthetic effects.
Workflow completion is the baseline; the effect contract is the measured outcome.</p>
<div class="metrics">{cards}</div><h2>Boundary matrix</h2><p>Every count is one repetition.
Expected unsafe baseline cells are diagnostic successes, not repaired applications.</p>
<div class="table"><table><thead><tr><th>Adapter</th><th>Tool mode</th><th>Crash boundary</th>
<th>Effects per repetition</th><th>Contract</th><th>Finding</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table></div><h2>Durable traces</h2>{"".join(details)}
<h2>Reproduction and limits</h2><p>Seed {report["seed"]}; versions <code>{versions}</code>.
No model or paid provider was called. Synthetic local effects and process death do not prove
remote-provider idempotency, power-loss recovery, semantic task quality, or production reliability.
The evidence is unsigned and must come from a trusted experiment.</p></main></body></html>"""


def render_svg(report: dict) -> str:
    adapters = list(dict.fromkeys(case["scenario"]["adapter"] for case in report["cases"]))
    height = 170 + len(adapters) * 175
    pieces = [
        f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 {height}"
role="img" aria-labelledby="title description"><title id="title">ResumeProbe crash recovery</title>
<desc id="description">Committed effects after a crash between effect commit and task persistence.
One effect is required. Counts are observed repetitions, not production reliability.</desc>
<rect width="960" height="{height}" rx="16" fill="#0a1324"/>
<g font-family="system-ui,sans-serif" fill="#e2e8f0">
<text x="32" y="40" font-size="24" font-weight="700">A successful resume can hide a duplicate</text>
<text x="32" y="70" font-size="15" fill="#bac7dc">
Crash: effect committed, task result not yet saved</text>'''
    ]
    y = 105
    for adapter in adapters:
        pieces.append(f'<text x="32" y="{y}" font-size="17" font-weight="700">{adapter}</text>')
        for index, mode in enumerate(("naive", "attempt-key", "stable-key")):
            cases = [
                case
                for case in report["cases"]
                if case["scenario"]["adapter"] == adapter
                and case["scenario"]["mode"] == mode
                and case["scenario"]["boundary"] == "after-effect"
            ]
            counts = ", ".join(str(case["effect_count"]) for case in cases)
            maximum = max((case["effect_count"] for case in cases), default=0)
            width = min(maximum, 4) * 145
            row_y = y + 20 + index * 40
            color = "#5eead4" if all(case["status"] == "safe" for case in cases) else "#fb923c"
            pieces.append(
                f'<text x="32" y="{row_y + 20}" font-size="15">{mode}</text>'
                f'<rect x="190" y="{row_y}" width="{width}" height="28" rx="5" '
                f'fill="{color}"/><text x="{205 + width}" y="{row_y + 20}" '
                f'font-size="15">effects: {counts}</text>'
            )
        y += 175
    pieces.append(
        f'<text x="32" y="{height - 30}" font-size="14" fill="#bac7dc">'
        "Observed local process experiments. One effect required; no semantic or remote "
        "service claim.</text></g></svg>"
    )
    return "".join(pieces)
