"""Export generated, validated machine evidence and the README comparison asset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from resumeprobe.http_evidence import load_http_report, render_http_svg
from resumeprobe.report import load_report, render_svg
from resumeprobe.sink_recovery import load_sink_report, render_sink_svg


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--svg", type=Path, required=True)
    suites = parser.add_mutually_exclusive_group()
    suites.add_argument("--http", action="store_true")
    suites.add_argument("--sink", action="store_true")
    args = parser.parse_args()
    loader = load_sink_report if args.sink else (load_http_report if args.http else load_report)
    renderer = render_sink_svg if args.sink else (render_http_svg if args.http else render_svg)
    report = loader(args.report)
    for output in (args.json, args.svg):
        output.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.svg.write_text(renderer(report), encoding="utf-8")
    print(json.dumps(report["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
