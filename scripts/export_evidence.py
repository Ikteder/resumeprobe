"""Export generated, validated machine evidence and the README comparison asset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from resumeprobe.http_evidence import load_http_report, render_http_svg
from resumeprobe.report import load_report, render_svg


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--json", type=Path, required=True)
    parser.add_argument("--svg", type=Path, required=True)
    parser.add_argument("--http", action="store_true")
    args = parser.parse_args()
    report = load_http_report(args.report) if args.http else load_report(args.report)
    for output in (args.json, args.svg):
        output.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.svg.write_text(
        render_http_svg(report) if args.http else render_svg(report), encoding="utf-8"
    )
    print(json.dumps(report["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
