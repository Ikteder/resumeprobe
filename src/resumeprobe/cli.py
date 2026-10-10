from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from resumeprobe.contracts import ADAPTERS
from resumeprobe.http_evidence import load_http_report, render_http_html, render_http_svg
from resumeprobe.http_runner import run_http_matrix
from resumeprobe.report import load_report, render_html, render_svg
from resumeprobe.runner import run_matrix
from resumeprobe.sink_recovery import (
    load_sink_report,
    render_sink_html,
    render_sink_svg,
    run_sink_matrix,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Test recovery against committed tool effects")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="Run a bounded synthetic process-crash matrix")
    run.add_argument("--output", type=Path, required=True, help="New evidence directory")
    run.add_argument("--seed", type=int, default=20261009)
    run.add_argument("--repetitions", type=int, default=3)
    run.add_argument("--adapters", nargs="+", choices=ADAPTERS, default=["reference"])
    run.add_argument("--timeout", type=float, default=20)
    audit = commands.add_parser("audit", help="Recompute report verdicts from supplied evidence")
    audit.add_argument("report", type=Path)
    http_run = commands.add_parser("http-run", help="Test response loss and bounded key retention")
    http_run.add_argument("--output", type=Path, required=True)
    http_run.add_argument("--seed", type=int, default=20261009)
    http_run.add_argument("--repetitions", type=int, default=3)
    http_run.add_argument("--timeout", type=float, default=10)
    http_audit = commands.add_parser("http-audit", help="Recompute HTTP replay evidence")
    http_audit.add_argument("report", type=Path)
    sink_run = commands.add_parser(
        "sink-run", help="Crash inside the tool's effect/key transaction"
    )
    sink_run.add_argument("--output", type=Path, required=True)
    sink_run.add_argument("--seed", type=int, default=20261009)
    sink_run.add_argument("--repetitions", type=int, default=3)
    sink_run.add_argument("--timeout", type=float, default=10)
    sink_audit = commands.add_parser("sink-audit", help="Reconcile sink transaction crash evidence")
    sink_audit.add_argument("report", type=Path)
    try:
        args = parser.parse_args(argv)
        if args.command == "run":
            report = run_matrix(
                args.output,
                seed=args.seed,
                repetitions=args.repetitions,
                adapters=tuple(args.adapters),
                timeout=args.timeout,
            )
            (args.output / "report.html").write_text(render_html(report), encoding="utf-8")
            (args.output / "comparison.svg").write_text(render_svg(report), encoding="utf-8")
            print(json.dumps(report["summary"], indent=2))
            print(f"Evidence: {args.output.resolve()}")
            return (
                0 if report["summary"]["expectation_matches"] == report["summary"]["cases"] else 1
            )
        if args.command in ("http-run", "sink-run"):
            runner = run_http_matrix if args.command == "http-run" else run_sink_matrix
            html_renderer = render_http_html if args.command == "http-run" else render_sink_html
            svg_renderer = render_http_svg if args.command == "http-run" else render_sink_svg
            report = runner(args.output, args.seed, args.repetitions, args.timeout)
            (args.output / "report.html").write_text(html_renderer(report), encoding="utf-8")
            (args.output / "comparison.svg").write_text(svg_renderer(report), encoding="utf-8")
            print(json.dumps(report["summary"], indent=2))
            print(f"Evidence: {args.output.resolve()}")
            return (
                0 if report["summary"]["expectation_matches"] == report["summary"]["cases"] else 1
            )
        loaders = {
            "http-audit": load_http_report,
            "sink-audit": load_sink_report,
            "audit": load_report,
        }
        report = loaders[args.command](args.report)
        print(json.dumps(report["summary"], indent=2))
        return 0 if report["summary"]["safe"] == report["summary"]["cases"] else 1
    except (ValueError, OSError) as exc:
        print(f"resumeprobe: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
